from pathlib import Path

import pytest

from autoreach.extract import extract_contacts, find_page_links

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def by_email(contacts):
    return {c.email: (c.name, c.title, c.department) for c in contacts}


def test_table_directory():
    got = by_email(extract_contacts(load("table.html"), "https://example.org/staff"))
    assert got == {
        "mdelgado@example.org": ("Maria Delgado", "Principal", "Administration"),
        "jwhitehorse@example.org": ("James Whitehorse", "Assistant Principal", "Administration"),
        "praman@example.org": ("Priya Raman", "Counselor", "Student Services"),
        "dokafor@example.org": ("Dale Okafor", "Social Studies Teacher", "Social Studies"),
        "info@example.org": ("", "", ""),
    }


def test_card_directory():
    got = by_email(extract_contacts(load("cards.html")))
    assert got == {
        "ltsosie@example.org": ("Linda Tsosie", "Superintendent", "District Office"),
        "rchen@example.org": ("Robert Chen", "Director of Human Resources", "Human Resources"),
        "abrookshill@example.org": ("Angela Brooks-Hill", "Student Council Sponsor", ""),
    }


def test_obfuscated_directory():
    got = by_email(extract_contacts(load("obfuscated.html")))
    assert got == {
        "kharjo@example.org": ("Kevin Harjo", "English Teacher", ""),
        "sramirez@example.org": ("Sofia Ramirez", "Math Teacher", ""),
        "mgarcia@example.org": ("Maria Garcia", "Science Teacher", ""),
        "tnguyen@example.org": ("Thanh Nguyen", "Band Director", ""),
    }


def test_apptegy_rendered_directory():
    got = by_email(extract_contacts(load("apptegy_cards.html")))
    assert got == {
        "macosta2@example.org": ("Michelle Acosta", "HQ TA", ""),
        "tadams@example.org": ("Terry Adams", "Director of Aviation Academy", ""),
    }


def test_js_page_has_nothing_without_rendering():
    assert extract_contacts(load("js_rendered.html")) == []


def test_source_url_is_recorded():
    contacts = extract_contacts(load("cards.html"), "https://example.org/staff")
    assert {c.source_url for c in contacts} == {"https://example.org/staff"}


def test_pagination_links_stay_on_site():
    links = find_page_links(load("cards.html"), "https://example.org/staff?const_page=1")
    assert links == ["https://example.org/staff?const_page=2"]


def test_letter_links():
    links = find_page_links(load("obfuscated.html"), "https://example.org/teachers")
    assert links == ["https://example.org/teachers?letter=A", "https://example.org/teachers?letter=B"]


def test_rendered_js_page(tmp_path):
    pytest.importorskip("playwright")
    from autoreach.fetch import Fetcher

    page = tmp_path / "staff.html"
    page.write_text(load("js_rendered.html"), encoding="utf-8")
    try:
        html = Fetcher(cache_dir=tmp_path / "cache")._render(page.as_uri())
    except Exception as e:
        pytest.skip(f"no browser available: {e}")
    got = by_email(extract_contacts(html))
    assert got == {
        "glee@example.org": ("Grace Lee", "Librarian", ""),
        "mbell@example.org": ("Marcus Bell", "Athletic Director", ""),
    }
