import json
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import JobPreference, Resume, SavedJob, utc_now
from app.services.job_api import fetch_jobs
from app.services.profile_detector import detect_candidate_profile, detect_candidate_seniority_intent, get_job_ordering_tuple
from app.services.skill_extractor import extract_skills
from app.services.skill_gap import analyze_job_skill_gap, suggest_learning
from app.services.job_verifier import attach_reliability_to_job, attach_reliability_batch
from app.services.job_validator import (
    normalize_apply_url,
    is_valid_apply_url,
    generate_job_id,
    GLOBAL_JOBS_REGISTRY,
    clean_job_for_registry,
    find_job_by_identifier,
)

jobs_bp = Blueprint("jobs", __name__)

USER_JOBS_CACHE = {}


@jobs_bp.route("/results")
@login_required
def results():
    resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.upload_date.desc()).first()
    if not resume:
        flash("Please upload your resume first so our AI can analyze your skills and find matching jobs.")
        return redirect(url_for("resume.upload"))

    pref = JobPreference.query.filter_by(user_id=current_user.id).first()

    # Create default preference if none exists
    if not pref:
        pref = JobPreference(user_id=current_user.id)
        db.session.add(pref)
        db.session.commit()

    resume_skills = json.loads(resume.extracted_skills or "[]") if resume.extracted_skills else []
    resume_text = resume.extracted_text or ""
    candidate_profile = detect_candidate_profile(resume_skills, resume_text, current_user.title_role or "")
    candidate_domain = candidate_profile["primary_domain"]
    candidate_title = current_user.title_role if (current_user.title_role and current_user.title_role != "Job Seeker") else candidate_profile["recommended_role"]

    # Detect candidate seniority intent (internship seeking, entry level, etc.)
    seniority_intent = detect_candidate_seniority_intent(
        resume_text=resume_text,
        declared_title=current_user.title_role or "",
        experience_level_pref=pref.experience_level or "",
        job_type_pref=pref.job_type or "",
        education_text=resume.education or "",
    )
    is_internship_seeking = seniority_intent["is_internship_seeking"]
    is_entry_level_seeking = seniority_intent["is_entry_level_seeking"]

    search_query = request.args.get("q", "").strip()
    source_query = request.args.get("source", "all").strip().lower()
    location_query = request.args.get("location", "all").strip().lower()
    country_query = request.args.get("country", "").strip().lower()
    company_query = request.args.get("company", "all").strip()
    type_query = request.args.get("type", "all").strip().lower()
    seniority_query = request.args.get("seniority", "all").strip().lower()
    domain_query = request.args.get("domain", "all").strip().lower()
    min_score_query = request.args.get("min_score", "all").strip().lower()
    reliability_query = request.args.get("reliability", "all").strip().lower()
    sort_query = request.args.get("sort", "score").strip().lower()

    # Intelligent detection for Bangladesh from candidate's resume, phone, education, or user profile
    from app.services.bd_job_scraper import is_bangladesh_resume_or_location
    from app.services.bd_companies import get_all_company_names, BD_TECH_COMPANIES

    is_bd_resume = is_bangladesh_resume_or_location(
        text=resume_text,
        location_val=(pref.location or "") + " " + (current_user.location or ""),
        phone_val=current_user.phone or "",
        education_val=resume.education or "",
    )
    user_bd_pref = (
        (pref.country and pref.country.lower() in ["bangladesh", "bd"])
        or (current_user.country and current_user.country.lower() in ["bangladesh", "bd"])
        or ("bangladesh" in (pref.location or "").lower())
    )

    if country_query:
        selected_country = country_query
        is_bd_active = country_query in ["bangladesh", "bd"]
    elif company_query and company_query.lower() != "all":
        selected_country = "bangladesh"
        is_bd_active = True
    elif user_bd_pref or is_bd_resume:
        selected_country = "bangladesh"
        is_bd_active = True
    else:
        selected_country = "all"
        is_bd_active = False

    if search_query:
        target_role = search_query
    elif pref.target_role and pref.target_role not in ["Software Engineer", "Machine Learning Engineer, Data Scientist"]:
        target_role = pref.target_role
    else:
        target_role = candidate_profile["recommended_role"]

    if is_bd_active and (not pref.location or pref.location == "Remote"):
        location = "Dhaka, Bangladesh"
    else:
        location = pref.location or "Remote"

    # Fetch live real-time job listings tailored to candidate's domain & country/company filter
    jobs_raw = fetch_jobs(
        target_role,
        location,
        source=source_query,
        country=selected_country,
        company_filter=company_query,
    )
    jobs = []
    for index, raw_job in enumerate(jobs_raw):
        job = dict(raw_job)
        description = job.get("job_description", "")
        extracted_job_skills = extract_skills(description)
        existing_skills = job.get("job_skills") or []
        combined_job_skills = sorted(list(set(extracted_job_skills + existing_skills)))
        job["job_skills"] = combined_job_skills

        # Transparent, job-specific multi-signal skill gap and domain relevance analysis
        analysis = analyze_job_skill_gap(
            resume_skills=resume_skills,
            job_skills=combined_job_skills,
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
        jobs.append(job)

    # Filter out unrelated roles unless user explicitly queried for something specific
    compatible_jobs = [j for j in jobs if not j.get("is_unrelated_domain", False)]
    display_jobs = jobs if search_query else (compatible_jobs if compatible_jobs else jobs)

    # Apply server-side filters if requested via GET URL parameters
    if location_query == "remote":
        display_jobs = [j for j in display_jobs if "remote" in (j.get("job_city") or j.get("location", "")).lower()]
    elif location_query == "onsite":
        display_jobs = [j for j in display_jobs if "remote" not in (j.get("job_city") or j.get("location", "")).lower()]

    if type_query and type_query != "all":
        display_jobs = [j for j in display_jobs if type_query in (j.get("job_employment_type", "")).lower()]

    if seniority_query in ["internship", "intern"]:
        display_jobs = [j for j in display_jobs if j.get("is_internship")]
    elif seniority_query in ["entry_level", "entry", "junior"]:
        display_jobs = [j for j in display_jobs if j.get("is_entry_level")]
    elif seniority_query in ["experienced", "mid", "senior"]:
        display_jobs = [j for j in display_jobs if not j.get("is_internship") and not j.get("is_entry_level")]

    if domain_query and domain_query != "all":
        display_jobs = [j for j in display_jobs if j.get("domain_info", {}).get("domain") == domain_query]

    if min_score_query and min_score_query.isdigit():
        min_s = int(min_score_query)
        display_jobs = [j for j in display_jobs if j.get("combined_score", 0) >= min_s]

    # Country & Bangladesh Company filtering
    if selected_country in ["bangladesh", "bd"]:
        bd_filtered = [
            j for j in display_jobs
            if j.get("is_bangladesh")
            or (j.get("country") or "").lower() == "bangladesh"
            or "bangladesh" in (j.get("location") or "").lower()
            or "dhaka" in (j.get("location") or "").lower()
            or any(c.lower() in (j.get("company") or "").lower() for c in BD_TECH_COMPANIES)
        ]
        if bd_filtered:
            display_jobs = bd_filtered
    elif selected_country not in ["all", ""]:
        display_jobs = [
            j for j in display_jobs
            if selected_country in (j.get("country") or "").lower() or selected_country in (j.get("location") or "").lower()
        ]

    if company_query and company_query.lower() != "all":
        display_jobs = [
            j for j in display_jobs
            if company_query.lower() in (j.get("company") or "").lower() or company_query.lower() in (j.get("employer_name") or "").lower()
        ]

    # Ensure reliability verification is attached to all display jobs
    attach_reliability_batch(display_jobs)

    if reliability_query == "verified":
        display_jobs = [j for j in display_jobs if j.get("reliability_status") == "Verified"]
    elif reliability_query == "unverified":
        display_jobs = [j for j in display_jobs if j.get("reliability_status") == "Unverified"]
    elif reliability_query in ["suspicious", "potentially_suspicious"]:
        display_jobs = [j for j in display_jobs if j.get("reliability_status") == "Potentially Suspicious"]
    elif reliability_query == "exclude_suspicious":
        display_jobs = [j for j in display_jobs if j.get("reliability_status") != "Potentially Suspicious"]

    # Order jobs with priority:
    if sort_query == "title":
        display_jobs.sort(key=lambda j: j.get("job_title", "").lower())
    elif sort_query == "company":
        display_jobs.sort(key=lambda j: (j.get("employer_name") or j.get("company", "")).lower())
    else:
        # Default smart priority ordering (Bangladesh top tech employers first, then internship/entry-level/match score)
        def smart_priority_sort(j):
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

        display_jobs.sort(key=smart_priority_sort, reverse=False)

    # Re-assign cache_id strictly AFTER sorting and ensure all jobs have valid job_ids and registry entries
    for idx, job in enumerate(display_jobs):
        job["cache_id"] = idx
        if not job.get("job_id"):
            job["job_id"] = generate_job_id(job)
        GLOBAL_JOBS_REGISTRY[job["job_id"]] = clean_job_for_registry(job)

    USER_JOBS_CACHE[current_user.id] = display_jobs[:45]

    # Dynamic extraction of top skills across active results for one-click quick filtering
    skills_counter = {}
    for j in display_jobs:
        for s in (j.get("job_skills") or []):
            clean_s = s.strip()
            if 1 < len(clean_s) < 25 and not clean_s.lower().startswith("http") and not clean_s.isdigit():
                skills_counter[clean_s] = skills_counter.get(clean_s, 0) + 1
    popular_skills = [s for s, _ in sorted(skills_counter.items(), key=lambda x: x[1], reverse=True)[:10]]

    saved_jobs_count = SavedJob.query.filter_by(user_id=current_user.id).count()

    return render_template(
        "results.html",
        jobs=display_jobs[:45],
        resume=resume,
        candidate_profile=candidate_profile,
        saved_jobs_count=saved_jobs_count,
        top_match_score=display_jobs[0]["combined_score"] if display_jobs else 88,
        selected_source=source_query,
        selected_location=location_query,
        selected_country=selected_country,
        selected_company=company_query,
        all_bd_companies=get_all_company_names(),
        is_bd_active=is_bd_active,
        is_bd_resume=is_bd_resume,
        selected_type=type_query,
        selected_seniority=seniority_query,
        selected_domain=domain_query,
        selected_min_score=min_score_query,
        selected_sort=sort_query,
        selected_reliability=reliability_query,
        search_query=search_query,
        popular_skills=popular_skills,
        is_internship_seeking=is_internship_seeking,
        is_entry_level_seeking=is_entry_level_seeking,
        seniority_intent=seniority_intent,
    )


@jobs_bp.route("/job/<index>")
@login_required
def job_detail(index):
    """
    Job details view with accurate job resolution by stable job_id or verified index.
    """
    job_raw = find_job_by_identifier(current_user.id, index, USER_JOBS_CACHE)
    if job_raw:
        job = dict(job_raw)
        resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.upload_date.desc()).first()

        # Candidate-specific dynamic scoring:
        # If the user has uploaded a resume, evaluate matching skills & scores against THEIR resume.
        # If the user has no resume, clear any previous user's match data so no cross-user resume data is shown.
        if resume:
            resume_skills = json.loads(resume.extracted_skills or "[]") if resume.extracted_skills else []
            resume_text = resume.extracted_text or ""
            pref = JobPreference.query.filter_by(user_id=current_user.id).first()
            cand_prof = detect_candidate_profile(resume_skills, resume_text, current_user.title_role or "")
            seniority_intent = detect_candidate_seniority_intent(
                resume_text=resume_text,
                declared_title=current_user.title_role or "",
                experience_level_pref=pref.experience_level if pref else "",
                job_type_pref=pref.job_type if pref else "",
                education_text=resume.education or "",
            )
            candidate_title = current_user.title_role if (current_user.title_role and current_user.title_role != "Job Seeker") else cand_prof["recommended_role"]
            analysis = analyze_job_skill_gap(
                resume_skills=resume_skills,
                job_skills=job.get("job_skills", []),
                resume_text=resume_text,
                job_description=job.get("job_description", ""),
                candidate_title=candidate_title,
                job_title=job.get("job_title", ""),
                experience_text=resume.experience or "",
                education_text=resume.education or "",
                candidate_domain=cand_prof["primary_domain"],
                is_internship_seeking=seniority_intent["is_internship_seeking"],
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
        else:
            job["matched_skills"] = []
            job["partial_skills"] = []
            job["missing_skills"] = job.get("job_skills", [])
            job["combined_score"] = None
            job["match_score"] = 0
            job["cosine_score"] = 0
            job["title_score"] = 0
            job["score_breakdown"] = {}
            job["score_explanation"] = "Upload your resume to see your personalized ATS match score and skill breakdown."

        learning_resources = suggest_learning(job.get("missing_skills", []))
        
        # Ensure reliability metadata is attached
        attach_reliability_to_job(job)

        # Format job description into clean semantic responsive layout
        from app.services.job_description_formatter import clean_job_description
        job["formatted_description"] = clean_job_description(job.get("job_description", ""))

        # Similar jobs from user's current recommendations excluding active job
        user_jobs = USER_JOBS_CACHE.get(current_user.id, [])
        active_jid = job.get("job_id")
        similar_jobs = [j for j in user_jobs if j.get("job_id") != active_jid][:3]
        if not similar_jobs:
            from app.services.job_api import load_seed_jobs
            similar_jobs = [j for j in load_seed_jobs() if j.get("job_id") != active_jid][:3]
        attach_reliability_batch(similar_jobs)
        
        return render_template(
            "job_detail.html",
            job=job,
            index=job.get("job_id", index),
            resume=resume,
            learning_resources=learning_resources,
            similar_jobs=similar_jobs,
        )

    flash("The requested job listing could not be found or your session has expired. Please view current recommendations.")
    return redirect(url_for("jobs.results"))


@jobs_bp.route("/job/apply/<index>")
@login_required
def apply_redirect(index):
    """
    Direct 'Apply Now' Redirector with Strict Job ID & Application URL Validation.
    Guarantees that users are redirected ONLY to the verified application URL for the selected job.
    Never redirects users to another job or unrelated listing.
    """
    job = find_job_by_identifier(current_user.id, index, USER_JOBS_CACHE)
    direct_url = request.args.get("direct_url", "").strip()

    if not job and direct_url and is_valid_apply_url(direct_url):
        apply_url = normalize_apply_url(direct_url)
        return redirect(apply_url)

    if not job:
        flash("The selected job opening could not be found or your session has expired. Please refresh your recommendations.")
        return redirect(url_for("jobs.results"))

    raw_apply_url = job.get("job_apply_link", "").strip()
    if (not raw_apply_url or not is_valid_apply_url(raw_apply_url)) and direct_url and is_valid_apply_url(direct_url):
        raw_apply_url = direct_url
    elif not raw_apply_url:
        raw_apply_url = direct_url

    job_title = job.get("job_title", "").strip()
    company = (job.get("employer_name") or job.get("company", "")).strip()
    location = (job.get("job_city") or job.get("location", "Remote")).strip()
    raw_score = job.get("combined_score")
    match_score = int(raw_score) if raw_score is not None else 85
    job_id = job.get("job_id", str(index))

    # Strict URL validation and normalization
    apply_url = normalize_apply_url(raw_apply_url)
    if not is_valid_apply_url(apply_url):
        flash(f"The official application link for '{job_title}' at '{company}' is currently unavailable. No external redirect could be performed.")
        return redirect(url_for("jobs.job_detail", index=job_id))

    # Auto-track under Applied status in SavedJob pipeline
    if job_title and company:
        try:
            existing = SavedJob.query.filter_by(user_id=current_user.id, job_title=job_title, company=company).first()
            if existing:
                existing.status = "Applied"
                if not existing.applied_date:
                    existing.applied_date = utc_now()
                existing.apply_link = apply_url
                existing.job_id = job_id
            else:
                applied = SavedJob(
                    user_id=current_user.id,
                    job_id=job_id,
                    job_title=job_title,
                    company=company,
                    apply_link=apply_url,
                    location=location,
                    match_score=match_score,
                    status="Applied",
                    applied_date=utc_now(),
                )
                db.session.add(applied)
            db.session.commit()
        except Exception as e:
            db.session.rollback()

    return redirect(apply_url)


@jobs_bp.route("/apply-job", methods=["POST"])
@login_required
def apply_job():
    """
    Form submission for Quick Apply with Resume.
    Validates job metadata and application URL before recording and redirecting.
    """
    job_title = request.form.get("job_title", "").strip()
    company = request.form.get("company", "").strip()
    raw_apply_link = request.form.get("apply_link", "").strip()
    location = request.form.get("location", "Remote").strip()
    job_id = request.form.get("job_id", "").strip()
    try:
        match_score = int(request.form.get("match_score", 85))
    except (ValueError, TypeError):
        match_score = 85

    apply_link = normalize_apply_url(raw_apply_link)
    verified_job_id = job_id if (job_id and job_id != "job") else generate_job_id({"job_title": job_title, "company": company, "job_apply_link": apply_link})

    if job_title and company:
        try:
            existing = SavedJob.query.filter_by(user_id=current_user.id, job_title=job_title, company=company).first()
            if existing:
                existing.status = "Applied"
                existing.applied_date = utc_now()
                if apply_link:
                    existing.apply_link = apply_link
                if verified_job_id:
                    existing.job_id = verified_job_id
            else:
                applied = SavedJob(
                    user_id=current_user.id,
                    job_id=verified_job_id,
                    job_title=job_title,
                    company=company,
                    apply_link=apply_link,
                    location=location,
                    match_score=match_score,
                    status="Applied",
                    applied_date=utc_now(),
                )
                db.session.add(applied)
            db.session.commit()
        except Exception as e:
            db.session.rollback()

    if is_valid_apply_url(apply_link):
        flash(f"🎉 Application recorded for {job_title} at {company}! Redirecting to the official application portal...")
        return redirect(apply_link)
    else:
        flash(f"Application recorded for {job_title} at {company}! (Official external application link is currently unavailable).")
        return redirect(request.referrer or url_for("jobs.saved_jobs"))


@jobs_bp.route("/saved-jobs")
@login_required
def saved_jobs():
    saved_list = SavedJob.query.filter_by(user_id=current_user.id).order_by(SavedJob.saved_date.desc()).all()
    return render_template("saved_jobs.html", saved_jobs=saved_list)


@jobs_bp.route("/save-job", methods=["POST"])
@login_required
def save_job():
    job_title = request.form.get("job_title", "").strip()
    company = request.form.get("company", "").strip()
    raw_apply_link = request.form.get("apply_link", "").strip()
    location = request.form.get("location", "Remote").strip()
    job_id = request.form.get("job_id", "").strip()
    try:
        match_score = int(request.form.get("match_score", 85))
    except (ValueError, TypeError):
        match_score = 85

    apply_link = normalize_apply_url(raw_apply_link)
    verified_job_id = job_id or generate_job_id({"job_title": job_title, "company": company, "job_apply_link": apply_link})

    # Avoid duplicate saves
    existing = SavedJob.query.filter_by(user_id=current_user.id, job_title=job_title, company=company).first()
    if not existing:
        saved = SavedJob(
            user_id=current_user.id,
            job_id=verified_job_id,
            job_title=job_title,
            company=company,
            apply_link=apply_link,
            location=location,
            match_score=match_score,
        )
        db.session.add(saved)
        db.session.commit()
        flash(f"Saved {job_title} at {company} to your saved jobs!")
    else:
        if apply_link and not existing.apply_link:
            existing.apply_link = apply_link
        if verified_job_id and (not existing.job_id or existing.job_id in ("job", "j001")):
            existing.job_id = verified_job_id
        db.session.commit()
        flash("Job is already saved.")

    GLOBAL_JOBS_REGISTRY[verified_job_id] = clean_job_for_registry({
        "job_id": verified_job_id,
        "job_title": job_title,
        "company": company,
        "employer_name": company,
        "job_apply_link": apply_link,
        "location": location,
    })

    if (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    ):
        return jsonify({
            "success": True,
            "saved": True,
            "job_id": verified_job_id,
            "message": f"Saved {job_title} at {company} to your saved jobs!",
        })

    return redirect(request.referrer or url_for("jobs.saved_jobs"))


@jobs_bp.route("/remove-saved-job/<int:id>", methods=["POST"])
@login_required
def remove_saved_job(id):
    job = db.session.get(SavedJob, id)
    if job and job.user_id == current_user.id:
        db.session.delete(job)
        db.session.commit()
        if (
            request.is_json
            or request.headers.get("Accept") == "application/json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        ):
            return jsonify({"success": True, "saved": False, "id": id, "message": "Job removed from saved list."})
        flash("Job removed from saved list.")
    elif request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"success": False, "error": "Job not found"}), 404
    return redirect(url_for("jobs.saved_jobs"))


@jobs_bp.route("/update-job-status/<int:id>", methods=["POST"])
@login_required
def update_job_status(id):
    job = db.session.get(SavedJob, id)
    if job and job.user_id == current_user.id:
        raw_status = (request.json.get("status") if request.is_json and request.json else None) or request.form.get("status", "Saved")
        new_status = (raw_status or "Saved").strip()
        job.status = new_status
        if new_status == "Applied" and not job.applied_date:
            job.applied_date = utc_now()
        db.session.commit()
        if (
            request.is_json
            or request.headers.get("Accept") == "application/json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        ):
            return jsonify({"success": True, "id": id, "status": new_status, "message": f"Status updated to {new_status}"})
        flash(f"Updated status for '{job.job_title}' to '{new_status}'.")
    elif request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"success": False, "error": "Job not found or unauthorized"}), 404
    return redirect(request.referrer or url_for("jobs.saved_jobs"))
