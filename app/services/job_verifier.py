"""
JobSnap - Job Reliability & Authenticity Verification System
============================================================
Evaluates job advertisements for authenticity, brand impersonation,
suspicious payment/deposit requests, and application link reliability.

Supports multi-source recruitment streams including BDJobs, Remotive,
Arbeitnow, RemoteOK, Jobicy, Adzuna, and corporate direct portals.

Classification Statuses:
1. Verified: Confirmed legitimate employer, official domain, or trusted ATS.
2. Unverified: Standard third-party or small business listing without negative
               flags, but lacking direct enterprise domain verification.
3. Potentially Suspicious: Detected scam indicators such as upfront payment
                          demands (bKash/Nagad/fees), brand impersonation,
                          URL shorteners, or deceptive contact methods.
"""

import logging
import re
import urllib.parse

logger = logging.getLogger(__name__)

STATUS_VERIFIED = "Verified"
STATUS_UNVERIFIED = "Unverified"
STATUS_SUSPICIOUS = "Potentially Suspicious"

# ---------------------------------------------------------------------------
# Catalog of Famous Entities & Respective Official Domain Roots
# ---------------------------------------------------------------------------
FAMOUS_ENTITIES = {
    # Global Tech Enterprises
    "google": ["google.com", "abc.xyz", "google.org", "careers.google.com"],
    "microsoft": ["microsoft.com", "careers.microsoft.com", "linkedin.com"],
    "amazon": ["amazon.jobs", "amazon.com", "aws.amazon.com"],
    "meta": ["metacareers.com", "meta.com", "facebook.com"],
    "facebook": ["metacareers.com", "meta.com", "facebook.com"],
    "apple": ["apple.com", "jobs.apple.com"],
    "netflix": ["netflix.com", "jobs.netflix.com"],
    "ibm": ["ibm.com"],
    "oracle": ["oracle.com"],
    "intel": ["intel.com"],
    "cisco": ["cisco.com"],
    "uber": ["uber.com"],
    "adobe": ["adobe.com"],
    "salesforce": ["salesforce.com"],
    "spotify": ["spotify.com"],
    "twitter": ["x.com", "twitter.com"],
    "linkedin": ["linkedin.com"],
    "paypal": ["paypal.com"],
    "samsung": ["samsung.com", "samsungcareers.com"],
    "sony": ["sony.com"],
    "siemens": ["siemens.com"],

    # Bangladesh Telecom, Fintech & Tech Leaders
    "grameenphone": ["grameenphone.com", "telenor.com"],
    "robi": ["robi.com.bd", "axiata.com"],
    "banglalink": ["banglalink.net", "veon.com"],
    "teletalk": ["teletalk.com.bd"],
    "bkash": ["bkash.com"],
    "nagad": ["nagad.com.bd"],
    "pathao": ["pathao.com"],
    "chaldal": ["chaldal.com"],
    "shopup": ["shopup.org"],
    "brain station 23": ["brainstation-23.com"],
    "brain station": ["brainstation-23.com"],
    "therap": ["therapbd.com", "therapservices.net"],
    "therap bd": ["therapbd.com", "therapservices.net"],
    "therap (bd)": ["therapbd.com", "therapservices.net"],
    "therap (bd) ltd.": ["therapbd.com", "therapservices.net"],
    "selise": ["selise.ch", "selisegroup.com"],
    "selise digital platforms": ["selise.ch", "selisegroup.com"],
    "enosis": ["enosisbd.com"],
    "enosis solutions": ["enosisbd.com"],
    "bjit": ["bjitgroup.com"],
    "bjit group": ["bjitgroup.com"],
    "vivasoft": ["vivasoftltd.com"],
    "vivasoft limited": ["vivasoftltd.com"],
    "cefalo": ["cefalo.com"],
    "cefalo bangladesh": ["cefalo.com"],
    "dynamic solution innovators": ["dsinnovators.com"],
    "dynamic solution innovators (dsi)": ["dsinnovators.com"],
    "dsi": ["dsinnovators.com"],
    "samsung r&d institute bangladesh": ["samsung.com"],
    "srbd": ["samsung.com"],
    "nascenia": ["nascenia.com"],
    "kaz software": ["kaz.com.bd"],
    "leadsoft": ["leadsoft.org"],
    "leadsoft bangladesh": ["leadsoft.org"],
    "tigerit": ["tigerit.com"],
    "tigerit bangladesh": ["tigerit.com"],
    "walton": ["waltonbd.com", "waltonhib-tech.com"],
    "walton hi-tech": ["waltonbd.com", "waltonhib-tech.com"],
    "ulkasemi": ["ulkasemi.com"],
    "datasoft": ["datasoft-bd.com"],
    "datasoft systems bangladesh": ["datasoft-bd.com"],
    "synesis it": ["synesisit.com.bd"],
    "dream71": ["dream71.com"],
    "dream71 bangladesh": ["dream71.com"],
    "southtech": ["southtechgroup.com"],
    "southtech group": ["southtechgroup.com"],
    "kona software lab": ["konasl.com"],
    "reve systems": ["revesystems.com"],
    "servicengine": ["servicengine.com", "secbpo.com"],
    "graphic people": ["graphicpeoplestudio.com"],
    "relisource": ["relisource.com"],
    "technonext": ["technonext.com"],
    "appscode": ["appscode.com"],
    "shikho": ["shikho.com"],
    "doctorkoi": ["doctorkoi.com"],
    "doctorkoi.com": ["doctorkoi.com"],
    "augmedix": ["augmedix.com"],
    "augmedix bangladesh": ["augmedix.com"],
    "bondstein": ["bondstein.com"],
    "bondstein technologies": ["bondstein.com"],
    "brac it": ["bracits.com"],
    "brac it services": ["bracits.com"],
    "brac it services (bits)": ["bracits.com"],
    "daffodil software": ["daffodil-bd.com"],
    "daffodil software limited": ["daffodil-bd.com"],
    "riseup labs": ["riseuplabs.com"],

    # Renowned Universities & Academic Institutions
    "dhaka university": ["du.ac.bd"],
    "university of dhaka": ["du.ac.bd"],
    "buet": ["buet.ac.bd"],
    "jahangirnagar university": ["juniv.edu"],
    "rajshahi university": ["ru.ac.bd"],
    "chittagong university": ["cu.ac.bd"],
    "north south university": ["northsouth.edu"],
    "nsu": ["northsouth.edu"],
    "brac university": ["bracu.ac.bd"],
    "bracu": ["bracu.ac.bd"],
    "independent university": ["iub.edu.bd"],
    "ahsanullah university": ["aust.edu"],
    "islamic university of technology": ["iutoic-dhaka.edu"],
    "aiub": ["aiub.edu"],
    "uiu": ["uiu.ac.bd"],
    "daffodil international university": ["daffodilvarsity.edu.bd"],
    "harvard": ["harvard.edu"],
    "mit": ["mit.edu"],
    "stanford": ["stanford.edu"],
    "oxford": ["ox.ac.uk"],
    "cambridge": ["cam.ac.uk"],

    # Banks & Large Conglomerates
    "brac bank": ["bracbank.com"],
    "dutch-bangla bank": ["dutchbanglabank.com"],
    "dbbl": ["dutchbanglabank.com"],
    "city bank": ["thecitybank.com"],
    "eastern bank": ["ebl.com.bd"],
    "standard chartered": ["sc.com"],
    "hsbc": ["hsbc.com", "hsbc.com.bd"],
    "sonali bank": ["sonalibank.com.bd"],
    "square": ["squaregroup.com", "squarepharma.com.bd"],
    "square pharma": ["squarepharma.com.bd"],
    "beximco": ["beximco.com"],
    "aci": ["aci-bd.com"],
    "pran": ["pranfoods.net", "rflbd.com"],
    "pran-rfl": ["pranfoods.net", "rflbd.com"],
    "akij": ["akij.net"],
    "bashundhara": ["bashundharagroup.com"],

    # International Organizations & NGOs
    "united nations": ["un.org", "undp.org", "unicef.org", "who.int", "worldbank.org", "wfp.org"],
    "un": ["un.org", "undp.org", "unicef.org", "who.int", "worldbank.org", "wfp.org"],
    "undp": ["undp.org"],
    "unicef": ["unicef.org"],
    "who": ["who.int"],
    "world bank": ["worldbank.org"],
    "asian development bank": ["adb.org"],
    "brac": ["brac.net"],
    "icddr,b": ["icddrb.org"],
    "icddrb": ["icddrb.org"],
    "red cross": ["icrc.org", "ifrc.org"],
}

