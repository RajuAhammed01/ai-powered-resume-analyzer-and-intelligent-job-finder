#!/usr/bin/env python3
"""
Supabase PostgreSQL Migration and Seeding Utility for JobSnap
Project: oihepjwiogxmpoxsdhti

Features:
- Validates Supabase connection (Direct 5432 session pooler for DDL, 6543 transaction pooler for runtime)
- Runs table schema migrations (db.create_all())
- Seeds demo candidate user, preferences, and verified company saved jobs
- Verifies record integrity and outputs summary
"""

import argparse
import os
import sys

# Ensure workspace root is in path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))


def normalize_pg_url(url: str) -> str:
    """Ensure SQLAlchemy uses pure-Python pg8000 driver without conflicting query params."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)
    if "postgresql+pg8000://" in url:
        url = url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
    return url


def run_migration_and_seed(db_url: str):
    db_url = normalize_pg_url(db_url)
    print(f"[*] Target Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    from flask import Flask
    from app.extensions import db
    from app.models import User, Resume, SavedJob, JobPreference, LoginHistory, utc_now
    from sqlalchemy.pool import NullPool
    from sqlalchemy import text, inspect

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"poolclass": NullPool}
    db.init_app(app)

    with app.app_context():
        # 1. Connection check
        print("[*] Testing connection to Supabase...")
        try:
            result = db.session.execute(text("SELECT version();")).scalar()
            print(f"[+] Connected successfully! PostgreSQL Engine: {result[:40]}...")
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return False

        # 2. Schema Migration: Create tables
        print("[*] Running schema migrations (creating tables)...")
        try:
            db.create_all()
            # Idempotent column check for "user" table (PostgreSQL reserved keyword quoted)
            try:
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS profile_image VARCHAR(255) DEFAULT \'\''))
                db.session.commit()
            except Exception:
                db.session.rollback()

            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"[+] Tables verified in Supabase: {', '.join(tables)}")
        except Exception as e:
            print(f"[!] Migration failed: {e}")
            db.session.rollback()
            return False

        # 3. Seed demo candidate user
        print("[*] Checking / seeding demo user data...")
        demo_email = "demo@jobsnap.com"
        demo_user = User.query.filter_by(email=demo_email).first()
        if not demo_user:
            demo_user = User(
                name="Demo Candidate",
                email=demo_email,
                phone="+8801712345678",
                location="Dhaka, Bangladesh",
                country="Bangladesh",
                title_role="Full Stack Engineer",
                status="active",
                created_at=utc_now(),
            )
            demo_user.set_password("DemoPassword123!")
            db.session.add(demo_user)
            db.session.commit()
            print(f"[+] Created demo user: {demo_email} (password: DemoPassword123!)")
        else:
            print(f"[i] Demo user {demo_email} already exists (id={demo_user.id}).")

        # 4. Seed user job preferences
        pref = JobPreference.query.filter_by(user_id=demo_user.id).first()
        if not pref:
            pref = JobPreference(
                user_id=demo_user.id,
                target_role="Full Stack Engineer",
                location="Remote / Hybrid",
                country="Bangladesh",
                experience_level="Mid Level",
                expected_salary="$25,000 - $40,000 / yr",
                job_type="Full-time",
                preferred_skills='["Python", "Flask", "React", "PostgreSQL", "Docker", "REST APIs", "AWS"]',
            )
            db.session.add(pref)
            db.session.commit()
            print("[+] Seeded job preferences for demo user.")

        # 5. Seed sample saved jobs (from verified Bangladesh tech firms)
        existing_saved = SavedJob.query.filter_by(user_id=demo_user.id).count()
        if existing_saved == 0:
            sample_jobs = [
                SavedJob(
                    user_id=demo_user.id,
                    job_id="bs23_py_01",
                    job_title="Senior Python / Cloud Solutions Engineer",
                    company="Brain Station 23",
                    location="Dhaka, Bangladesh / Hybrid",
                    employment_type="Full-time",
                    match_score=94,
                    matched_skills='["Python", "Flask", "PostgreSQL", "Docker", "AWS"]',
                    missing_skills='["Kubernetes"]',
                    apply_link="https://brainstation-23.com/career/",
                    status="Saved",
                ),
                SavedJob(
                    user_id=demo_user.id,
                    job_id="bjit_fs_02",
                    job_title="Full Stack Software Engineer (Python/React)",
                    company="BJIT Group",
                    location="Dhaka, Bangladesh",
                    employment_type="Full-time",
                    match_score=91,
                    matched_skills='["Python", "React", "PostgreSQL", "REST APIs"]',
                    missing_skills='["TypeScript"]',
                    apply_link="https://bjitgroup.com/career",
                    status="Saved",
                ),
                SavedJob(
                    user_id=demo_user.id,
                    job_id="pathao_be_03",
                    job_title="Backend Platform Engineer",
                    company="Pathao",
                    location="Dhaka, Bangladesh",
                    employment_type="Full-time",
                    match_score=88,
                    matched_skills='["Python", "PostgreSQL", "Docker", "REST APIs"]',
                    missing_skills='["Kafka", "Go"]',
                    apply_link="https://pathao.com/careers/",
                    status="Applied",
                    applied_date=utc_now(),
                ),
            ]
            db.session.add_all(sample_jobs)
            db.session.commit()
            print(f"[+] Seeded {len(sample_jobs)} sample saved jobs for verified companies.")

        # 6. Seed login history audit entry
        history_entry = LoginHistory(
            user_id=demo_user.id,
            email=demo_email,
            status="SUCCESS",
            ip_address="127.0.0.1",
            user_agent="JobSnap Migration Seeder/1.0",
            failure_reason="Initial seed login audit",
            timestamp=utc_now(),
        )
        db.session.add(history_entry)
        db.session.commit()
        print("[+] Seeded initial login audit record.")

        # 7. Print summary statistics
        total_users = User.query.count()
        total_jobs = SavedJob.query.count()
        total_prefs = JobPreference.query.count()
        total_history = LoginHistory.query.count()

        print("\n" + "=" * 50)
        print("    SUPABASE MIGRATION & SEED SUMMARY")
        print("=" * 50)
        print(f"  Total Registered Users    : {total_users}")
        print(f"  Total Job Preferences     : {total_prefs}")
        print(f"  Total Saved / Applied Jobs: {total_jobs}")
        print(f"  Total Login History Logs  : {total_history}")
        print("=" * 50)
        print("[SUCCESS] Supabase PostgreSQL database is fully ready for JobSnap!")
        return True


def main():
    parser = argparse.ArgumentParser(description="Supabase migration and seed utility for JobSnap")
    parser.add_argument("--password", "-p", help="Supabase database password")
    parser.add_argument("--url", "-u", help="Explicit database URL override")
    args = parser.parse_args()

    # Determine URL
    db_url = args.url or os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        print("[!] Error: Neither DIRECT_URL nor DATABASE_URL found.")
        sys.exit(1)

    # Check for password replacement
    if "[YOUR-PASSWORD]" in db_url:
        pwd = args.password or os.getenv("SUPABASE_DB_PASSWORD")
        if not pwd:
            import getpass
            try:
                pwd = getpass.getpass("Enter Supabase database password: ")
            except (KeyboardInterrupt, EOFError):
                print("\n[!] Operation cancelled.")
                sys.exit(1)
        if not pwd:
            print("[!] Error: No password provided to replace [YOUR-PASSWORD].")
            sys.exit(1)
        db_url = db_url.replace("[YOUR-PASSWORD]", pwd)

    success = run_migration_and_seed(db_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
