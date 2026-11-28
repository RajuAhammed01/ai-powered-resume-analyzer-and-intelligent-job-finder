import base64
import io
import os
import re
import time
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from PIL import Image

from app.extensions import db
from app.models import JobPreference, Resume, SavedJob, User
from app.routes.jobs import USER_JOBS_CACHE
from app.services.bd_companies import BD_TECH_COMPANIES
from app.services.job_validator import (
    normalize_apply_url,
    is_valid_apply_url,
    generate_job_id,
    GLOBAL_JOBS_REGISTRY,
    clean_job_for_registry,
)
from app.services.job_api import fetch_jobs
from app.services.profile_detector import detect_candidate_profile, detect_candidate_seniority_intent, get_job_ordering_tuple
from app.services.resume_parser import extract_structure
from app.services.skill_extractor import extract_skills
from app.services.skill_gap import analyze_job_skill_gap
from app.services.job_verifier import attach_reliability_to_job

main_bp = Blueprint("main", __name__)

ALLOWED_AVATAR_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB upload limit


def _allowed_avatar(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


@main_bp.route("/avatar/<path:filename>")
def serve_avatar(filename):
    """Serve uploaded avatar images securely with directory traversal prevention and DB fallback."""
    avatar_folder = current_app.config.get("AVATAR_FOLDER") or os.path.join(
        current_app.config["UPLOAD_FOLDER"], "avatars"
    )
    safe_name = os.path.basename(filename)
    if safe_name != filename or not _allowed_avatar(safe_name):
        abort(404)

    full_path = os.path.join(avatar_folder, safe_name)
    if os.path.isfile(full_path):
        return send_from_directory(avatar_folder, safe_name)

    # Serverless resilience: recover image data from the persistent database
    from app.models import User
    user = None
    if safe_name.startswith("avatar_"):
        parts = safe_name.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            user = db.session.get(User, int(parts[1]))
    if not user:
        user = User.query.filter_by(profile_image=safe_name).first()

    raw_data = getattr(user, "avatar_data", None) or getattr(user, "profile_image", "")
    if user and raw_data and raw_data.startswith("data:image/"):
        try:
            header, encoded = raw_data.split(",", 1)
            mime = header.split(";")[0].replace("data:", "")
            img_bytes = base64.b64decode(encoded)
            try:
                os.makedirs(avatar_folder, exist_ok=True)
                with open(full_path, "wb") as f:
                    f.write(img_bytes)
            except Exception:
                pass
            resp = Response(img_bytes, mimetype=mime)
            resp.headers["Cache-Control"] = "public, max-age=86400"
            return resp
        except Exception:
            pass

    abort(404)


USER_DASHBOARD_CACHE = {}


@main_bp.route("/api/index")
@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.upload_date.desc()).first()
    saved_jobs = SavedJob.query.filter_by(user_id=current_user.id).order_by(SavedJob.saved_date.desc()).all()
    extracted_skills_count = len(resume.skills) if resume and resume.skills else 0

    recommended_jobs = []
    top_match_score = None
    skill_gap_summary = []

    candidate_profile = None
    if resume:
        cache_entry = USER_DASHBOARD_CACHE.get(current_user.id)
        if (
            cache_entry
            and cache_entry.get("resume_id") == resume.id
            and (time.time() - cache_entry.get("timestamp", 0) < 1800)
            and cache_entry.get("recommended_jobs")
        ):
            recommended_jobs = cache_entry["recommended_jobs"]
            top_match_score = cache_entry["top_match_score"]
            skill_gap_summary = cache_entry["skill_gap_summary"]
            candidate_profile = cache_entry["candidate_profile"]

            # Re-register cached recommended jobs so 'Apply Now' clicks never encounter 'cant find any job'
            USER_JOBS_CACHE[current_user.id] = recommended_jobs
            for rj in recommended_jobs:
                if rj.get("job_id"):
                    GLOBAL_JOBS_REGISTRY[rj["job_id"]] = clean_job_for_registry(rj)
        else:
            pref = JobPreference.query.filter_by(user_id=current_user.id).first()
            resume_skills = resume.skills or []
            resume_text = resume.extracted_text or ""
            candidate_profile = detect_candidate_profile(resume_skills, resume_text, current_user.title_role or "")
            candidate_domain = candidate_profile["primary_domain"]
            candidate_title = current_user.title_role if (current_user.title_role and current_user.title_role != "Job Seeker") else candidate_profile["recommended_role"]

            seniority_intent = detect_candidate_seniority_intent(
                resume_text=resume_text,
                declared_title=current_user.title_role or "",
                experience_level_pref=pref.experience_level if pref else "",
                job_type_pref=pref.job_type if pref else "",
                education_text=resume.education or "",
            )
            is_internship_seeking = seniority_intent["is_internship_seeking"]
            is_entry_level_seeking = seniority_intent["is_entry_level_seeking"]

            if pref and pref.target_role and pref.target_role not in ["Software Engineer", "Machine Learning Engineer, Data Scientist"]:
                target_role = pref.target_role
            else:
                target_role = candidate_profile["recommended_role"]

            location = (pref.location if pref else None) or "Remote"

            from app.services.bd_job_scraper import is_bangladesh_resume_or_location
            is_bd_candidate = is_bangladesh_resume_or_location(
                text=resume_text,
                location_val=((pref.location if pref else '') or '') + ' ' + (current_user.location or ''),
                phone_val=current_user.phone or '',
                education_val=resume.education or '',
            ) or (pref and pref.country and pref.country.lower() in ['bangladesh', 'bd'])
            target_country = "bangladesh" if is_bd_candidate else "all"

            raw_jobs = fetch_jobs(target_role, location, country=target_country)
            processed_jobs = []
            # Process up to 25 prioritized candidate jobs for optimal responsive dashboard ranking
            for index, job_item in enumerate(raw_jobs[:25]):
                job = dict(job_item)
                description = job.get("job_description", "")
                extracted_j = extract_skills(description)
                provider_tags = job.get("job_skills") or []
                combined_j = sorted(list(set(extracted_j + provider_tags)))
                job["job_skills"] = combined_j

                # Transparent, multi-signal, domain-aligned skill gap analysis
                analysis = analyze_job_skill_gap(
                    resume_skills=resume_skills,
                    job_skills=combined_j,
                    resume_text=resume_text,
                    job_description=description,
                    candidate_title=candidate_title,
                    job_title=job.get("job_title", ""),
                    experience_text=resume.experience or "",
                    education_text=resume.education or "",
                    candidate_domain=candidate_domain,
                    is_internship_seeking=is_internship_seeking,
                    employment_type=job.get("job_employment_type", ""),
                )
                job["match_score"] = analysis["skill_coverage_score"]
                job["cosine_score"] = analysis["semantic_score"]
                job["title_score"] = analysis["title_score"]
                job["experience_score"] = analysis["experience_score"]
                job["education_score"] = analysis["education_score"]
                job["combined_score"] = analysis["final_score"]
                job["is_unrelated_domain"] = analysis["is_unrelated_domain"]
                job["domain_info"] = analysis["domain_info"]
                job["matched_skills"] = analysis["matched_skills"]
                job["partial_skills"] = analysis["partial_skills"]
                job["missing_skills"] = analysis["missing_skills"]
                job["score_explanation"] = analysis["summary_explanation"]
                job["actionable_advice"] = analysis["actionable_advice"]
                job["score_breakdown"] = analysis["score_breakdown"]
                job["skill_points"] = analysis["skill_points"]
                job["seniority_level"] = analysis.get("seniority_level", "experienced")
                job["is_internship"] = analysis.get("is_internship", False)
                job["is_entry_level"] = analysis.get("is_entry_level", False)
                job["is_experienced"] = analysis.get("is_experienced", True)
                job["display_seniority"] = analysis.get("display_seniority", "Experienced")
                job["badge_color"] = analysis.get("badge_color", "#1e40af")
                job["badge_bg"] = analysis.get("badge_bg", "#eff6ff")
                job["qualifications_score"] = analysis.get("qualifications_score", 70)
                job["projects_score"] = analysis.get("projects_score", 70)
                job["responsibilities_score"] = analysis.get("responsibilities_score", 70)
                job["strong_skills"] = analysis.get("strong_skills", [])
                job["missing_skills_detailed"] = analysis.get("missing_skills_detailed", [])
                job["detailed_diagnostic"] = analysis.get("detailed_diagnostic", {})
                attach_reliability_to_job(job)
                processed_jobs.append(job)

            # Prioritize verified Bangladesh top tech companies, then internship/entry-level/domain match
            def dashboard_priority_sort(j):
                is_bd_comp = 0 if (
                    j.get("is_bangladesh")
                    or any(c.lower() in (j.get("company") or "").lower() for c in BD_TECH_COMPANIES)
                    or any(c.lower() in (j.get("employer_name") or "").lower() for c in BD_TECH_COMPANIES)
                ) else 1
                ordering_tuple = get_job_ordering_tuple(
                    j,
                    is_internship_seeking=is_internship_seeking,
                    is_entry_level_seeking=is_entry_level_seeking,
                )
                return (is_bd_comp, *ordering_tuple)

            # Filter out unrelated category jobs to ensure top recommended jobs are genuinely suitable
            compatible_jobs = [j for j in processed_jobs if not j.get("is_unrelated_domain", False)]
            display_dashboard_jobs = compatible_jobs if compatible_jobs else processed_jobs
            display_dashboard_jobs.sort(key=dashboard_priority_sort, reverse=False)

            # Re-assign cache_id strictly AFTER sorting and ensure all jobs have valid job_ids and registry entries
            for idx, job in enumerate(display_dashboard_jobs):
                job["cache_id"] = idx
                if not job.get("job_id"):
                    job["job_id"] = generate_job_id(job)
                GLOBAL_JOBS_REGISTRY[job["job_id"]] = clean_job_for_registry(job)

            USER_JOBS_CACHE[current_user.id] = display_dashboard_jobs[:25]
            recommended_jobs = display_dashboard_jobs[:3]

            if recommended_jobs:
                top_match_score = recommended_jobs[0]["combined_score"]

            # Aggregate missing skills from actual live recommended jobs
            missing_skills_map = {}
            sample_jobs = processed_jobs[:10]
            for j in sample_jobs:
                for s in j.get("missing_skills", []):
                    missing_skills_map[s] = missing_skills_map.get(s, 0) + 1

            top_missing_sorted = sorted(missing_skills_map.items(), key=lambda x: x[1], reverse=True)[:5]
            ref_count = max(1, len(sample_jobs))
            for idx, (skill_name, count) in enumerate(top_missing_sorted):
                demand_pct = max(35, min(95, int(round((count / ref_count) * 100))))
                level = "High demand" if demand_pct >= 50 else "Medium demand"
                color = "#ef4444" if demand_pct >= 50 else "#f59e0b"
                skill_gap_summary.append({
                    "skill": skill_name,
                    "demand": demand_pct,
                    "level": level,
                    "color": color,
                    "count": count,
                    "total": ref_count,
                })

            USER_DASHBOARD_CACHE[current_user.id] = {
                "recommended_jobs": recommended_jobs,
                "top_match_score": top_match_score,
                "skill_gap_summary": skill_gap_summary,
                "candidate_profile": candidate_profile,
                "resume_id": resume.id,
                "timestamp": time.time(),
            }

    pipeline_stats = {
        "saved": len([j for j in saved_jobs if (j.status or "Saved").lower() == "saved"]),
        "applied": len([j for j in saved_jobs if (j.status or "").lower() == "applied"]),
        "interview": len([j for j in saved_jobs if (j.status or "").lower() == "interview"]),
        "offer": len([j for j in saved_jobs if (j.status or "").lower() == "offer"]),
        "total": len(saved_jobs),
    }

    return render_template(
        "dashboard.html",
        resume=resume,
        candidate_profile=candidate_profile,
        saved_jobs=saved_jobs,
        extracted_skills_count=extracted_skills_count,
        top_match_score=top_match_score,
        recommended_jobs=recommended_jobs,
        skill_gap_summary=skill_gap_summary,
        pipeline_stats=pipeline_stats,
        is_internship_seeking=is_internship_seeking if 'is_internship_seeking' in locals() else False,
    )