# ---------------------------------------------------------------------------
# Trusted Enterprise Applicant Tracking Systems (ATS)
# ---------------------------------------------------------------------------
TRUSTED_ATS_DOMAINS = {
    "greenhouse.io", "gh.io", "boards.greenhouse.io",
    "lever.co", "jobs.lever.co",
    "workday.com", "myworkdayjobs.com",
    "ashbyhq.com", "jobs.ashbyhq.com",
    "smartrecruiters.com",
    "bamboohr.com",
    "taleo.net",
    "icims.com",
    "jobvite.com",
    "recruitee.com",
    "workable.com", "apply.workable.com",
    "applytojob.com",
    "rippling.com",
    "personio.com", "personio.de",
    "pinpointhq.com",
    "breezy.hr",
    "freshteam.com",
}

# ---------------------------------------------------------------------------
# Vetted Tech Recruitment Platforms & Legitimate Aggregators
# ---------------------------------------------------------------------------
VETTED_PLATFORM_DOMAINS = {
    "weworkremotely.com",
    "remotive.com",
    "arbeitnow.com",
    "remoteok.com",
    "remoteok.io",
    "jobicy.com",
    "linkedin.com",
    "lemon.io",
    "bdjobs.com",
    "jobs.bdjobs.com",
    "brainstation-23.com",
    "nascenia.com",
    "bjitgroup.com",
    "therapbd.com",
}

