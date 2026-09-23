import pytest

from autoreach.models import Contact
from autoreach.role import filter_by_role, matches_role


def test_matches_role_basic():
    assert matches_role("Principal", "principal")
    assert matches_role("9-12 Counselor", "counselor")
    assert not matches_role("Assistant Principal", "principal")
    assert matches_role("Assistant Principal / Athletic Director", "assistant principal")


def test_matches_role_is_case_insensitive_and_word_bounded():
    assert matches_role("SCHOOL COUNSELOR", "counselor")
    assert not matches_role("Counseling Office Manager", "counselor")


def test_matches_role_unknown_role_raises():
    with pytest.raises(ValueError):
        matches_role("Principal", "not-a-real-role")


def test_filter_by_role_keeps_matching_titles():
    contacts = [
        Contact(name="A", title="Principal"),
        Contact(name="B", title="Assistant Principal"),
        Contact(name="C", title="Superintendent"),
    ]
    kept = filter_by_role(contacts, ["principal"])
    assert [c.name for c in kept] == ["A"]


def test_filter_by_role_multiple_roles():
    contacts = [
        Contact(name="A", title="Principal"),
        Contact(name="B", title="Counselor"),
        Contact(name="C", title="Superintendent"),
    ]
    kept = filter_by_role(contacts, ["principal", "counselor"])
    assert [c.name for c in kept] == ["A", "B"]


def test_filter_by_role_no_roles_returns_everything():
    contacts = [Contact(name="A", title="Principal")]
    assert filter_by_role(contacts, []) == contacts


def test_filter_by_role_include_unlabeled():
    contacts = [
        Contact(name="A", title="Principal"),
        Contact(email="info@example.org", title=""),
    ]
    kept = filter_by_role(contacts, ["principal"], include_unlabeled=True)
    assert len(kept) == 2

    kept = filter_by_role(contacts, ["principal"], include_unlabeled=False)
    assert len(kept) == 1