def compute_profile_completion(user, resume):
    """Calculate profile completion percentage and breakdown metrics."""
    score = 0
    checks = []

    # 1. Full name provided
    if user.name and user.name.strip() and user.name.strip() != "User":
        score += 15
        checks.append({"label": "Full Name", "completed": True})
    else:
        checks.append({"label": "Full Name", "completed": False})

    # 2. Email confirmed
    if user.email and user.email.strip():
        score += 15
        checks.append({"label": "Email Verified", "completed": True})
    else:
        checks.append({"label": "Email Verified", "completed": False})

    # 3. Professional Title / Role
    if user.title_role and user.title_role.strip() and user.title_role.strip() != "Job Seeker":
        score += 15
        checks.append({"label": "Target Role", "completed": True})
    else:
        checks.append({"label": "Target Role", "completed": False})

    # 4. Contact Phone
    if user.phone and user.phone.strip():
        score += 15
        checks.append({"label": "Phone Number", "completed": True})
    else:
        checks.append({"label": "Phone Number", "completed": False})

    # 5. Location
    if user.location and user.location.strip():
        score += 15
        checks.append({"label": "Location", "completed": True})
    else:
        checks.append({"label": "Location", "completed": False})

    # 6. LinkedIn or Professional URL
    if user.linkedin_url and user.linkedin_url.strip():
        score += 10
        checks.append({"label": "LinkedIn Profile", "completed": True})
    else:
        checks.append({"label": "LinkedIn Profile", "completed": False})

    # 7. Uploaded Resume
    if resume and (resume.extracted_skills or resume.extracted_text):
        score += 15
        checks.append({"label": "Resume Uploaded", "completed": True})
    else:
        checks.append({"label": "Resume Uploaded", "completed": False})

    percentage = min(score, 100)
    level = "Starter"
    if percentage >= 90:
        level = "All-Star"
    elif percentage >= 70:
        level = "Advanced"
    elif percentage >= 50:
        level = "Intermediate"

    return {
        "percentage": percentage,
        "checks": checks,
        "level": level,
        "is_complete": percentage >= 90,
    }


