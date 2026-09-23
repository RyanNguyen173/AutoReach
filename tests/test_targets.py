import pytest

from autoreach.models import Target
from autoreach.targets import load_targets, targets_to_domains


def test_load_targets_minimal_columns(tmp_path):
    csv_path = tmp_path / "targets.csv"
    csv_path.write_text(
        "name,homepage_url\n"
        "Example Elementary,https://www.example-elem.org\n"
        "Example High,https://www.example-hs.org\n",
        encoding="utf-8",
    )
    targets = load_targets(csv_path)
    assert targets == [
        Target(name="Example Elementary", homepage_url="https://www.example-elem.org"),
        Target(name="Example High", homepage_url="https://www.example-hs.org"),
    ]


def test_load_targets_all_columns(tmp_path):
    csv_path = tmp_path / "targets.csv"
    csv_path.write_text(
        "name,homepage_url,district,city,county,source\n"
        "Example Elementary,https://www.example-elem.org,Example Public Schools,Example City,Example County,manual\n",
        encoding="utf-8",
    )
    [target] = load_targets(csv_path)
    assert target == Target(
        name="Example Elementary",
        homepage_url="https://www.example-elem.org",
        district="Example Public Schools",
        city="Example City",
        county="Example County",
        source="manual",
    )


def test_load_targets_skips_rows_with_no_homepage(tmp_path):
    csv_path = tmp_path / "targets.csv"
    csv_path.write_text(
        "name,homepage_url\n"
        "No Website Yet,\n"
        "Has A Website,https://www.example.org\n",
        encoding="utf-8",
    )
    targets = load_targets(csv_path)
    assert [t.name for t in targets] == ["Has A Website"]


def test_load_targets_missing_required_column_raises(tmp_path):
    csv_path = tmp_path / "targets.csv"
    csv_path.write_text("name\nExample Elementary\n", encoding="utf-8")
    with pytest.raises(ValueError, match="homepage_url"):
        load_targets(csv_path)


def test_targets_to_domains_format():
    targets = [
        Target(name="Example Elementary", homepage_url="https://www.example-elem.org"),
        Target(name="Example High", homepage_url="https://www.example-hs.org"),
    ]
    assert targets_to_domains(targets) == (
        "# Example Elementary\n"
        "https://www.example-elem.org\n"
        "# Example High\n"
        "https://www.example-hs.org\n"
    )


def test_targets_to_domains_empty_list():
    assert targets_to_domains([]) == ""