# ---------------------------------------------------------------------------
# High-Risk URL Shorteners & Free Hosts Often Abused for Scams
# ---------------------------------------------------------------------------
URL_SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "cutt.ly", "is.gd",
    "rb.gy", "shorturl.at", "rebrand.ly", "ow.ly", "buff.ly",
}

FREE_HOSTING_DOMAINS = {
    "blogspot.com", "wordpress.com", "wixsite.com", "weebly.com",
    "sites.google.com", "jimdofree.com", "000webhostapp.com",
}

FREE_WEBMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "ymail.com", "hotmail.com", "outlook.com",
    "live.com", "aol.com", "mail.com", "protonmail.com", "zoho.com",
    "inbox.com", "gmx.com",
}

# ---------------------------------------------------------------------------
# Scam & Payment Request Regex Patterns
# ---------------------------------------------------------------------------
PAYMENT_PATTERNS = [
    # Mobile Financial Services (MFS) used in BD recruitment scams
    r"\b(bkash|b-kash|nagad|rocket|upay|surecash)\b",
    # Fee & deposit demands
    r"\b(registration\s+fee|application\s+fee|processing\s+fee|interview\s+fee|exam\s+fee|examination\s+fee)\b",
    r"\b(training\s+fee|security\s+money|security\s+deposit|refundable\s+deposit|equipment\s+deposit|badge\s+fee)\b",
    r"\b(medical\s+test\s+fee|police\s+clearance\s+fee|verification\s+fee|form\s+purchase\s+fee|joining\s+fee)\b",
    r"\b(send\s+money|send\s+tk|send\s+bdt|taka\s+send|pay\s+fee|pay\s+advance|advance\s+payment)\b",
    r"\b(transaction\s+id|trx\s*id|trxid)\b",
    # Bengali script indicators
    r"(বিকাশ|নগদ|রকেট|জামানত|রেজিস্ট্রেশন\s*ফি|খরচ\s*পাঠাতে|টাকা\s*পাঠান|ভর্তি\s*ফি)",
]

