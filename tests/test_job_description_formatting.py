import pytest
from bs4 import BeautifulSoup
from app.services.job_description_formatter import clean_job_description


def test_plain_text_bullets_and_numbered_lists():
    """Verify plain text with bullet points, numbered lists, and headings are properly structured."""
    raw = """
    About the Role:
    We are looking for an exceptional Python Backend Engineer.

    Key Responsibilities:
    * Build and maintain scalable REST APIs
    * Integrate PostgreSQL and Redis caching
    * Deploy containerized microservices via Docker

    Requirements:
    1. 3+ years of professional backend engineering experience
    2. Strong proficiency in Python, Flask, or Django
    3. Practical understanding of relational databases

    Compensation & Benefits:
    • Competitive salary package
    • Flexible remote work arrangement

    Visit https://careers.example.com/apply for more details.
    """
    html_output = clean_job_description(raw)

    assert '<div class="job-description-content">' in html_output
    assert '<h4 class="job-desc-heading">About the Role:</h4>' in html_output
    assert '<h4 class="job-desc-heading">Key Responsibilities:</h4>' in html_output
    assert '<h4 class="job-desc-heading">Requirements:</h4>' in html_output
    assert '<h4 class="job-desc-heading">Compensation &amp; Benefits:</h4>' in html_output

    soup = BeautifulSoup(html_output, "html.parser")

    # Check unordered list
    uls = soup.find_all("ul", class_="job-desc-list")
    assert len(uls) >= 2
    ul_items = [li.get_text(strip=True) for li in uls[0].find_all("li")]
    assert "Build and maintain scalable REST APIs" in ul_items
    assert "Integrate PostgreSQL and Redis caching" in ul_items
    # Confirm bullet symbol (*) is stripped so browser renders standard list bullet without double-bullets
    assert not any(it.startswith("*") for it in ul_items)

    # Check ordered list
    ols = soup.find_all("ol", class_="job-desc-ordered-list")
    assert len(ols) >= 1
    ol_items = [li.get_text(strip=True) for li in ols[0].find_all("li")]
    assert "3+ years of professional backend engineering experience" in ol_items
    # Confirm number symbol is stripped
    assert not any(it.startswith("1.") for it in ol_items)

    # Check auto-linked URL
    link = soup.find("a", class_="job-desc-link")
    assert link is not None
    assert link.get("href") == "https://careers.example.com/apply"
    assert link.get("target") == "_blank"
    assert link.get("rel") == ["noopener", "noreferrer"]


def test_messy_word_and_html_inline_styles_sanitization():
    """Verify inline style pollution, Word MsoNormal tags, and raw colors/backgrounds are stripped."""
    messy_html = """
    <p class="MsoNormal" style="margin: 0in 0in 8pt; line-height: 15.6933px; color: #000000; background-color: #ffffff; font-family: Calibri;">
        <span style="font-size: 11pt; color: #000000;">Unió Digital is an Arizona-based managed service provider.</span>
    </p>
    <p class="MsoNormal" style="margin: 0in; line-height: normal;">
        <strong>Duties & Responsibilities:</strong>
    </p>
    <p class="MsoListParagraphCxSpFirst" style="margin: 0in 0in 0in 0.5in; line-height: 15.6933px; color: #000000; text-indent: -0.25in;">
        ·<span style="font-style: normal; font-size: 7pt;">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>Resolve Tier 3 technical escalations
    </p>
    <p class="MsoListParagraphCxSpLast" style="margin: 0in 0in 0in 0.5in; line-height: 15.6933px; color: #000000; text-indent: -0.25in;">
        ·<span style="font-style: normal; font-size: 7pt;">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>Manage client network infrastructure
    </p>
    """
    cleaned = clean_job_description(messy_html)

    # Ensure dangerous/destructive inline styles are removed completely
    assert "color: #000000" not in cleaned
    assert "background-color: #ffffff" not in cleaned
    assert "margin: 0in" not in cleaned
    assert "font-family: Calibri" not in cleaned
    assert "MsoNormal" not in cleaned

    soup = BeautifulSoup(cleaned, "html.parser")
    # Check that Duties heading was converted
    heading = soup.find("h4", class_="job-desc-heading")
    assert heading is not None
    assert "Duties" in heading.get_text()

    # Check that pseudo-bullet paragraphs were converted to clean ul/li
    lis = soup.find_all("li", class_="job-desc-item")
    assert len(lis) >= 2
    li_texts = [li.get_text(strip=True) for li in lis]
    assert any("Resolve Tier 3 technical escalations" in t for t in li_texts)
    assert any("Manage client network infrastructure" in t for t in li_texts)
    # Check that leading middle dot (·) was cleaned
    assert not any(t.startswith("·") for t in li_texts)


