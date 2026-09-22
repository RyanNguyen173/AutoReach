import re
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .emails import clean, decode_cfemail, find_emails
from .models import Contact

NAME_KEYS = ("name",)
TITLE_KEYS = ("title", "position", "role", "job")
DEPT_KEYS = ("department", "dept", "location", "school", "building", "subject", "group")

_LABEL_RE = re.compile(r"^(e-?mail|phone|tel|fax|website|contact|send (an )?email|ext\.?)\b\s*:?\s*$", re.I)
_PHONE_RE = re.compile(r"^[\s\d().+\-x:]*\d{3}[\s\d().+\-x:]*$", re.I)
# Every word capitalized, like a real personal name - excludes phrases such
# as "Click here" or generic sentence fragments that would otherwise pass a
# looser check.
_NAME_RE = re.compile(r"^[A-Z][A-Za-z.'\-]*(?:,?\s+[A-Z][A-Za-z.'\-]*){1,4}$")
_PAGE_PARAMS = {"page", "const_page", "pagenumber", "pg", "p"}
_LEADING_PUNCT_RE = re.compile(r"^[,;:\-–—]+\s*")

# Per-person "contact this staff member" links, used by CMSes (Finalsite's
# fs/form-manager is the known case) that route messages through a web form
# and never put the person's real email address in the page at all.
FORM_LINK_RE = re.compile(r"/fs/form-manager/view/[0-9a-f-]{8,}", re.I)

# Site-wide utility links that happen to match FORM_LINK_RE (a general
# "can't find who you need" catch-all form, a records-request form in the
# footer, ...) - these aren't a specific staff member, so they're dropped
# even if a name-shaped heading ends up nearby.
_GENERIC_LINK_NAMES = {
    "click here", "get in touch", "quick links", "contact us", "records request",
    "having trouble", "contact the school", "general inquiries",
}


def extract_contacts(html: str, base_url: str = "") -> list[Contact]:
    soup = _prepare(html)
    counts: dict[int, set[str]] = {}
    contacts = []
    for kind, value, node in _contact_nodes(soup, base_url):
        container = _container(node, counts)
        name, title, dept = _fields(container, node) if container else ("", "", "")
        if kind == "form" and (not name or name.strip().lower() in _GENERIC_LINK_NAMES):
            # A site-wide utility form (no real name found, or a known
            # catch-all like "Click here" / "Get In Touch"), not a person.
            continue
        if kind == "email":
            contacts.append(Contact(email=value, name=name, title=title, department=dept, source_url=base_url))
        else:
            contacts.append(Contact(contact_form_url=value, name=name, title=title, department=dept, source_url=base_url))
    return contacts


def find_page_links(html: str, base_url: str) -> list[str]:
    """Same-site links that look like 'next page' or A-Z letter pages of a directory."""
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(base_url).netloc
    here = urldefrag(base_url)[0]
    found: dict[str, None] = {}
    for a in soup.find_all("a", href=True):
        url = urldefrag(urljoin(base_url, a["href"]))[0]
        parsed = urlparse(url)
        if parsed.netloc != host or url == here or parsed.scheme not in ("http", "https"):
            continue
        text = a.get_text(" ", strip=True).lower()
        params = {k.lower() for k in parse_qs(parsed.query)}
        is_next = text in {"»", "›", ">", ">>"} or text.startswith("next") or "next" in (a.get("rel") or [])
        is_letter = len(text) == 1 and text.isalpha()
        if is_next or is_letter or params & _PAGE_PARAMS:
            found.setdefault(url)
    return list(found)


def _prepare(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for el in soup(["script", "style", "noscript", "template"]):
        el.decompose()
    for el in soup.select("[data-cfemail]"):
        el.replace_with(decode_cfemail(el["data-cfemail"]))
    for a in soup.select('a[href*="/cdn-cgi/l/email-protection#"]'):
        a["href"] = "mailto:" + decode_cfemail(a["href"].split("#", 1)[1])
    return soup


def _contact_nodes(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str, Tag]]:
    """Each distinct (kind, email-or-form-url) with the element it first appears in,
    in page order. kind is "email" or "form"."""
    found: dict[tuple[str, str], Tag] = {}
    for el in soup.descendants:
        if isinstance(el, Tag) and el.name == "a" and el.get("href"):
            href = el["href"]
            if href.lower().startswith("mailto:"):
                if email := clean(href):
                    found.setdefault(("email", email), el)
            elif FORM_LINK_RE.search(href):
                found.setdefault(("form", urljoin(base_url, href)), el)
        elif isinstance(el, NavigableString) and not isinstance(el, Comment):
            for email in find_emails(str(el)):
                found.setdefault(("email", email), el.parent)
    return [(kind, value, node) for (kind, value), node in found.items()]


def _contacts_in(el: Tag, counts: dict[int, set[str]]) -> set[str]:
    """Every email address and contact-form URL found anywhere inside el."""
    key = id(el)
    if key not in counts:
        identifiers = set(find_emails(el.get_text(" ")))
        for a in el.find_all("a", href=True):
            href = a["href"]
            if href.lower().startswith("mailto:"):
                if email := clean(href):
                    identifiers.add(email)
            elif FORM_LINK_RE.search(href):
                identifiers.add(href)
        counts[key] = identifiers
    return counts[key]


