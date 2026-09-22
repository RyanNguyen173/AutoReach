from pathlib import Path

import pytest

from autoreach.extract import extract_contacts, find_page_links

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def by_email(contacts):
    return {c.email: (c.name, c.title, c.department) for c in contacts}


def by_form_url(contacts):
    return {c.contact_form_url: (c.name, c.title, c.department) for c in contacts}


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


def test_form_link_directory_has_no_emails():
    contacts = extract_contacts(load("form_links_directory.html"), "https://example.org/staff")
    by_name = {c.name: (c.title, c.email, c.contact_form_url) for c in contacts}
    assert by_name == {
        "Cynthia Decker": (
            "Head Principal", "",
            "https://example.org/fs/form-manager/view/11111111-1111-1111-1111-111111111111",
        ),
        "Lauren Summers": (
            "Principal Secretary (405) 555-4898", "",
            "https://example.org/fs/form-manager/view/22222222-2222-2222-2222-222222222222",
        ),
        "Amber Balderrama": (
            "Senior Principal", "",
            "https://example.org/fs/form-manager/view/33333333-3333-3333-3333-333333333333",
        ),
        "Matthew Stevens": (
            "Junior Principal", "",
            "https://example.org/fs/form-manager/view/44444444-4444-4444-4444-444444444444",
        ),
    }


def test_generic_two_column_layout_doesnt_merge_people():
    got = by_form_url(extract_contacts(load("two_column_merge.html"), "https://example.org/staff"))
    assert got == {
        "https://example.org/fs/form-manager/view/55555555-5555-5555-5555-555555555555": (
            "Dana Ellis", "Math", "",
        ),
        "https://example.org/fs/form-manager/view/66666666-6666-6666-6666-666666666666": (
            "Omar Reyes", "Science", "",
        ),
    }


def test_site_wide_utility_form_links_are_dropped():
    contacts = extract_contacts(load("utility_form_links.html"))
    assert contacts == []


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
