"""Parse a state education department's staff directory spreadsheet.

Some states (Oklahoma's OSDE, for example) publish an official directory of
every school's principal, already up to date, as an .xlsx download - no
scraping needed. This reads that spreadsheet straight into Contacts.
"""
from pathlib import Path

from openpyxl import load_workbook

from .emails import clean
from .models import Contact

EMAIL_HEADER = "email"
NAME_HEADER = "principal"
SCHOOL_HEADER = "school"
DISTRICT_HEADER = "district"


def _normalize(value: object) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _find_header_row(ws) -> dict[str, int]:
    for row in ws.iter_rows(min_row=1, max_row=20):
        headers = {_normalize(cell.value): cell.column - 1 for cell in row if cell.value}
        if any(EMAIL_HEADER in h for h in headers):
            return headers
    raise ValueError("No header row with an email column found in the first 20 rows.")


def _column(headers: dict[str, int], contains: str) -> int | None:
    for header, idx in headers.items():
        if contains in header:
            return idx
    return None


def parse_state_directory(path: Path, source_url: str = "") -> list[Contact]:
    """Read a school directory .xlsx into one Contact per school with an email."""
    wb = load_workbook(path, data_only=True)
    ws = wb.worksheets[0]

    headers = _find_header_row(ws)
    email_col = _column(headers, EMAIL_HEADER)
    name_col = _column(headers, NAME_HEADER)
    school_col = _column(headers, SCHOOL_HEADER)
    district_col = _column(headers, DISTRICT_HEADER)
    if email_col is None:
        raise ValueError("Could not locate the principal email column.")

    header_row = next(
        r for r, row in enumerate(ws.iter_rows(min_row=1, max_row=20), start=1)
        if any(_normalize(c.value) and EMAIL_HEADER in _normalize(c.value) for c in row)
    )

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
            title="Principal",
            department=department,
            source_url=source_url,
        ))
    return contacts
