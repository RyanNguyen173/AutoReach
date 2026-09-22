from dataclasses import dataclass, fields


@dataclass
class Contact:
    email: str
    name: str = ""
    title: str = ""
    department: str = ""
    source_url: str = ""

    @classmethod
    def columns(cls) -> list[str]:
        return ["name", "title", "department", "email", "source_url"]

    def row(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}
