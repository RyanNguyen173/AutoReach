"""Parse a state education department's staff directory spreadsheet.

Some states (Oklahoma's OSDE, for example) publish official directories of
every school's principal or every district's superintendent, already up to
date, as .xlsx downloads - no scraping needed. This reads either kind of
spreadsheet straight into Contacts, detecting the role (principal,
superintendent, ...) from whichever "<Role>'s Email" column it finds.
"""
import re
from pathlib import Path

from openpyxl import load_workbook

from .emails import clean
from .models import Contact

SCHOOL_HEADER = "school"
DISTRICT_HEADER = "district"

_EMAIL_HEADER_RE = re.compile(r"^(.*?)(?:'s)?\s+email$")


def _normalize(value: object) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _find_header_row(ws) -> tuple[int, dict[str, int]]:
    for row in ws.iter_rows(min_row=1, max_row=20):
        headers = {_normalize(cell.value): cell.column - 1 for cell in row if cell.value}
        if any(h.endswith("email") for h in headers):
            return row[0].row, headers
    raise ValueError("No header row with an email column found in the first 20 rows.")


def _column(headers: dict[str, int], contains: str) -> int | None:
    for header, idx in headers.items():
        if contains in header:
            return idx
    return None


def parse_state_directory(path: Path, source_url: str = "") -> list[Contact]:
    """Read a school or district directory .xlsx into one Contact per row with an email."""
    wb = load_workbook(path, data_only=True)
    ws = wb.worksheets[0]

    header_row, headers = _find_header_row(ws)
    email_header = next(h for h in headers if h.endswith("email"))
    email_col = headers[email_header]

    role_match = _EMAIL_HEADER_RE.match(email_header)
    role = role_match.group(1).strip() if role_match else ""
    title = role.title()
    name_col = _column(headers, role) if role else None
    school_col = _column(headers, SCHOOL_HEADER)
    district_col = _column(headers, DISTRICT_HEADER)

    contacts = []
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        email = clean(str(row[email_col])) if row[email_col] else None
        if not email:
            continue
        name = str(row[name_col]).strip() if name_col is not None and row[name_col] else ""
        school = str(row[school_col]).strip() if school_col is not None and row[school_col] else ""
        district = str(row[district_col]).strip() if district_col is not None and row[district_col] else ""
        department = " / ".join(p for p in (school, district) if p)
        contacts.append(Contact(
            email=email,
            name=name,
            title=title,
            department=department,
            source_url=source_url,
        ))
    return contacts
