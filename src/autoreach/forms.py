"""Read a per-person "contact this staff member" form: find its fields and what
they mean, and build the data a submission would send. This module never makes
a network request or submits anything - sending is a deliberate, later step
that needs a person to review the message first.
"""
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

_CAPTCHA_RE = re.compile(r"recaptcha|hcaptcha|turnstile|h-captcha", re.I)
_SKIP_TYPES = {"submit", "button", "image", "reset"}


@dataclass
class FormField:
    name: str  # the real "name" attribute this value is POSTed under
    label: str  # human-readable label or hint text, e.g. "Your First Name"
    kind: str  # "text", "email", "tel", "textarea", "hidden", ...
    required: bool = False
    value: str = ""  # current value; the only one that matters for a hidden field


@dataclass
class ContactForm:
    action: str
    method: str
    fields: list[FormField] = field(default_factory=list)
    has_captcha: bool = False

    def visible_fields(self) -> list[FormField]:
        return [f for f in self.fields if f.kind != "hidden"]


def parse_form(html: str, base_url: str = "") -> ContactForm | None:
    """Describe the first real form on a contact page. Returns None if the page
    has no form (it's just informational, or the form failed to load)."""
    soup = BeautifulSoup(html, "lxml")
    form = soup.find("form")
    if form is None:
        return None

    fields = []
    for el in form.find_all(["input", "textarea", "select"]):
        name = el.get("name")
        kind = el.get("type", "textarea" if el.name == "textarea" else "text").lower()
        if not name or kind in _SKIP_TYPES:
            continue
        fields.append(FormField(
            name=name,
            label=_label_for(el, form) or name,
            kind=kind,
            required=el.has_attr("required") or el.get("data-required", "").lower() == "true",
            value=el.get("value", ""),
        ))

    return ContactForm(
        action=urljoin(base_url, form.get("action") or ""),
        method=(form.get("method") or "get").upper(),
        fields=fields,
        has_captcha=bool(_CAPTCHA_RE.search(html)),
    )


def _label_for(el: Tag, form: Tag) -> str:
    """A field-specific label if one exists; a shared fieldset legend (used by
    grouped fields like first/last name) is only a last resort, since it
    describes the whole group rather than this one field."""
    el_id = el.get("id")
    if el_id and (label := form.find("label", attrs={"for": el_id})):
        return label.get_text(" ", strip=True)
    if hint_id := el.get("aria-labelledby"):
        if hint := form.find(id=hint_id):
            return hint.get_text(" ", strip=True)
    if placeholder := el.get("placeholder"):
        return placeholder
    if fieldset := el.find_parent("fieldset"):
        if legend := fieldset.find("legend"):
            return legend.get_text(" ", strip=True)
    return ""


def build_submission(cform: ContactForm, values: dict[str, str]) -> dict[str, str]:
    """Map `values` (keyed by the human labels parse_form reported) onto this
    form's real field names, and fill in hidden fields with their existing
    default value. Returns the data a POST would send - it does not send it."""
    payload = {}
    for f in cform.fields:
        if f.kind == "hidden":
            payload[f.name] = f.value
            continue
        match = values.get(f.label)
        if match is None:
            match = next((v for k, v in values.items() if k.lower() in f.label.lower()), None)
        if match is not None:
            payload[f.name] = match
    return payload
