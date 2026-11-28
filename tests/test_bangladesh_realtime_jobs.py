import pytest
from app.services.bd_job_scraper import (
    is_bangladesh_resume_or_location,
    fetch_bangladesh_jobs,
)
from app.services.job_verifier import attach_reliability_to_job
from app.services.job_api import fetch_jobs


def test_bangladesh_cv_detection():
    # Keyword 'Bangladesh'
    assert is_bangladesh_resume_or_location(text="Experienced developer based in Bangladesh.") is True
    # 'Bangladeshi'
    assert is_bangladesh_resume_or_location(text="Nationality: Bangladeshi") is True
    # .bd domain email
    assert is_bangladesh_resume_or_location(text="Contact: rafi@du.ac.bd") is True
    # BD institution
    assert is_bangladesh_resume_or_location(education_val="B.Sc. in CSE, BUET") is True
    # BD Phone
    assert is_bangladesh_resume_or_location(phone_val="+8801712345678") is True
    # BD City / area
    assert is_bangladesh_resume_or_location(location_val="Dhanmondi, Dhaka") is True
    # Non-BD CV
    assert is_bangladesh_resume_or_location(text="Python developer in Berlin, Germany", location_val="Berlin") is False


def test_fetch_bangladesh_jobs_returns_verified_listings():
    jobs = fetch_bangladesh_jobs("Software Engineer", limit=10)
    assert len(jobs) > 0
    for j in jobs:
        assert j.get("is_bangladesh") is True
        assert j.get("country") == "Bangladesh"
        assert j.get("job_apply_link", "").startswith("http")
        attach_reliability_to_job(j)
        assert j.get("reliability", {}).get("status") == "Verified"


def test_fetch_jobs_bangladesh_prioritization():
    # When country='bangladesh', Bangladesh jobs must be at index 0
    jobs = fetch_jobs(role="Software Engineer", location="Remote", country="bangladesh")
    assert len(jobs) > 0
    top_job = jobs[0]
    assert top_job.get("is_bangladesh") is True or top_job.get("country") == "Bangladesh"
