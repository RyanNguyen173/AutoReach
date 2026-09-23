from pathlib import Path

from autoreach.state_directory import parse_state_directory

FIXTURE = Path(__file__).parent / "fixtures" / "state_directory.xlsx"


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
