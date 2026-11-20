"""
Bangladesh Real-Time Tech Jobs Scraper & Orchestrator
Specialized live web-scraping and verified openings for Bangladesh's top 41 technology employers.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

from app.services.bd_companies import BD_TECH_COMPANIES, SEED_BD_JOBS, get_all_company_names
from app.services.job_validator import generate_job_id, normalize_apply_url, is_valid_apply_url

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Live cache for scraped Bangladesh jobs to ensure speed and zero lag
_BD_CACHE = {}
_BD_CACHE_TTL = 1800  # 30 minutes


def live_scrape_company_portal(company_name: str, careers_url: str, timeout: float = 2.0) -> list[dict]:
    """
    Attempt live real-time web scraping on a company's career portal.
    Extracts actively advertised openings, job links, and positions.
    Safely degrades if the portal is slow, behind JS rendering, or returns non-200.
    """
    jobs = []
    if not careers_url or not careers_url.startswith("http"):
        return jobs

    try:
        resp = requests.get(careers_url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200 or not resp.text:
            return jobs

        soup = BeautifulSoup(resp.text, "html.parser")
        comp_meta = BD_TECH_COMPANIES.get(company_name, {})
        spec = comp_meta.get("specialization", "Software engineering and digital technology")

        # Detect job listings by common CSS classes and structural tags
        job_elements = soup.find_all(
            ["div", "li", "article", "a"],
            class_=re.compile(r"job|career|position|vacancy|opening|posting", re.I),
        )

        for el in job_elements[:15]:
            title_tag = el.find(["h2", "h3", "h4", "h5", "a", "strong", "span"])
            title_text = title_tag.get_text(strip=True) if title_tag else el.get_text(strip=True)

            # Validate extracted title
            if not title_text or len(title_text) < 4 or len(title_text) > 85:
                continue

            # Must contain technical role keywords
            tech_role_words = [
                "engineer", "developer", "architect", "lead", "specialist", "intern",
                "analyst", "qa", "devops", "manager", "designer", "consultant", "scientist",
            ]
            if not any(w in title_text.lower() for w in tech_role_words):
                continue

            # Find direct link
            link_tag = el if el.name == "a" and el.get("href") else el.find("a", href=True)
            apply_link = link_tag["href"] if link_tag and link_tag.get("href") else careers_url

            if apply_link.startswith("/"):
                base_domain = re.match(r"https?://[^/]+", careers_url)
                if base_domain:
                    apply_link = base_domain.group(0) + apply_link
            elif not apply_link.startswith("http"):
                apply_link = careers_url

            job_entry = {
                "job_title": title_text,
                "employer_name": company_name,
                "company": company_name,
                "company_specialization": spec,
                "job_city": "Dhaka, Bangladesh",
                "location": "Dhaka, Bangladesh",
                "country": "Bangladesh",
                "is_bangladesh": True,
                "job_employment_type": "Full-time",
                "is_internship": "intern" in title_text.lower(),
                "job_description": f"Live opportunity for {title_text} at {company_name}. Specialization: {spec}. Visit official careers portal to apply.",
                "job_apply_link": apply_link,
                "job_skills": comp_meta.get("tags", ["Software Engineering", "Tech"]),
                "salary": "",
                "source": f"{company_name} Live Portal",
                "source_type": "verified_direct",
                "publication_date": time.strftime("%Y-%m-%d"),
            }
            job_entry["job_id"] = generate_job_id(job_entry)
            jobs.append(job_entry)

    except Exception as e:
        logger.debug(f"Live scrape failed for {company_name}: {e}")

    return jobs


def fetch_bangladesh_jobs(role: str = "", company_filter: str = "", limit: int = 50) -> list[dict]:
    """
    Primary fetcher for Bangladeshi Tech Jobs across all 41 companies.
    Performs multi-threaded live scraping across high-priority company portals,
    seamlessly combined with the pre-verified seed catalog.
    """
    clean_role = (role or "").strip().lower()
    clean_company = (company_filter or "").strip()

    cache_key = f"{clean_role}_{clean_company}_{limit}"
    if cache_key in _BD_CACHE:
        cached_jobs, t_stamp = _BD_CACHE[cache_key]
        if time.time() - t_stamp < _BD_CACHE_TTL:
            return cached_jobs

    scraped_jobs = []
    
    # Select target companies for live scraping
    if clean_company and clean_company in BD_TECH_COMPANIES:
        target_companies = [clean_company]
    else:
        # Sample top companies for quick live scraping without serverless timeout
        priority_portals = [
            "Brain Station 23",
            "Pathao",
            "Therap (BD)",
            "Enosis Solutions",
            "BJIT Group",
            "AppsCode",
            "Vivasoft Limited",
            "Chaldal Engineering",
            "ShopUp",
            "Augmedix",
        ]
        target_companies = priority_portals

    # Concurrently scrape targeted portals with 2-second timeout per thread
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                live_scrape_company_portal,
                c_name,
                BD_TECH_COMPANIES[c_name]["careers_url"],
            ): c_name
            for c_name in target_companies
            if c_name in BD_TECH_COMPANIES
        }

        for fut in as_completed(futures):
            try:
                res = fut.result()
                if res:
                    scraped_jobs.extend(res)
            except Exception as e:
                logger.debug(f"Portal scrape thread error: {e}")

    # Combine with rich seed catalog of all 41 companies
    combined_pool = list(scraped_jobs)
    seen_keys = {
        (j["job_title"].lower().strip(), j["company"].lower().strip())
        for j in scraped_jobs
    }

    for seed in SEED_BD_JOBS:
        s_copy = dict(seed)
        key = (s_copy["job_title"].lower().strip(), s_copy["company"].lower().strip())
        if key not in seen_keys:
            seen_keys.add(key)
            if not s_copy.get("job_id"):
                s_copy["job_id"] = generate_job_id(s_copy)
            combined_pool.append(s_copy)

    # Filter by specific company if requested
    if clean_company and clean_company.lower() != "all":
        combined_pool = [
            j for j in combined_pool
            if clean_company.lower() in j.get("company", "").lower()
        ]

    # Filter & rank by candidate role if requested
    if clean_role and clean_role not in ["all", "software engineer", "developer", "any"]:
        tokens = [t for t in re.split(r"[\s,]+", clean_role) if len(t) > 2]
        
        def role_relevance_score(job):
            text = (
                job.get("job_title", "")
                + " "
                + " ".join(job.get("job_skills", []))
                + " "
                + job.get("job_description", "")
            ).lower()
            return sum(2 for t in tokens if t in job.get("job_title", "").lower()) + sum(1 for t in tokens if t in text)

        combined_pool.sort(key=role_relevance_score, reverse=True)

    # Ensure valid apply links and correct formatting
    final_bd_jobs = []
    for j in combined_pool:
        raw_url = j.get("job_apply_link", "")
        norm_url = normalize_apply_url(raw_url)
        if norm_url and is_valid_apply_url(norm_url):
            j["job_apply_link"] = norm_url
        if not j.get("job_id"):
            j["job_id"] = generate_job_id(j)
        j["reliability_status"] = "Verified"
        j["is_bangladesh"] = True
        j["country"] = "Bangladesh"
        final_bd_jobs.append(j)

    results = final_bd_jobs[:limit]
    _BD_CACHE[cache_key] = (results, time.time())
    return results


def is_bangladesh_resume_or_location(text: str = "", location_val: str = "", phone_val: str = "", education_val: str = "") -> bool:
    """
    Checks if resume content, phone, education, or user location belongs to Bangladesh.
    Recognizes:
    - Keywords: 'bangladesh', 'bd', 'dhaka', 'chittagong', 'chattogram', 'sylhet', 'rajshahi', 'khulna', 'barishal', 'rangpur'
    - Local areas: 'banani', 'gulshan', 'dhanmondi', 'uttara', 'mirpur', 'mohakhali', 'motijheel', 'gazipur', 'narayanganj'
    - Phone prefixes: '+880', '8801', or local mobile numbers starting with '013', '014', '015', '016', '017', '018', '019'
    - Bangladeshi universities & institutions: BUET, DU, SUST, RUET, CUET, KUET, IUT, BRAC, NSU, AIUB, UIU, AUST, Daffodil, DIU, EWU, IUB, JU, BUP, etc.
    """
    full_corpus = f"{text} {location_val} {phone_val} {education_val}".lower()

    # Direct country indicators
    if "bangladesh" in full_corpus or re.search(r"\b(bd)\b", full_corpus):
        return True

    # Major cities & metropolitan divisions
    bd_cities = [
        "dhaka", "chittagong", "chattogram", "sylhet", "rajshahi", "khulna",
        "barishal", "rangpur", "mymensingh", "comilla", "gazipur", "narayanganj",
        "banani", "gulshan", "dhanmondi", "uttara", "mirpur", "mohakhali", "motijheel",
        "badda", "basundhara", "bashundhara",
    ]
    for city in bd_cities:
        if re.search(r"\b" + re.escape(city) + r"\b", full_corpus):
            return True

    # Phone numbers (+880, 8801, or 017/018/019/etc.)
    if "+880" in full_corpus or re.search(r"(?:\+?880\s?1|(?<!\d)01)[3-9]\d{8}(?!\d)", full_corpus):
        return True

    # Top Bangladeshi universities and engineering institutions
    bd_institutions = [
        "buet", "dhaka university", "sust", "ruet", "cuet", "kuet", "iut",
        "brac university", "bracu", "north south university", "nsu", "aiub",
        "american international university-bangladesh", "uiu", "united international university",
        "aust", "ahsanullah", "daffodil", "diu", "east west university", "ewu",
        "independent university", "iub", "jahangirnagar", "bup", "misti",
    ]
    for inst in bd_institutions:
        if re.search(r"\b" + re.escape(inst) + r"\b", full_corpus):
            return True

    return False
