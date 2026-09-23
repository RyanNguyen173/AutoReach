from pathlib import Path

from autoreach.forms import build_submission, parse_form

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_form_reads_labels_and_requiredness():
    cform = parse_form(load("contact_form.html"), base_url="https://example.org/contact/echevarria")
    assert cform is not None
    assert cform.method == "POST"
    # No action attribute on the <form> - submits back to the page it's on.
    assert cform.action == "https://example.org/contact/echevarria"
    assert cform.has_captcha is True

    by_label = {f.label: f for f in cform.visible_fields()}
    assert by_label["Your First Name"].name == "field_first"
    assert by_label["Your First Name"].required is True
    assert by_label["Phone Number"].name == "field_phone"
    assert by_label["Message"].kind == "textarea"

    hidden = [f for f in cform.fields if f.kind == "hidden"]
    assert hidden == [type(hidden[0])(name="submission_uuid", label="submission_uuid", kind="hidden", value="abc123")]


def test_parse_form_without_captcha():
    cform = parse_form(load("contact_form_no_captcha.html"), base_url="https://example.org/contact")
    assert cform.has_captcha is False
    assert cform.action == "https://example.org/send"
    assert [f.name for f in cform.visible_fields()] == ["sender_name", "body"]


def test_no_form_on_page_returns_none():
    assert parse_form("<html><body><p>Nothing here</p></body></html>") is None


def test_build_submission_maps_labels_to_real_field_names():
    cform = parse_form(load("contact_form.html"), base_url="https://example.org/contact/echevarria")
    payload = build_submission(cform, {
        "Your First Name": "Ryan",
        "Your Last Name": "Nguyen",
        "Phone Number": "405-555-0100",
        "Email Address": "ryan@example.org",
        "Message": "Hello, I'd love to connect about the student voice coalition.",
    })
    assert payload == {
        "submission_uuid": "abc123",
        "field_first": "Ryan",
        "field_last": "Nguyen",
        "field_phone": "405-555-0100",
        "field_email": "ryan@example.org",
        "field_message": "Hello, I'd love to connect about the student voice coalition.",
    }


def test_build_submission_skips_unmatched_values():
    cform = parse_form(load("contact_form_no_captcha.html"))
    payload = build_submission(cform, {"Name": "Ryan", "Something else": "ignored"})
    assert payload == {"sender_name": "Ryan"}