DECEPTIVE_PROMISE_PATTERNS = [
    r"\b(no\s+interview\s+required|direct\s+joining\s+without\s+interview)\b",
    r"\b(100%\s+guarantee\s+appointment|direct\s+appointment\s+letter\s+without)\b",
    r"\b(earn\s+\$?[0-9]{3,}\s+daily\s+without\s+experience)\b",
    r"\b(typing\s+captcha\s+work\s+daily\s+payment|sms\s+sending\s+job\s+daily)\b",
    r"\b(100%\s+visa\s+guarantee\s+with\s+job)\b",
]

ANONYMOUS_COMPANY_NAMES = {
    "confidential", "confidential company", "leading mnc", "top mnc",
    "reputed company", "reputed software company", "renowned group",
    "famous university", "a leading it firm", "hiring employer",
    "company", "private group",
}


def _extract_domain(url: str) -> str:
    """Extract lowercase netloc without port."""
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        netloc = parsed.netloc.split(":")[0].strip().lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def _domain_matches(host: str, target: str) -> bool:
    """Exact or subdomain match (e.g. 'careers.microsoft.com' matches 'microsoft.com')."""
    if not host or not target:
        return False
    h = host.lower().strip()
    t = target.lower().strip()
    return h == t or h.endswith("." + t)


def _extract_emails(text: str) -> list[str]:
    """Find all email addresses in text."""
    if not text:
        return []
    return re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)


def _check_payment_requests(text: str) -> list[str]:
    """Return matched suspicious payment/fee phrases in text."""
    matched = []
    if not text:
        return matched
    for pat in PAYMENT_PATTERNS:
        found = re.findall(pat, text, flags=re.IGNORECASE)
        if found:
            # Flatten tuples if regex has capture groups
            for item in found:
                val = item if isinstance(item, str) else item[0]
                if val and val.lower() not in [m.lower() for m in matched]:
                    matched.append(val.strip())
    return matched


def _check_deceptive_promises(text: str) -> list[str]:
    """Return matched deceptive/unrealistic promise phrases."""
    matched = []
    if not text:
        return matched
    for pat in DECEPTIVE_PROMISE_PATTERNS:
        found = re.findall(pat, text, flags=re.IGNORECASE)
        if found:
            for item in found:
                val = item if isinstance(item, str) else item[0]
                if val and val.lower() not in [m.lower() for m in matched]:
                    matched.append(val.strip())
    return matched


def _find_claimed_famous_entity(title: str, company: str, desc: str) -> tuple[str, list[str]] | None:
    """
    Check if the advertisement claims to represent a famous entity.
    Returns (entity_name, allowed_domains) or None.
    """
    comp_lower = (company or "").lower().strip()
    title_lower = (title or "").lower().strip()
    desc_start = (desc or "")[:500].lower()

    for entity, domains in FAMOUS_ENTITIES.items():
        # Match entity as whole word or phrase in company or title
        pattern = r"\b" + re.escape(entity) + r"\b"
        if re.search(pattern, comp_lower) or re.search(pattern, title_lower) or re.search(pattern, desc_start):
            return entity, domains
    return None