def _signature(el: Tag) -> tuple[str, tuple[str, ...]]:
    return el.name, tuple(sorted(el.get("class") or []))


def _is_repeated(el: Tag, counts: dict[int, set[str]]) -> bool:
    """True when a sibling of the same kind also holds an email, i.e. el is one entry in a list."""
    if el.parent is None:
        return False
    sig = _signature(el)
    return any(
        sib is not el and isinstance(sib, Tag) and _signature(sib) == sig and _contacts_in(sib, counts)
        for sib in el.parent.children
    )


def _linked_name_count(el: Tag) -> int:
    """How many <a> tags inside el have name-shaped text. A real one-person
    container has at most one (the contact link itself) - job titles and
    departments are normal text, never wrapped in a link. More than one
    usually means two different people's entries got merged together."""
    return sum(1 for a in el.find_all("a") if looks_like_name(_text(a)))


def _container(node: Tag, counts: dict[int, set[str]]) -> Tag | None:
    """The smallest ancestor that is one person's row or card."""
    best = None
    for anc in [node, *node.parents]:
        if not isinstance(anc, Tag) or anc.name in ("body", "html", "[document]"):
            break
        if len(_contacts_in(anc, counts)) > 1 or len(anc.get_text(" ", strip=True)) > 600:
            break
        # A generic layout wrapper reused across the page (e.g. a two-column
        # row used both for a pair of staff members and for unrelated footer
        # sections) can look "repeated" without actually being a list of
        # people - don't grow into it once it would mix in a second name.
        if best is not None and _linked_name_count(anc) > 1:
            break
        best = anc
        if anc.name == "tr" or _is_repeated(anc, counts):
            return anc
    return best


def _text(el: Tag | None) -> str:
    return " ".join(el.get_text(" ").split()) if el else ""


def looks_like_name(text: str) -> bool:
    return len(text) <= 60 and bool(_NAME_RE.match(text)) and not find_emails(text)


def _by_class(container: Tag, keys: tuple[str, ...], skip: set[int]) -> Tag | None:
    for el in container.find_all(True):
        if id(el) in skip:
            continue
        classes = " ".join(el.get("class") or []).lower()
        if any(k in classes for k in keys):
            text = _text(el)
            if text and len(text) <= 100 and not find_emails(text):
                return el
    return None


def _fields(container: Tag, node: Tag | None = None) -> tuple[str, str, str]:
    if container.name == "tr" and (row := _from_row(container)):
        return row

    used: set[int] = set()
    # A contact link's own text is usually exactly the person's name (e.g. a
    # "click this name to contact them" form link), which is a more reliable
    # signal than scanning headings - those can combine "Name, Title" in one
    # element and accidentally look like a name themselves.
    name_el = node if isinstance(node, Tag) and node.name == "a" and looks_like_name(_text(node)) else None
    if name_el is None:
        name_el = _by_class(container, NAME_KEYS, used)
    if name_el is None or not looks_like_name(_text(name_el)):
        name_el = next(
            (h for h in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"])
             if looks_like_name(_text(h))),
            None,
        )
    if name_el is not None:
        used.update(id(e) for e in [name_el, *name_el.find_all(True)])
    title_el = _by_class(container, TITLE_KEYS, used)
    if title_el is not None:
        used.update(id(e) for e in [title_el, *title_el.find_all(True)])
    dept_el = _by_class(container, DEPT_KEYS, used)

    name, title, dept = _text(name_el), _text(title_el), _text(dept_el)
    taken = {name, title, dept}
    lines = [
        cleaned for raw in container.get_text("\n").split("\n")
        # Strip stray separator punctuation left behind when the name and
        # title shared one element, e.g. "<a>Name</a>, Title" -> ", Title".
        if (cleaned := _LEADING_PUNCT_RE.sub("", " ".join(raw.split())))
        and cleaned not in taken and not find_emails(cleaned)
        and not _LABEL_RE.match(cleaned) and not _PHONE_RE.match(cleaned)
    ]
    if not name and lines and looks_like_name(lines[0]):
        name = lines.pop(0)
    if not name:
        return "", title, dept
    if not title and lines:
        # A job title normally has no digits; a stray office/phone line (e.g.
        # "WHS Junior Office (405) 735-4811") that ends up ahead of it in the
        # markup shouldn't be picked over the real title.
        idx = next((i for i, line in enumerate(lines) if not any(c.isdigit() for c in line)), 0)
        title = lines.pop(idx)
    if not dept and lines:
        dept = lines.pop(0)
    return name, title, dept


def _from_row(tr: Tag) -> tuple[str, str, str] | None:
    table = tr.find_parent("table")
    header_row = table.find("tr") if table else None
    if header_row is None or header_row is tr:
        return None
    headers = [_text(c).lower() for c in header_row.find_all(["th", "td"], recursive=False)]
    cells = [_text(c) for c in tr.find_all(["td", "th"], recursive=False)]

    def cols(*keys: str) -> list[str]:
        return [cells[i] for i, h in enumerate(headers) if i < len(cells) and any(k in h for k in keys)]

    names = [
        cells[i] for i, h in enumerate(headers)
        if i < len(cells) and cells[i] and "name" in h and not any(k in h for k in DEPT_KEYS)
    ]
    if not names:
        return None
    return " ".join(names), " ".join(cols(*TITLE_KEYS)), " ".join(cols(*DEPT_KEYS))