def test_broken_escaped_tags_and_truncated_html():
    """Verify broken escaped tags (&lt;span...) and trailing cut-off tags are cleaned safely."""
    broken_html = (
        '<p>Overview of the position.</p>'
        '<p>·&lt;span style="font-style: normal; font-variant: normal; font-language-override: normal; line-height: nor'
    )
    cleaned = clean_job_description(broken_html)

    # Broken raw escaped tag text should never be exposed
    assert "&lt;span" not in cleaned
    assert "line-height: nor" not in cleaned
    assert '<div class="job-description-content">' in cleaned


def test_overflow_and_long_token_wrapping():
    """Verify unbroken long strings and URLs are formatted inside wrap-safe containers."""
    long_url = "https://careers.company.com/apply/v2/positions/software-engineer-backend-infrastructure-cloud-platform-services-2026"
    raw = f"Apply directly using this long link: {long_url}"
    cleaned = clean_job_description(raw)

    soup = BeautifulSoup(cleaned, "html.parser")
    link = soup.find("a", class_="job-desc-link")
    assert link is not None
    assert link.get("href") == long_url
    assert "job-desc-link" in link.get("class", [])


def test_empty_description_fallback():
    """Verify null or empty description provides clear friendly fallback."""
    empty_res = clean_job_description("")
    assert "job-desc-empty" in empty_res
    assert "No detailed description provided" in empty_res

    none_res = clean_job_description(None)
    assert "job-desc-empty" in none_res


def test_job_detail_page_renders_formatted_description():
    """Verify /job/<id> renders formatted description with proper container classes."""
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
        user = User(name="Format User", email="format@test.com")
        user.set_password("SecurePass123!")
        db.session.add(user)
        db.session.commit()

        resume = Resume(
            user_id=user.id,
            filename="Format_Resume.pdf",
            extracted_skills='["Python", "Django"]',
            extracted_text="Python Backend Engineer.",
            completeness_score=80,
        )
        db.session.add(resume)
        pref = JobPreference(user_id=user.id, target_role="Python Engineer", location="Remote")
        db.session.add(pref)
        db.session.commit()

        client.post("/login", data={"email": "format@test.com", "password": "SecurePass123!"})

        job = {
            "job_id": "test_format_101",
            "job_title": "Python Platform Engineer",
            "employer_name": "CloudScale Inc",
            "company": "CloudScale Inc",
            "job_city": "Remote",
            "location": "Remote",
            "job_employment_type": "Full-time",
            "job_apply_link": "https://careers.cloudscale.io/jobs/101",
            "job_description": "Responsibilities:\n* Maintain microservices\n* Optimize queries\n\nRequirements:\n1. 3+ years experience\n2. Python mastery",
            "source": "Remotive",
            "combined_score": 85,
            "matched_skills": ["Python"],
            "missing_skills": [],
            "partial_skills": [],
        }

        USER_JOBS_CACHE[user.id] = [job]
        GLOBAL_JOBS_REGISTRY["test_format_101"] = job

        res = client.get("/job/test_format_101")
        assert res.status_code == 200
        html_str = res.get_data(as_text=True)

        assert "job-description-wrapper" in html_str
        assert "job-description-content" in html_str
        assert "job-desc-heading" in html_str
        assert "job-desc-list" in html_str
        assert "job-desc-item" in html_str
        assert "Maintain microservices" in html_str
        assert "Optimize queries" in html_str
        assert "Python mastery" in html_str
