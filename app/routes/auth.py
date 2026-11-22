from datetime import datetime
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for, Response
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import LoginHistory, User, utc_now
from app.services.auth_dataset import (
    build_auth_hashmap,
    get_auth_dataset_summary,
    get_client_ip,
    get_client_user_agent,
    record_login_activity,
    sync_auth_dataset_file,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required")
            return redirect(url_for("auth.register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters long")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists")
            return redirect(url_for("auth.register"))

        user = User(
            name=name,
            email=email,
            created_at=utc_now(),
            status="active",
        )
        # Hash password securely using werkzeug (scrypt/pbkdf2 hashmap)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Record registration in authentication dataset & audit history
        record_login_activity(
            email=email,
            status="SUCCESS",
            user=user,
            failure_reason="Account registration created",
        )

        login_user(user, remember=True)
        from flask import session
        session.permanent = True

        flash("Account created successfully! Welcome to JobSnap.")
        response = redirect(url_for("main.dashboard"))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    return render_template("auth/register.html", is_auth_page=True)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        from sqlalchemy import func
        identifier = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        # Support sign-in by registered Email OR Username/Name (case-insensitive)
        user = User.query.filter(
            (func.lower(User.email) == identifier.lower()) |
            (func.lower(User.name) == identifier.lower())
        ).first()

        # Verify password (including whitespace-tolerant check for copy-paste safety)
        password_valid = False
        if user:
            if user.check_password(password):
                password_valid = True
            elif password != password.strip() and user.check_password(password.strip()):
                password_valid = True

        if user and password_valid:
            # Record successful login date and client details
            record_login_activity(
                email=user.email,
                status="SUCCESS",
                user=user,
                failure_reason="",
            )
            login_user(user, remember=True)
            from flask import session
            session.permanent = True

            next_page = request.args.get("next")
            redirect_target = next_page if (next_page and next_page.startswith("/") and not next_page.startswith("//")) else url_for("main.dashboard")
            response = redirect(redirect_target)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            return response

        # Record failed login attempt in dataset for security auditing
        reason = "Invalid password" if user else "Account not registered"
        record_login_activity(
            email=user.email if user else identifier,
            status="FAILED",
            user=user,
            failure_reason=reason,
        )

        if not user:
            flash("No account registered with this email or username. Please click 'Create an account' below to sign up.")
        else:
            flash("Incorrect password. Please verify your password and try again.")

    return render_template("auth/login.html", is_auth_page=True)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@auth_bp.route("/activity")
@login_required
def activity():
    """View personal login activity history with dates, IP, and status."""
    logs = (
        LoginHistory.query.filter_by(user_id=current_user.id)
        .order_by(LoginHistory.timestamp.desc())
        .limit(50)
        .all()
    )
    return render_template("auth/activity.html", logs=logs)


@auth_bp.route("/export-my-data")
@login_required
def export_my_data():
    """Download the authenticated user's complete profile, resumes, career preferences, saved jobs, and activity records."""
    import json
    pref = current_user.job_preference
    data = {
        "export_metadata": {
            "service": "JobSnap AI Resume Analyzer & Intelligent Job Finder",
            "exported_at": utc_now().isoformat(),
            "data_owner_id": current_user.id,
            "email": current_user.email,
        },
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone or "",
        "location": current_user.location or "",
        "country": current_user.country or "",
        "title_role": current_user.title_role or "",
        "linkedin_url": current_user.linkedin_url or "",
        "account_created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login_at": current_user.last_login.isoformat() if current_user.last_login else None,
        "total_logins": current_user.login_count or 1,
        "job_preferences": pref.to_dict() if pref else None,
        "resumes": [r.to_dict() for r in (current_user.resumes or [])],
        "saved_jobs": [j.to_dict() for j in (current_user.saved_jobs or [])],
        "login_activity": [
            {
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "status": log.status,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
            }
            for log in (current_user.login_history or [])[:20]
        ],
    }
    return Response(
        json.dumps(data, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=my_jobsnap_data_{current_user.id}.json"},
    )


@auth_bp.route("/dataset")
@login_required
def dataset_view():
    """
    Returns the user authentication dataset structured as a hashmap
    indexed by email.
    - Regular users are strictly scoped to their own personal account.
    - Administrators (status='admin' or in ADMIN_EMAILS) see the global dataset.
    - Sensitive password hashes and exact IP logs are scrubbed for privacy.
    """
    scope_user = None if current_user.is_admin else current_user
    hashmap = build_auth_hashmap(user=scope_user, include_sensitive=False)
    summary = get_auth_dataset_summary(user=scope_user)
    is_admin = current_user.is_admin

    # If JSON requested via query arg e.g. /dataset?format=json
    if request.args.get("format") == "json":
        return jsonify({
            "scope": "global" if is_admin else "personal",
            "is_admin": is_admin,
            "summary": summary,
            "users_hashmap": hashmap,
        })

    return render_template(
        "auth/dataset_view.html",
        hashmap=hashmap,
        summary=summary,
        is_admin_view=is_admin,
    )


@auth_bp.route("/export-dataset")
@login_required
def export_dataset():
    """
    Download authentication dataset as JSON with password hashes scrubbed.
    - Regular users receive only their own sanitized account activity record.
    - Administrators receive aggregated dataset with credentials protected.
    """
    import json
    scope_user = None if current_user.is_admin else current_user
    hashmap = build_auth_hashmap(user=scope_user, include_sensitive=False)
    summary = get_auth_dataset_summary(user=scope_user)
    is_admin = current_user.is_admin

    data = {
        "dataset_name": "JobSnap User Authentication & Login History Dataset",
        "scope": "global_administrative" if is_admin else "personal_authenticated",
        "description": "User account metadata, signup dates, and login activity records (credentials cryptographically protected)",
        "exported_at": utc_now().isoformat(),
        "summary": summary,
        "users_hashmap": hashmap,
    }
    response_json = json.dumps(data, indent=2)
    filename = "users_auth_dataset.json" if is_admin else f"my_auth_dataset_{current_user.id}.json"
    return Response(
        response_json,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename={filename}"},
    )
