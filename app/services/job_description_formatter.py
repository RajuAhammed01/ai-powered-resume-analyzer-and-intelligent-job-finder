"""
JobSnap - Job Description Formatter & Layout Beautifier
======================================================
Transforms raw, messy, or inconsistent job descriptions (HTML, Markdown, or plain text)
into clean, responsive, and semantic HTML with proper paragraph spacing, bullet alignment,
heading hierarchies, and wrap-safe layout protection.
"""

import html
import re
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# Common section heading phrases in recruitment postings
HEADING_PATTERNS = [
    r"^(about\s+(us|the\s+company|our\s+team|the\s+role|the\s+position|you))\b",
    r"^(role\s+(overview|summary|description|mission|purpose))\b",
    r"^(job\s+(summary|overview|description|purpose|scope))\b",
    r"^(key\s+)?(responsibilities|duties|accountabilities|deliverables)\b",
    r"^(what\s+you('ll|\s+will)\s+(do|be\s+doing|work\s+on|bring))\b",
    r"^(what\s+we('re|\s+are)\s+looking\s+for)\b",
    r"^(qualifications|requirements|prerequisites|skills\s+(&|and)\s+experience)\b",
    r"^(required\s+(skills|qualifications|experience|competencies))\b",
    r"^(minimum\s+(qualifications|requirements))\b",
    r"^(preferred|nice\s+to\s+have|bonus|desired)\s+(skills|qualifications|experience)?\b",
    r"^(tech\s+stack|technologies|tools\s+used)\b",
    r"^(benefits|perks|compensation|what\s+we\s+offer|why\s+join\s+us)\b",
    r"^(how\s+to\s+apply|application\s+process|selection\s+process)\b",
    r"^(work\s+(location|environment|hours|type|arrangement))\b",
    r"^(education|academic\s+requirements|experience\s+requirements)\b",
    r"^(equal\s+opportunity\s+employer|about\s+diversity)\b",
]

BULLET_REGEX = re.compile(
    r"^[\s\t]*([*•·▪▫–—\-\+✔►]|(\d{1,2}[\.\)]))\s*(.+)",
    re.UNICODE
)

NUMBERED_REGEX = re.compile(
    r"^[\s\t]*(\d{1,2}[\.\)])\s*(.+)",
    re.UNICODE
)


def clean_job_description(raw_content: str) -> str:
    """
    Primary entry point: Takes raw job description string and returns clean,
    accessible, responsive HTML ready for safe template rendering.
    """
    if not raw_content or not isinstance(raw_content, str):
        return (
            '<div class="job-desc-empty">'
            '<i class="fa-solid fa-circle-info" style="margin-right: 0.35rem; color: var(--primary);"></i> '
            'No detailed description provided for this opening.'
            '</div>'
        )

    text = raw_content.strip()
    if not text:
        return (
            '<div class="job-desc-empty">'
            '<i class="fa-solid fa-circle-info" style="margin-right: 0.35rem; color: var(--primary);"></i> '
            'No detailed description provided for this opening.'
            '</div>'
        )

    # Pre-clean broken escaped fragments, truncated tags, zero-width spaces
    text = _pre_clean_raw_text(text)

    # Detect whether the content is primarily HTML or Plain Text/Markdown
    has_html_tags = bool(re.search(r"<(p|div|ul|ol|li|br|h[1-6]|span|b|strong|em|i|table|a)\b", text, re.IGNORECASE))

    if has_html_tags:
        cleaned_html = _format_html_description(text)
    else:
        cleaned_html = _format_plain_description(text)

    # Final wrap in protective responsive container
    return f'<div class="job-description-content">\n{cleaned_html}\n</div>'


def _pre_clean_raw_text(text: str) -> str:
    """
    Strips broken escaped tags (e.g. &lt;span style="..." from truncated scraper feeds),
    trailing cut-off tags, non-breaking spaces, and zero-width artifacts.
    """
    if not text:
        return ""

    # 1. Strip escaped opening/closing tags or fragments like &lt;span style="..." or &lt;/span&gt;
    text = re.sub(r"&lt;/?(span|font|o:p|div|p|style|class|body|html)\b.*?(?:&gt;|>|$)", "", text, flags=re.IGNORECASE)

    # 2. Strip truncated HTML tags at the end of string (e.g. <span style="... without closing quote or bracket)
    text = re.sub(r"<[a-zA-Z0-9_\-]+[^>]*$", "", text)

    # 3. Remove zero width characters and non-breaking spaces
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]+", "", text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")

    return text.strip()


