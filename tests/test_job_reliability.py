import pytest
from app.services.job_verifier import (
    STATUS_VERIFIED,
    STATUS_UNVERIFIED,
    STATUS_SUSPICIOUS,
    verify_job_reliability,
    attach_reliability_to_job,
    attach_reliability_batch,
)


def test_verified_official_ats_listing():
    """Legitimate job hosted on verified enterprise ATS should be Verified."""
    job = {
        "job_title": "Senior Python Backend Engineer",
        "employer_name": "Datadog",
        "company": "Datadog",
        "job_apply_link": "https://boards.greenhouse.io/datadog/jobs/5432100",
        "job_description": "We are looking for a Senior Backend Engineer proficient in Python, PostgreSQL, and distributed systems.",
        "source": "Greenhouse",
    }
    result = verify_job_reliability(job)
    assert result["status"] == STATUS_VERIFIED
    assert result["score"] >= 80
    assert result["checks"]["link_safety"]["passed"] is True
    assert result["checks"]["payment_safety"]["passed"] is True


def test_verified_famous_enterprise_official_domain():
    """Job claiming a top tech giant with its official careers portal should be Verified."""
    job = {
        "job_title": "Software Engineer II",
        "employer_name": "Microsoft",
        "company": "Microsoft",
        "job_apply_link": "https://careers.microsoft.com/us/en/job/123456/Software-Engineer",
        "job_description": "Join our Azure cloud infrastructure team building large scale microservices.",
        "source": "Microsoft Careers",
    }
    result = verify_job_reliability(job)
    assert result["status"] == STATUS_VERIFIED
    assert result["score"] >= 85
    assert result["checks"]["company_authenticity"]["passed"] is True


def test_suspicious_famous_brand_impersonation():
    """Job claiming a famous company (e.g., Google or Grameenphone) via suspicious link or free mail should be Potentially Suspicious."""
    job = {
        "job_title": "Remote Data Entry / Python Assistant",
        "employer_name": "Google LLC",
        "company": "Google",
        "job_apply_link": "https://bit.ly/google-remote-hiring-bd-2026",
        "job_description": "Work for Google directly. Send CV to google.careers.hr@gmail.com. Immediate joining.",
        "source": "BDJobs Third Party",
    }
    result = verify_job_reliability(job)
    assert result["status"] == STATUS_SUSPICIOUS
    assert result["score"] < 50
    assert result["checks"]["company_authenticity"]["passed"] is False
    assert any("Google" in r or "domain mismatch" in r.lower() or "shortener" in r.lower() for r in result["reasons"])


def test_suspicious_payment_fee_scam_bkash():
    """Job asking for bKash / Nagad / training fees or security deposit must be Potentially Suspicious."""
    job = {
        "job_title": "Junior Office Executive",
        "employer_name": "Global Trade Network",
        "company": "Global Trade Network",
        "job_apply_link": "https://example.com/jobs/apply",
        "job_description": "Selected applicants must send 500 BDT via bKash to 01711000000 for application verification fee and ID card processing.",
        "source": "Online Job Board",
    }
    result = verify_job_reliability(job)
    assert result["status"] == STATUS_SUSPICIOUS
    assert result["checks"]["payment_safety"]["passed"] is False
    assert len(result["critical_flags"]) > 0
    assert any("fee" in flag.lower() or "bkash" in flag.lower() for flag in result["critical_flags"])


def test_suspicious_university_recruitment_impersonation():
    """Job claiming Dhaka University or BUET using free webmail or suspicious domains should be flagged."""
    job = {
        "job_title": "Research Assistant - Computer Science",
        "employer_name": "Dhaka University",
        "company": "Dhaka University",
        "job_apply_link": "http://dhaka-varsity-jobs.blogspot.com/apply",
        "job_description": "Submit resume to du.recruitment2026@yahoo.com for immediate appointment.",
        "source": "BDJobs Third Party",
    }
    result = verify_job_reliability(job)
    assert result["status"] == STATUS_SUSPICIOUS
    assert result["checks"]["company_authenticity"]["passed"] is False


def test_unverified_legitimate_third_party_listing():
    """Standard third-party listing without payment demands or impersonation should be Unverified, not Suspicious."""
    job = {
        "job_title": "Junior Web Developer",
        "employer_name": "Creative Pixel Studio",
        "company": "Creative Pixel Studio",
        "job_apply_link": "https://creativepixelstudio.com/careers/junior-dev",
        "job_description": "Looking for a junior web developer proficient in HTML, CSS, JavaScript, and PHP. Remote friendly.",
        "source": "BDJobs",
    }
    result = verify_job_reliability(job)
    assert result["status"] == STATUS_UNVERIFIED
    assert 50 <= result["score"] <= 79
    assert result["checks"]["payment_safety"]["passed"] is True
    assert len(result["critical_flags"]) == 0


