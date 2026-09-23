"""Filter extracted contacts down to the job titles a campaign cares about.

Titles come from messy real-world directory text ("Assistant Principal /
Athletic Director", "9-12 Counselor"), so matching is keyword-based against
canonical role tags rather than exact string equality.
"""
import re

from .models import Contact

_ASSISTANT_PRINCIPAL_KEYWORDS = ["assistant principal", "vice principal", "asst. principal", "asst principal"]

# Canonical role tag -> (title keywords that count as that role, keywords
# that override a match, e.g. "Assistant Principal" contains "principal"
# but should not count as a plain "principal").
ROLE_KEYWORDS: dict[str, tuple[list[str], list[str]]] = {
    "principal": (["principal"], _ASSISTANT_PRINCIPAL_KEYWORDS),
    "assistant principal": (_ASSISTANT_PRINCIPAL_KEYWORDS, []),
    "superintendent": (["superintendent"], []),
    "counselor": (["counselor", "counsellor"], []),
    "teacher": (["teacher"], []),
}


def _title_pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(keyword) + r"\b", re.I)


def matches_role(title: str, role: str) -> bool:
    """Does this title count as the given canonical role tag?"""
    entry = ROLE_KEYWORDS.get(role.strip().lower())
    if entry is None:
        raise ValueError(f"Unknown role {role!r}. Known roles: {', '.join(sorted(ROLE_KEYWORDS))}")
    keywords, excludes = entry
    if any(_title_pattern(kw).search(title) for kw in excludes):
        return False
    return any(_title_pattern(kw).search(title) for kw in keywords)


def filter_by_role(contacts: list[Contact], roles: list[str], include_unlabeled: bool = False) -> list[Contact]:
    """Keep only contacts whose title matches one of the given role tags.

    With include_unlabeled=True, contacts with no title at all (e.g. a
    generic info@ address with no name/title row) are kept too, since
    they can't be excluded on role grounds one way or the other.
    """
    if not roles:
        return contacts
    return [
        c for c in contacts
        if (include_unlabeled and not c.title) or any(matches_role(c.title, r) for r in roles)
    ]