@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.upload_date.desc()).first()

    if request.method == "POST":
        action = request.form.get("action", "")
        target_tab = "personal"

        if action == "update_profile":
            current_user.name = request.form.get("name", current_user.name).strip()
            current_user.phone = request.form.get("phone", "").strip()
            current_user.location = request.form.get("location", "").strip()
            current_user.title_role = request.form.get("title_role", current_user.title_role).strip()
            current_user.date_of_birth = request.form.get("date_of_birth", "").strip()
            current_user.linkedin_url = request.form.get("linkedin_url", "").strip()
            db.session.commit()
            flash("Profile information updated successfully.", "success")
            target_tab = "personal"

        elif action == "sync_from_resume":
            if resume:
                structure = extract_structure(resume.extracted_text, filepath=resume.file_path)
                cand_prof = detect_candidate_profile(resume.skills or [], resume.extracted_text or "", structure.get("title_role", ""))
                role_to_use = structure.get("title_role") or cand_prof["recommended_role"]

                if structure.get("phone"):
                    current_user.phone = structure["phone"]
                if structure.get("location"):
                    current_user.location = structure["location"]
                if structure.get("linkedin_url"):
                    current_user.linkedin_url = structure["linkedin_url"]
                if role_to_use:
                    current_user.title_role = role_to_use

                pref = JobPreference.query.filter_by(user_id=current_user.id).first()
                if not pref:
                    pref = JobPreference(user_id=current_user.id)
                    db.session.add(pref)
                if role_to_use:
                    pref.target_role = role_to_use
                if structure.get("location") and (not pref.location or pref.location == "Remote"):
                    pref.location = structure["location"]

                db.session.commit()
                flash("Personal information successfully auto-filled from your uploaded resume!", "success")
            else:
                flash("No uploaded resume found to sync information from.", "warning")
            target_tab = "personal"

        elif action == "change_password":
            target_tab = "security"
            current_pass = request.form.get("current_password", "").strip()
            new_pass = request.form.get("new_password", "").strip()
            confirm_pass = request.form.get("confirm_password", "").strip()

            if not current_pass or not new_pass or not confirm_pass:
                flash("All password fields are required.", "danger")
            elif not current_user.check_password(current_pass):
                flash("Current password is incorrect. Please verify and try again.", "danger")
            elif current_pass == new_pass:
                flash("New password cannot be the same as your current password.", "danger")
            elif len(new_pass) < 8:
                flash("New password must be at least 8 characters long.", "danger")
            elif not re.search(r"[A-Z]", new_pass):
                flash("New password must contain at least one uppercase letter (A-Z).", "danger")
            elif not re.search(r"[a-z]", new_pass):
                flash("New password must contain at least one lowercase letter (a-z).", "danger")
            elif not (re.search(r"[0-9]", new_pass) or re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_pass)):
                flash("New password must contain at least one number (0-9) or special character.", "danger")
            elif new_pass != confirm_pass:
                flash("The new password and confirmation password do not match.", "danger")
            else:
                current_user.set_password(new_pass)
                db.session.commit()
                from app.services.auth_dataset import record_login_activity
                record_login_activity(
                    email=current_user.email,
                    status="SUCCESS",
                    user=current_user,
                    failure_reason="Password changed successfully by user",
                )
                flash("Password updated successfully! Your account credentials have been secured.", "success")

        elif action == "update_settings":
            current_user.language = request.form.get("language", "English")
            current_user.theme = request.form.get("theme", "Light")
            current_user.notifications_enabled = request.form.get("notifications_enabled") == "on"
            db.session.commit()
            flash("Account settings updated successfully.", "success")
            target_tab = "preferences"

        elif action == "upload_avatar":
            target_tab = "personal"
            avatar_folder = current_app.config.get("AVATAR_FOLDER") or os.path.join(
                current_app.config["UPLOAD_FOLDER"], "avatars"
            )
            os.makedirs(avatar_folder, exist_ok=True)

            cropped_data = request.form.get("avatar_cropped_data", "").strip()
            avatar_file = request.files.get("avatar_file")

            try:
                img = None
                file_ext = "png"

                if cropped_data:
                    data_match = re.match(r"^data:image\/(png|jpeg|jpg|webp);base64,(.+)$", cropped_data, re.IGNORECASE)
                    if not data_match:
                        flash("Invalid image payload. Please select a valid photo.", "danger")
                    else:
                        img_format = data_match.group(1).lower()
                        raw_bytes = base64.b64decode(data_match.group(2))
                        if len(raw_bytes) > MAX_AVATAR_SIZE_BYTES:
                            flash("Image size exceeds the 5MB limit. Please choose a smaller photo.", "danger")
                        else:
                            img = Image.open(io.BytesIO(raw_bytes))
                            file_ext = "jpg" if img_format in ("jpeg", "jpg") else "png"

                elif avatar_file and avatar_file.filename:
                    if not _allowed_avatar(avatar_file.filename):
                        flash("Invalid file format. Allowed formats: JPG, JPEG, PNG, WEBP.", "danger")
                    else:
                        file_bytes = avatar_file.read()
                        if len(file_bytes) > MAX_AVATAR_SIZE_BYTES:
                            flash("Image size exceeds the 5MB limit. Please choose a smaller file.", "danger")
                        else:
                            img = Image.open(io.BytesIO(file_bytes))
                            # Center crop to square
                            w, h = img.size
                            min_dim = min(w, h)
                            left = (w - min_dim) // 2
                            top = (h - min_dim) // 2
                            img = img.crop((left, top, left + min_dim, top + min_dim))
                            ext = avatar_file.filename.rsplit(".", 1)[1].lower()
                            file_ext = "jpg" if ext in ("jpg", "jpeg") else "png"
                else:
                    flash("Please select an image file to upload.", "warning")

                if img is not None:
                    # Clean resize to square 400x400
                    img = img.resize((400, 400), Image.Resampling.LANCZOS)
                    new_filename = f"avatar_{current_user.id}_{int(time.time())}.{file_ext}"
                    dest_path = os.path.join(avatar_folder, new_filename)

                    buffered = io.BytesIO()
                    if file_ext == "png":
                        if img.mode not in ("RGBA", "RGB"):
                            img = img.convert("RGBA")
                        img.save(dest_path, "PNG", optimize=True)
                        img.save(buffered, format="PNG", optimize=True)
                        mime_type = "image/png"
                    else:
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        img.save(dest_path, "JPEG", quality=90, optimize=True)
                        img.save(buffered, format="JPEG", quality=90, optimize=True)
                        mime_type = "image/jpeg"

                    b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    data_uri = f"data:{mime_type};base64,{b64_str}"

                    # Delete previous avatar if any
                    if current_user.profile_image:
                        old_path = os.path.join(avatar_folder, os.path.basename(current_user.profile_image))
                        if os.path.exists(old_path) and os.path.abspath(old_path) != os.path.abspath(dest_path):
                            try:
                                os.remove(old_path)
                            except Exception:
                                pass

                    current_user.profile_image = new_filename
                    current_user.avatar_data = data_uri
                    db.session.commit()
                    flash("Profile picture updated successfully!", "success")

            except Exception as e:
                current_app.logger.error(f"Avatar processing failed: {e}")
                flash("Could not process image. Please upload a valid JPG, PNG, or WEBP file.", "danger")

        elif action == "remove_avatar":
            target_tab = "personal"
            avatar_folder = current_app.config.get("AVATAR_FOLDER") or os.path.join(
                current_app.config["UPLOAD_FOLDER"], "avatars"
            )
            if current_user.profile_image:
                old_path = os.path.join(avatar_folder, os.path.basename(current_user.profile_image))
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass
                current_user.profile_image = ""
                current_user.avatar_data = ""
                db.session.commit()
                flash("Profile picture removed successfully. Default avatar restored.", "success")
            else:
                flash("No profile picture to remove.", "info")

        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({
                "success": True,
                "profile_image": current_user.profile_image or "",
                "avatar_url": current_user.avatar_url,
                "name": current_user.name,
            })

        return redirect(url_for("main.profile") + f"#{target_tab}")

    # Auto-sync empty fields from resume on GET if a resume exists
    if resume:
        needs_commit = False
        structure = extract_structure(resume.extracted_text, filepath=resume.file_path)
        if not current_user.phone and structure.get("phone"):
            current_user.phone = structure["phone"]
            needs_commit = True
        if not current_user.location and structure.get("location"):
            current_user.location = structure["location"]
            needs_commit = True
        if not current_user.linkedin_url and structure.get("linkedin_url"):
            current_user.linkedin_url = structure["linkedin_url"]
            needs_commit = True
        if not current_user.title_role or current_user.title_role == "Job Seeker":
            cand_prof = detect_candidate_profile(resume.skills or [], resume.extracted_text or "", structure.get("title_role", ""))
            current_user.title_role = structure.get("title_role") or cand_prof["recommended_role"]
            needs_commit = True
        if needs_commit:
            pref = JobPreference.query.filter_by(user_id=current_user.id).first()
            if not pref:
                pref = JobPreference(user_id=current_user.id)
                db.session.add(pref)
            if current_user.title_role:
                pref.target_role = current_user.title_role
            if structure.get("location") and (not pref.location or pref.location == "Remote"):
                pref.location = structure["location"]
            db.session.commit()

    completion = compute_profile_completion(current_user, resume)
    return render_template("profile.html", resume=resume, completion=completion)