def test_attach_reliability_helpers():
    """Verify that attach_reliability_to_job and batch attach enrich dictionary with all UI properties."""
    job = {
        "job_title": "Backend Python Engineer",
        "employer_name": "Stripe",
        "job_apply_link": "https://stripe.com/jobs/search",
        "job_description": "Scale payments infrastructure.",
    }
    attach_reliability_to_job(job)
    assert "reliability" in job
    assert "reliability_status" in job
    assert "reliability_score" in job
    assert "reliability_label" in job
    assert "reliability_icon" in job
    assert "reliability_color" in job
    assert "reliability_bg" in job
    assert "reliability_reasons" in job

    jobs = [job, {"job_title": "Frontend Engineer", "job_apply_link": "https://example.com"}]
    attach_reliability_batch(jobs)
    assert "reliability" in jobs[1]
    assert jobs[1]["reliability_status"] in [STATUS_VERIFIED, STATUS_UNVERIFIED, STATUS_SUSPICIOUS]


def test_results_and_details_reliability_ui_integration():
    """Verify that results and job detail pages render the reliability badges, audit cards, and filters."""
    from app import create_app
    from app.extensions import db
    from app.models import User, Resume, JobPreference
    from app.routes.jobs import USER_JOBS_CACHE, GLOBAL_JOBS_REGISTRY

    test_app = create_app(test_config={
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })

    client = test_app.test_client()

    with test_app.app_context():
        db.drop_all()
        db.create_all()
        user = User(name="Test User", email="reliability@test.com")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

        resume = Resume(
            user_id=user.id,
            filename="Test_Resume.pdf",
            extracted_skills='["Python", "Django", "SQL"]',
            extracted_text="Python Backend Developer with Django and SQL.",
            education="B.Sc in CSE, University of Dhaka, 2022",
            experience="Software Engineer at Tech Ltd (2022-Present)",
            completeness_score=85,
        )
        db.session.add(resume)
        pref = JobPreference(user_id=user.id, target_role="Python Developer", location="Remote")
        db.session.add(pref)
        db.session.commit()

        # Login
        client.post("/login", data={"email": "reliability@test.com", "password": "Password123!"})

        # Inject sample jobs into cache representing all 3 statuses
        verified_job = {
            "job_id": "test_verified_1",
            "job_title": "Senior Python Engineer",
            "employer_name": "Microsoft",
            "company": "Microsoft",
            "job_city": "Remote",
            "location": "Remote",
            "job_employment_type": "Full-time",
            "job_apply_link": "https://careers.microsoft.com/jobs/123",
            "job_description": "Cloud backend engineering with Python and Azure.",
            "source": "Microsoft Careers",
            "combined_score": 88,
            "matched_skills": ["Python", "Django"],
            "missing_skills": ["Azure"],
            "partial_skills": [],
        }
        attach_reliability_to_job(verified_job)

        suspicious_job = {
            "job_id": "test_suspicious_2",
            "job_title": "Python Developer - BD Hiring",
            "employer_name": "Google",
            "company": "Google",
            "job_city": "Dhaka",
            "location": "Dhaka",
            "job_employment_type": "Part-time",
            "job_apply_link": "https://bit.ly/google-fake-apply",
            "job_description": "Pay 500 BDT via bKash to 01711000000 for verification fee. Send CV to hr@gmail.com",
            "source": "BDJobs",
            "combined_score": 60,
            "matched_skills": ["Python"],
            "missing_skills": ["Excel"],
            "partial_skills": [],
        }
        attach_reliability_to_job(suspicious_job)

        USER_JOBS_CACHE[user.id] = [verified_job, suspicious_job]
        GLOBAL_JOBS_REGISTRY["test_verified_1"] = verified_job
        GLOBAL_JOBS_REGISTRY["test_suspicious_2"] = suspicious_job

        from unittest.mock import patch
        with patch("app.routes.jobs.fetch_jobs", return_value=[verified_job, suspicious_job]):
            # Test results page rendering
            res = client.get("/results")
            assert res.status_code == 200
            html = res.get_data(as_text=True)
            assert 'id="filter-reliability"' in html
            assert 'All Reliability' in html
            assert 'Verified Only' in html
            assert 'Potentially Suspicious' in html
            assert 'Reliability Audit' in html or 'Trust Score' in html
            assert 'data-reliability="verified"' in html
            assert 'data-reliability="potentially suspicious"' in html

        # Test job detail view for verified job
        detail_res = client.get("/job/test_verified_1")
        assert detail_res.status_code == 200
        detail_html = detail_res.get_data(as_text=True)
        assert 'Reliability Audit' in detail_html
        assert 'Credibility Trust Score' in detail_html
        assert 'Verified Employer' in detail_html or 'Verified' in detail_html

        # Test job detail view for suspicious job
        suspicious_res = client.get("/job/test_suspicious_2")
        assert suspicious_res.status_code == 200
        susp_html = suspicious_res.get_data(as_text=True)
        assert 'Potentially Suspicious' in susp_html
        assert 'High Risk Warning' in susp_html
        assert 'Never send money or bKash/Nagad payments' in susp_html