def _format_html_description(html_text: str) -> str:
    """
    Sanitizes, un-styles, and restructures HTML job descriptions.
    Strips destructive inline CSS, un-wraps redundant spans, and standardizes lists/headings.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Remove dangerous or non-content tags
    for tag in soup.find_all([
        "script", "style", "iframe", "object", "embed", "form", "input",
        "button", "meta", "link", "noscript", "svg", "canvas", "o:p", "xml"
    ]):
        tag.decompose()

    # 2. Remove HTML comments
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # 3. Tag classification: Convert Word list paragraphs or pseudo-bullets before stripping classes
    _convert_pseudo_bullet_paragraphs(soup)

    # 4. Strip all inline styles, presentation attributes, and class pollution (Word/Google Docs)
    # This prevents black text in dark mode, oversized fixed margins, and horizontal overflow.
    for tag in soup.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in ("href", "src", "title", "alt", "target", "rel", "class")}

    # 5. Unwrap pointless styling containers like <span> and <font>
    for tag in soup.find_all(["font", "span"]):
        tag.unwrap()

    # 6. Sanitize and enhance links
    for a in soup.find_all("a"):
        href = a.get("href", "").strip()
        if not href or href.startswith(("javascript:", "data:", "file:")):
            a.unwrap()
        else:
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"
            a["class"] = "job-desc-link"

    # 7. Normalize headings (h1 - h6) into clean h4 elements with consistent class
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        h_text = h.get_text(strip=True)
        if not h_text:
            h.decompose()
            continue
        new_h = soup.new_tag("h4")
        new_h["class"] = "job-desc-heading"
        new_h.string = h_text
        h.replace_with(new_h)

    # 8. Convert pseudo-heading paragraphs like <p><strong>Responsibilities:</strong></p> into real headings
    for p in soup.find_all("p"):
        p_text = p.get_text(strip=True)
        if not p_text:
            continue
        strong_child = p.find(["strong", "b"])
        if strong_child and strong_child.get_text(strip=True) == p_text:
            if _is_heading_candidate(p_text):
                new_h = soup.new_tag("h4")
                new_h["class"] = "job-desc-heading"
                new_h.string = p_text.rstrip(":") + ":"
                p.replace_with(new_h)
                continue

        if _is_heading_candidate(p_text):
            new_h = soup.new_tag("h4")
            new_h["class"] = "job-desc-heading"
            new_h.string = p_text.rstrip(":") + ":"
            p.replace_with(new_h)

    # 9. Split paragraphs containing <br> separated bullet lists
    _split_br_bullet_paragraphs(soup)

    # 10. Standardize <ul> and <ol> lists
    for ul in soup.find_all("ul"):
        ul["class"] = "job-desc-list"
        for li in ul.find_all("li", recursive=False):
            li["class"] = "job-desc-item"
            _clean_li_bullet_prefix(li)

    for ol in soup.find_all("ol"):
        ol["class"] = "job-desc-list job-desc-ordered-list"
        for li in ol.find_all("li", recursive=False):
            li["class"] = "job-desc-item"
            _clean_li_bullet_prefix(li)

    # 11. Clean up empty paragraphs, empty headers, and excessive <br>
    for p in soup.find_all("p"):
        p_clean = p.get_text(strip=True)
        if not p_clean and not p.find("img"):
            p.decompose()
        else:
            p["class"] = "job-desc-paragraph"

    for h4 in soup.find_all("h4"):
        if not h4.get_text(strip=True):
            h4.decompose()

    # Wrap tables in responsive container
    for tbl in soup.find_all("table"):
        wrap = soup.new_tag("div")
        wrap["class"] = "table-responsive"
        tbl.wrap(wrap)

    rendered = str(soup).strip()

    # Collapse triple or more <br> to max two
    rendered = re.sub(r"(<br\s*/?>\s*){3,}", "<br><br>", rendered)

    # If the parser emptied everything, fall back to plain text formatting
    if not rendered or rendered in ("<p></p>", "<div></div>"):
        return _format_plain_description(BeautifulSoup(html_text, "html.parser").get_text(separator="\n"))

    return rendered


def _split_br_bullet_paragraphs(soup: BeautifulSoup) -> None:
    """Splits <p> containing <br>-separated bullet lines into proper <ul>/<ol> lists."""
    for p in list(soup.find_all("p")):
        if not p.find("br"):
            continue
        inner_html = "".join(str(c) for c in p.contents)
        parts = [pt.strip() for pt in re.split(r"<br\s*/?>", inner_html, flags=re.IGNORECASE) if pt.strip()]
        if len(parts) <= 1:
            continue

        has_bullet = any(BULLET_REGEX.match(BeautifulSoup(pt, "html.parser").get_text(strip=True)) for pt in parts)
        if not has_bullet:
            continue

        container = soup.new_tag("div")
        p.insert_before(container)
        curr_list = None
        curr_is_num = False

        for part in parts:
            pt_text = BeautifulSoup(part, "html.parser").get_text(strip=True)
            num_m = NUMBERED_REGEX.match(pt_text)
            bull_m = BULLET_REGEX.match(pt_text)

            if num_m:
                if not curr_list or not curr_is_num:
                    curr_list = soup.new_tag("ol")
                    curr_list["class"] = "job-desc-list job-desc-ordered-list"
                    container.append(curr_list)
                    curr_is_num = True
                li = soup.new_tag("li")
                li["class"] = "job-desc-item"
                li.string = num_m.group(2).strip()
                curr_list.append(li)
            elif bull_m:
                if not curr_list or curr_is_num:
                    curr_list = soup.new_tag("ul")
                    curr_list["class"] = "job-desc-list"
                    container.append(curr_list)
                    curr_is_num = False
                li = soup.new_tag("li")
                li["class"] = "job-desc-item"
                li.string = bull_m.group(3).strip()
                curr_list.append(li)
            else:
                curr_list = None
                if _is_heading_candidate(pt_text):
                    h = soup.new_tag("h4")
                    h["class"] = "job-desc-heading"
                    h.string = pt_text.rstrip(":") + ":"
                    container.append(h)
                else:
                    new_p = soup.new_tag("p")
                    new_p["class"] = "job-desc-paragraph"
                    new_p.append(BeautifulSoup(part, "html.parser"))
                    container.append(new_p)

        container.unwrap()
        p.decompose()


def _clean_li_bullet_prefix(li: Tag) -> None:
    """Strip leading literal bullet symbols (*, -, •, ·) from li text to prevent double bullets."""
    if not li.contents:
        return
    first = li.contents[0]
    if isinstance(first, NavigableString):
        cleaned = re.sub(r"^[\s\t]*([*•·▪▫–—\-\+✔►]|(\d{1,2}[\.\)]))\s*", "", str(first))
        first.replace_with(cleaned)


def _is_pseudo_bullet_node(node: Tag) -> tuple[bool, bool, str]:
    """
    Checks if a <p> or <div> represents a list item.
    Returns (is_bullet, is_numbered, clean_text).
    """
    if node.name not in ("p", "div"):
        return False, False, ""

    text = node.get_text(strip=True)
    if not text:
        return False, False, ""

    num_m = NUMBERED_REGEX.match(text)
    if num_m:
        return True, True, num_m.group(2).strip()

    bull_m = BULLET_REGEX.match(text)
    if bull_m:
        return True, False, bull_m.group(3).strip()

    # Check Word MsoListParagraph class or text-indent
    classes = node.get("class") or []
    cls_str = " ".join(classes).lower()
    style_str = (node.get("style") or "").lower()
    if "msolistparagraph" in cls_str or "text-indent: -0.25in" in style_str:
        cleaned = re.sub(r"^[\s\t]*([*•·▪▫–—\-\+✔►]|(\d{1,2}[\.\)]))\s*", "", text)
        return True, False, cleaned.strip()

    return False, False, ""


def _convert_pseudo_bullet_paragraphs(soup: BeautifulSoup) -> None:
    """Finds runs of <p> or <div> that begin with bullet symbols and groups them into clean <ul>."""
    children = list(soup.find_all(["p", "div"], recursive=False))
    i = 0
    while i < len(children):
        child = children[i]
        is_bullet, is_num, item_text = _is_pseudo_bullet_node(child)
        if is_bullet:
            bullet_run = []
            run_is_numbered = is_num
            while i < len(children):
                curr = children[i]
                c_bullet, c_num, c_text = _is_pseudo_bullet_node(curr)
                if c_bullet and (c_num == run_is_numbered or not run_is_numbered):
                    bullet_run.append((curr, c_text))
                    i += 1
                else:
                    break

            if len(bullet_run) >= 1:
                list_tag = soup.new_tag("ol" if run_is_numbered else "ul")
                list_tag["class"] = "job-desc-list" + (" job-desc-ordered-list" if run_is_numbered else "")
                first_node = bullet_run[0][0]
                first_node.insert_before(list_tag)
                for node, clean_content in bullet_run:
                    li = soup.new_tag("li")
                    li["class"] = "job-desc-item"
                    li.string = clean_content
                    list_tag.append(li)
                    node.decompose()
                continue
        i += 1


def _is_heading_candidate(line: str) -> bool:
    """Determines whether a short string represents a section heading."""
    if not line:
        return False
    clean = line.strip().rstrip(":")
    if len(clean) > 65 or len(clean) < 3:
        return False

    clean_lower = clean.lower()
    for pat in HEADING_PATTERNS:
        if re.search(pat, clean_lower):
            return True

    # Standalone uppercase section headers (e.g., "REQUIREMENTS", "DUTIES")
    if clean.isupper() and len(clean.split()) <= 4:
        return True

    # Short title-case phrases ending with colon
    if line.strip().endswith(":") and len(clean.split()) <= 5:
        return True

    return False


def _format_plain_description(raw_text: str) -> str:
    """
    Parses plain text / markdown job descriptions:
    - Normalizes linebreaks and non-breaking spaces
    - Detects headings, lists, links, bold, and paragraphs
    - Converts into semantic HTML
    """
    text = html.unescape(raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]+", "", text)
    text = text.replace("\xa0", " ")

    lines = text.split("\n")
    output_parts = []
    current_list_type = None  # "ul" or "ol"
    current_list_items = []
    current_paragraph = []

    def flush_list():
        nonlocal current_list_type, current_list_items
        if current_list_items:
            tag = "ol" if current_list_type == "ol" else "ul"
            cls = "job-desc-list" + (" job-desc-ordered-list" if tag == "ol" else "")
            items_html = "\n".join(f'  <li class="job-desc-item">{_inline_format(it)}</li>' for it in current_list_items)
            output_parts.append(f'<{tag} class="{cls}">\n{items_html}\n</{tag}>')
            current_list_items = []
            current_list_type = None

    def flush_paragraph():
        nonlocal current_paragraph
        if current_paragraph:
            content = " ".join(current_paragraph).strip()
            if content:
                output_parts.append(f'<p class="job-desc-paragraph">{_inline_format(content)}</p>')
            current_paragraph = []

    for raw_line in lines:
        line = raw_line.strip()

        # Empty line triggers flush of paragraph or list
        if not line:
            flush_paragraph()
            flush_list()
            continue

        # 1. Heading check (markdown # or heading phrases)
        if line.startswith("#"):
            flush_paragraph()
            flush_list()
            heading_text = line.lstrip("#").strip()
            output_parts.append(f'<h4 class="job-desc-heading">{_inline_format(heading_text)}</h4>')
            continue

        if _is_heading_candidate(line):
            flush_paragraph()
            flush_list()
            heading_text = line.rstrip(":") + ":"
            output_parts.append(f'<h4 class="job-desc-heading">{_inline_format(heading_text)}</h4>')
            continue

        # 2. Numbered list check
        num_match = NUMBERED_REGEX.match(line)
        if num_match:
            flush_paragraph()
            if current_list_type and current_list_type != "ol":
                flush_list()
            current_list_type = "ol"
            current_list_items.append(num_match.group(2).strip())
            continue

        # 3. Bullet list check
        bullet_match = BULLET_REGEX.match(line)
        if bullet_match:
            flush_paragraph()
            if current_list_type and current_list_type != "ul":
                flush_list()
            current_list_type = "ul"
            item_text = bullet_match.group(3).strip()
            current_list_items.append(item_text)
            continue

        # 4. Continuation of previous list item if indented
        if current_list_items and (raw_line.startswith("   ") or raw_line.startswith("\t")):
            current_list_items[-1] += " " + line
            continue

        # 5. Regular text paragraph
        flush_list()
        current_paragraph.append(line)

    flush_paragraph()
    flush_list()

    return "\n".join(output_parts)


def _inline_format(text: str) -> str:
    """Converts inline markdown formatting and auto-links URLs safely."""
    if not text:
        return ""

    safe = html.escape(text)

    # 1. Inline code: `code`
    safe = re.sub(r"`([^`]+)`", r'<code class="job-desc-code">\1</code>', safe)

    # 2. Inline bold: **bold** or __bold__
    safe = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", safe)

    # 3. Inline italic: *italic* or _italic_
    safe = re.sub(r"(?<!\*)\*([^\*]+)\*(?!\*)", r"<em>\1</em>", safe)
    safe = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", safe)

    # 4. Auto-link URLs safely
    url_pattern = re.compile(r'(https?://[^\s<>"]+)', re.IGNORECASE)
    safe = url_pattern.sub(r'<a href="\1" class="job-desc-link" target="_blank" rel="noopener noreferrer">\1</a>', safe)

    # 5. Auto-link emails
    email_pattern = re.compile(r'\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b')
    safe = email_pattern.sub(r'<a href="mailto:\1" class="job-desc-link">\1</a>', safe)

    return safe
