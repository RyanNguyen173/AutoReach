from dataclasses import dataclass, fields


@dataclass
class Contact:
    email: str = ""
    name: str = ""
    title: str = ""
    department: str = ""
    contact_form_url: str = ""
    source_url: str = ""

    @classmethod
    def columns(cls) -> list[str]:
        return ["name", "title", "department", "email", "contact_form_url", "source_url"]

    def row(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class Target:
    """An organization worth running find-directory/extract against, before
    any contact has been found - the input to `batch`, not its output."""
    name: str = ""
    homepage_url: str = ""
    district: str = ""
    city: str = ""
    county: str = ""
    source: str = ""

    @classmethod
    def columns(cls) -> list[str]:
        return ["name", "homepage_url", "district", "city", "county", "source"]

    def row(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}
