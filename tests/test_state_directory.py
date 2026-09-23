from pathlib import Path

from autoreach.state_directory import parse_state_directory

FIXTURE = Path(__file__).parent / "fixtures" / "state_directory.xlsx"
DISTRICT_FIXTURE = Path(__file__).parent / "fixtures" / "district_directory.xlsx"


def test_parses_principal_rows_with_an_email():
    contacts = parse_state_directory(FIXTURE, source_url="https://example.test/directory.xlsx")

    assert len(contacts) == 1
    contact = contacts[0]
    assert contact.name == "Jane Q. Sample"
    assert contact.email == "jane.sample@example-schools.test"
    assert contact.title == "Principal"
    assert contact.department == "Example High School / Example School District"
    assert contact.source_url == "https://example.test/directory.xlsx"


def test_skips_rows_without_an_email():
    contacts = parse_state_directory(FIXTURE)

    names = [c.name for c in contacts]
    assert "John Doe" not in names


def test_detects_superintendent_role_from_district_directory():
    contacts = parse_state_directory(DISTRICT_FIXTURE)

    assert len(contacts) == 1
    contact = contacts[0]
    assert contact.name == "Sam Superintendent"
    assert contact.email == "sam.super@example-schools.test"
    assert contact.title == "Superintendent"
    assert contact.department == "Example School District"
