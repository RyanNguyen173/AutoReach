import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

_AT_RE = re.compile(r"\s*[\[\(\{<]\s*at\s*[\]\)\}>]\s*", re.I)
_DOT_RE = re.compile(r"\s*[\[\(\{<]\s*dot\s*[\]\)\}>]\s*", re.I)

# Asset filenames like logo@2x.png look like emails to the regex.
_FILE_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js", "ico", "pdf"}


def deobfuscate(text: str) -> str:
    """Turn 'jdoe [at] school [dot] org' style text into a normal address."""
    return _DOT_RE.sub(".", _AT_RE.sub("@", text))


def decode_cfemail(encoded: str) -> str:
    """Decode a Cloudflare email-protection hex string (first byte is the XOR key)."""
    key = int(encoded[:2], 16)
    return "".join(chr(int(encoded[i:i + 2], 16) ^ key) for i in range(2, len(encoded), 2))


def clean(email: str) -> str | None:
    email = email.strip().strip(".,;:()[]<>\"'").lower()
    if email.startswith("mailto:"):
        email = email[7:]
    email = email.split("?")[0]
    if not EMAIL_RE.fullmatch(email):
        return None
    if email.rsplit(".", 1)[-1] in _FILE_TLDS:
        return None
    return email


def find_emails(text: str) -> list[str]:
    """All distinct emails in text, in order of first appearance."""
    seen: dict[str, None] = {}
    for match in EMAIL_RE.findall(deobfuscate(text)):
        email = clean(match)
        if email:
            seen.setdefault(email)
    return list(seen)