def verify_job_reliability(job: dict) -> dict:
    """
    Comprehensive multi-signal reliability and fraud risk verification.

    Analyzes:
    1. Company Information & Brand Authenticity
    2. Application Link & Host Trust
    3. Payment & Financial Safety (bKash/Nagad/deposits)
    4. Contact Channels & Description Transparency

    Returns a structured verification diagnostic dictionary.
    """
    if not isinstance(job, dict):
        return {
            "status": STATUS_UNVERIFIED,
            "score": 50,
            "badge_color": "#D97706",
            "badge_bg": "#FFFBEB",
            "badge_border": "#FDE68A",
            "icon": "fa-solid fa-shield-halved",
            "label": "Unverified Listing",
            "summary": "Job information is incomplete or unverified.",
            "reasons": ["Listing contains insufficient data for complete reliability verification."],
            "positive_signals": [],
            "risk_signals": ["Incomplete job record."],
            "checks": {},
            "safety_guidelines": "Exercise caution and do not send payments for job applications.",
        }

    title = (job.get("job_title") or "").strip()
    company = (job.get("employer_name") or job.get("company") or "").strip()
    desc = (job.get("job_description") or "").strip()
    apply_url = (job.get("job_apply_link") or "").strip()
    source = (job.get("source") or "").strip()
    source_lower = source.lower()
    full_text = f"{title} {company} {desc} {apply_url}"

    score = 65  # Neutral baseline
    positive_signals = []
    risk_signals = []
    critical_scam_flags = []

    domain = _extract_domain(apply_url)
    emails = _extract_emails(full_text)

    # -----------------------------------------------------------------------
    # 1. Payment & Financial Safety Check (Zero Tolerance)
    # -----------------------------------------------------------------------
    payment_matches = _check_payment_requests(full_text)
    if payment_matches:
        critical_scam_flags.append(
            f"Suspicious payment or mobile banking request detected: '{', '.join(payment_matches[:3])}'"
        )
        risk_signals.append("Explicitly asks for fee, security money, or mobile banking transfer (bKash/Nagad/fees)")
        score -= 75

    deceptive_matches = _check_deceptive_promises(full_text)
    if deceptive_matches:
        risk_signals.append(f"Deceptive promise detected: '{deceptive_matches[0]}'")
        score -= 30

    payment_passed = len(payment_matches) == 0

    # -----------------------------------------------------------------------
    # 2. Company Information & Brand Impersonation Check
    # -----------------------------------------------------------------------
    claimed_famous = _find_claimed_famous_entity(title, company, desc)
    company_passed = True

    if claimed_famous:
        entity_name, allowed_domains = claimed_famous
        # Check if the apply link domain matches an official domain or trusted ATS
        is_official_domain = any(_domain_matches(domain, d) for d in allowed_domains)
        is_trusted_ats = any(_domain_matches(domain, ats) for ats in TRUSTED_ATS_DOMAINS)
        is_verified_vetted = any(_domain_matches(domain, vp) for vp in VETTED_PLATFORM_DOMAINS)

        # Check contact emails
        uses_free_webmail = any(any(_domain_matches(e.split('@')[-1], m) for m in FREE_WEBMAIL_DOMAINS) for e in emails)

        if not is_official_domain and not is_trusted_ats:
            # Impersonation alert: claims famous brand, but link is untrusted, shortened, or free
            is_suspicious_host = (
                any(_domain_matches(domain, sh) for sh in URL_SHORTENER_DOMAINS) or
                any(_domain_matches(domain, fh) for fh in FREE_HOSTING_DOMAINS) or
                _domain_matches(domain, "forms.gle") or ("docs.google.com" in domain and "forms" in apply_url) or
                uses_free_webmail or
                domain == ""
            )
            if is_suspicious_host or uses_free_webmail:
                critical_scam_flags.append(
                    f"Brand Impersonation Alert: Claims to represent '{entity_name.title()}', "
                    f"but uses an unofficial application channel ({domain or 'free webmail'})"
                )
                risk_signals.append(
                    f"Unverified entity: advertisement uses {entity_name.title()}'s name without an official domain"
                )
                company_passed = False
                score -= 60
            else:
                risk_signals.append(
                    f"Claims association with {entity_name.title()}; verified on third-party portal ({domain})"
                )
                score -= 10
        else:
            positive_signals.append(f"Official enterprise domain verified for {entity_name.title()} ({domain})")
            score += 25
    else:
        # Check for anonymous/vague company names
        if company.lower() in ANONYMOUS_COMPANY_NAMES:
            risk_signals.append("Employer name is confidential or unspecified ('" + company + "')")
            score -= 15
        elif len(company) > 2 and company.lower() not in ["company", "hiring company"]:
            positive_signals.append(f"Named employer profile: {company}")
            score += 10

    # -----------------------------------------------------------------------
    # 3. Application Link & Host Trust Check
    # -----------------------------------------------------------------------
    link_passed = True

    if any(_domain_matches(domain, sh) for sh in URL_SHORTENER_DOMAINS):
        risk_signals.append(f"High-risk URL shortener detected in application link ({domain})")
        link_passed = False
        score -= 30

    if any(_domain_matches(domain, fh) for fh in FREE_HOSTING_DOMAINS):
        risk_signals.append(f"Application link hosted on free public blog platform ({domain})")
        link_passed = False
        score -= 25

    if _domain_matches(domain, "forms.gle") or ("docs.google.com" in domain and "forms" in apply_url):
        # A Google Form isn't automatically a scam for small communities, but flags caution
        risk_signals.append("Application hosted on an unbranded Google Form rather than an official ATS")
        score -= 15

    has_ats_or_official = False
    if any(_domain_matches(domain, ats) for ats in TRUSTED_ATS_DOMAINS):
        positive_signals.append(f"Recognized Enterprise ATS portal verified ({domain})")
        score += 25
        has_ats_or_official = True
    elif any(_domain_matches(domain, vp) for vp in VETTED_PLATFORM_DOMAINS):
        positive_signals.append(f"Direct application on verified job board ({domain})")
        score += 20
        has_ats_or_official = True
    elif claimed_famous and any(_domain_matches(domain, d) for d in allowed_domains):
        has_ats_or_official = True

    is_bdjobs = _domain_matches(domain, "bdjobs.com") or "bdjobs" in source_lower
    if is_bdjobs:
        # BDJobs specific analysis
        if company.lower() in ANONYMOUS_COMPANY_NAMES:
            risk_signals.append("Anonymous/Confidential BDJobs listing; verify credentials at interview")
            score -= 10
        elif not has_ats_or_official:
            # Standard third-party BDJobs post without enterprise ATS:
            # It is not a scam, but it is an Unverified third-party listing
            positive_signals.append("Published on BDJobs regional employment portal")
            risk_signals.append("Third-party job board listing; direct employer institutional domain not confirmed")
            score = min(score, 70)
    elif not has_ats_or_official and not claimed_famous:
        # Check if employer's clean name matches their domain root (e.g. stripe.com for Stripe)
        clean_comp = re.sub(r"[^a-zA-Z0-9]", "", company.lower())
        domain_sld = domain.split(".")[0] if domain else ""
        if len(clean_comp) >= 3 and (clean_comp in domain_sld or domain_sld in clean_comp):
            positive_signals.append(f"Direct corporate website link matches employer name ({domain})")
            score += 15
        else:
            risk_signals.append(f"Third-party or unconfirmed domain ({domain or 'no direct link'}); verify before applying")
            score = min(score, 70)

    # -----------------------------------------------------------------------
    # 4. Contact Channels & Transparency Check
    # -----------------------------------------------------------------------
    contact_passed = True
    if emails:
        has_free_email = any(any(f in e.lower() for f in FREE_WEBMAIL_DOMAINS) for e in emails)
        if has_free_email:
            if claimed_famous:
                contact_passed = False
            else:
                risk_signals.append("Uses public free webmail address (e.g. @gmail.com) for applications")
                score -= 10
        else:
            positive_signals.append(f"Corporate contact email verified ({emails[0]})")
            score += 15

    # Check for WhatsApp/Telegram only contact
    if re.search(r"\b(whatsapp|telegram|imo)\s+only\b", full_text, flags=re.IGNORECASE):
        risk_signals.append("Directs candidates exclusively through instant messaging without a formal portal")
        score -= 20
        contact_passed = False

    # Check description depth
    if len(desc) > 300:
        positive_signals.append("Comprehensive job description with transparent role requirements")
        score += 10
    elif len(desc) < 80 and not positive_signals:
        risk_signals.append("Brief or vague job description with minimal role specifications")
        score -= 10

    # -----------------------------------------------------------------------
    # Final Status & Diagnostic Resolution
    # -----------------------------------------------------------------------
    score = max(5, min(100, score))

    if critical_scam_flags:
        status = STATUS_SUSPICIOUS
        score = min(score, 35)
        label = "Potentially Suspicious"
        icon = "fa-solid fa-triangle-exclamation"
        badge_color = "#DC2626"
        badge_bg = "#FEF2F2"
        badge_border = "#FECACA"
        summary = (
            "Caution: This advertisement contains suspicious indicators "
            "(e.g. payment/bKash requests, brand impersonation, or unverified link)."
        )
    elif (score >= 75 or has_ats_or_official) and not critical_scam_flags and not any("shortener" in r.lower() or "impersonation" in r.lower() or "payment" in r.lower() for r in risk_signals):
        status = STATUS_VERIFIED
        label = "Verified Employer"
        icon = "fa-solid fa-shield-check"
        badge_color = "#059669"
        badge_bg = "#ECFDF5"
        badge_border = "#A7F3D0"
        summary = "Verified legitimate opportunity with confirmed corporate or reputable platform credentials."
    else:
        status = STATUS_UNVERIFIED
        label = "Unverified Listing"
        icon = "fa-solid fa-shield-halved"
        badge_color = "#D97706"
        badge_bg = "#FFFBEB"
        badge_border = "#FDE68A"
        summary = (
            "Standard third-party or emerging business listing. No critical fraud flags detected, "
            "but lacks direct enterprise domain verification."
        )

    # Compile clear reasons list
    reasons = []
    if critical_scam_flags:
        reasons.extend(critical_scam_flags)
    if risk_signals:
        reasons.extend(risk_signals[:3])
    if positive_signals and not critical_scam_flags:
        reasons.extend(positive_signals[:3])
    if not reasons:
        reasons.append("Standard third-party recruitment listing with basic role information.")

    checks = {
        "company_authenticity": {
            "passed": company_passed,
            "label": "Company & Brand Authenticity",
            "details": (
                "Verified company identity and brand legitimacy."
                if company_passed
                else "Unverified company identity or brand impersonation risk."
            ),
        },
        "link_safety": {
            "passed": link_passed,
            "label": "Application Link & Host Trust",
            "details": (
                f"Application URL resides on trusted domain ({domain or 'direct portal'})."
                if link_passed
                else f"Application link uses suspicious or free hosting ({domain})."
            ),
        },
        "payment_safety": {
            "passed": payment_passed,
            "label": "Payment Safety Check",
            "details": (
                "Passed: No suspicious fee, deposit, or bKash/Nagad payment requests detected."
                if payment_passed
                else "FAILED: Detected upfront fee, deposit, or mobile banking payment demand."
            ),
        },
        "contact_transparency": {
            "passed": contact_passed,
            "label": "Contact & Channel Transparency",
            "details": (
                "Application channels follow standard professional protocols."
                if contact_passed
                else "Informal or unofficial contact channels detected."
            ),
        },
    }

    safety_guidelines = (
        "JobSnap Safety Notice: Legitimate employers never charge application fees, "
        "bKash/Nagad deposits, or training charges. Always verify company identity before "
        "sharing sensitive personal or financial information."
    )

    return {
        "status": status,
        "score": score,
        "label": label,
        "icon": icon,
        "badge_color": badge_color,
        "badge_bg": badge_bg,
        "badge_border": badge_border,
        "summary": summary,
        "reasons": reasons,
        "positive_signals": positive_signals,
        "risk_signals": risk_signals,
        "critical_flags": critical_scam_flags,
        "checks": checks,
        "safety_guidelines": safety_guidelines,
    }


def attach_reliability_to_job(job: dict) -> dict:
    """
    Enrich a job dictionary with reliability diagnostic properties.
    Ensures safe idempotent execution.
    """
    if not isinstance(job, dict):
        return job

    reliability = verify_job_reliability(job)
    job["reliability"] = reliability
    job["reliability_status"] = reliability["status"]
    job["reliability_score"] = reliability["score"]
    job["reliability_label"] = reliability["label"]
    job["reliability_icon"] = reliability["icon"]
    job["reliability_color"] = reliability["badge_color"]
    job["reliability_bg"] = reliability["badge_bg"]
    job["reliability_border"] = reliability["badge_border"]
    job["reliability_reasons"] = reliability["reasons"]
    job["reliability_summary"] = reliability["summary"]
    return job


def attach_reliability_batch(jobs: list[dict]) -> list[dict]:
    """Batch attach reliability diagnostics to a list of jobs."""
    for j in jobs:
        attach_reliability_to_job(j)
    return jobs
