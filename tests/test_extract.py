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


def test_obscure_email_attrs_directory():
    """Blackbaud/myschoolcdn-style directory: no mailto: href or visible
    email text at all - the address is split across data-username/
    data-domain attributes on an empty <a href="#">, reassembled by JS.
    Also covers a first-name/last-name split into separate elements."""
    got = by_email(extract_contacts(load("obscure_email_attrs.html"), "https://example.org/faculty"))
    assert got == {
        "sasha_klein@example.org": ("Sasha Klein", "Upper School Science", ""),
        "devon_park@example.org": ("Devon Park", "Middle School Counselor", ""),
    }


def test_crooked_oak_directory():
    """Real-world regression fixture: a CMS layout not covered elsewhere
    (grid of per-person contact-info boxes, no table/card class names).
    Names, emails etc. are fictionalized; the markup shape is real."""
    got = by_email(extract_contacts(load("crooked_oak_staff.html"), "https://www.crookedoak.org/staff"))
    assert len(got) == 20
    assert got == {
        "aalder@example.org": ("Ava Alder", "COHS Teacher", "Crooked Oak High School"),
        "bbrix@example.org": ("Ben Brix", "COMS Teacher", "Crooked Oak Middle School"),
        "ccarver@example.org": ("Cora Carver", "COHS Teacher", "Crooked Oak High School"),
        "office@example.org": ("Dax Doyle", "COE Reading Specialist", "Central Oak Elementary"),
        "eember@example.org": ("Ella Ember", "2nd Grade Teacher", "Central Oak Elementary"),
        "ffrost@example.org": ("Finn Frost", "COE Para-Professional", "Central Oak Elementary"),
        "ggable@example.org": ("Gwen Gable", "5th Grade Teacher", "Central Oak Elementary"),
        "hhollis@example.org": ("Huck Hollis", "Child Nutrition Director", "Crooked Oak Administration"),
        "iivers@example.org": ("Ivy Ivers", "2nd Grade Teacher", "Central Oak Elementary"),
        "jjuno@example.org": ("Jax Juno", "Math Teacher", "Crooked Oak Middle School"),
        "kknox@example.org": ("Kira Knox", "4th Grade Teacher", "Central Oak Elementary"),
        "llark@example.org": ("Leo Lark", "Special Services Secretary", "Central Oak Elementary"),
        "mmoss@example.org": ("Mira Moss", "COHS Counselor", "Crooked Oak High School"),
        "nnoor@example.org": ("Nash Noor", "High School Science", "Crooked Oak High School"),
        "oosei@example.org": ("Opal Osei", "Athletics Director", "Crooked Oak Administration"),
        "ppryce@example.org": ("Piper Pryce", "5th Grade Teacher", "Central Oak Elementary"),
        "qquill@example.org": ("Quinn Quill", "District Registrar", "Crooked Oak Administration"),
        "rreyes@example.org": ("Ren Reyes", "English Teacher", "Crooked Oak Middle School"),
        "sstark@example.org": ("Sana Stark", "CareerTech Teacher", "Crooked Oak High School"),
        "ttanaka@example.org": ("Theo Tanaka", "COE Counselor", "Central Oak Elementary"),
    }


def test_split_mailto_link_is_one_person():
    """A CMS artifact splits one mailto link's display text across two
    adjacent <a> tags with the identical href. The second fragment's visible
    text can coincidentally look like a different, valid email - it isn't."""
    got = by_email(extract_contacts(load("split_mailto_link.html"), "https://example.org/faculty"))
    assert got == {
        "jellison@example.org": ("Jordan Ellison", "Associate Professor", "Curriculum Studies"),
        "pnair@example.org": ("Priya Nair", "Professor", "Educational Psychology"),
    }


def test_multiline_heading_keeps_name_title_and_department_separate():
    """A heading combines the name and two title/role lines with no
    separate element for each (Name<br>Title<br>Second role line)."""
    got = by_email(extract_contacts(load("multiline_heading.html"), "https://example.org/faculty"))
    assert got == {
        "mvasquez@example.org": (
            "Morgan Vasquez", "Associate Professor Associate Dean of Graduate Studies", "Learning Sciences",
        ),
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
