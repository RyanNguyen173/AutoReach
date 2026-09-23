"""Read a list of organizations to run `batch` against, and turn it into the
domains.txt format `batch` already consumes.

The list itself (which schools, which homepage URLs) is curated data, not
something this module derives - see data/oklahoma-schools.csv.example for
the expected shape.
"""
import csv
from pathlib import Path

from .models import Target

REQUIRED_COLUMNS = {"name", "homepage_url"}


def load_targets(path: Path) -> list[Target]:
    """Read a targets CSV. Only `name` and `homepage_url` are required;
    `district`, `city`, `county` and `source` are optional and default to
    empty. Rows with no homepage_url are skipped (nothing to run against)."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing required column(s): {', '.join(sorted(missing))}")

        targets = []
        for row in reader:
            homepage_url = (row.get("homepage_url") or "").strip()
            if not homepage_url:
                continue
            targets.append(Target(
                name=(row.get("name") or "").strip(),
                homepage_url=homepage_url,
                district=(row.get("district") or "").strip(),
                city=(row.get("city") or "").strip(),
                county=(row.get("county") or "").strip(),
                source=(row.get("source") or "").strip(),
            ))
        return targets


def targets_to_domains(targets: list[Target]) -> str:
    """Render targets as the domains.txt format `batch` reads: one homepage
    URL per line, with a `# name` comment above each for readability."""
    lines = []
    for t in targets:
        if t.name:
            lines.append(f"# {t.name}")
        lines.append(t.homepage_url)
    return "\n".join(lines) + "\n" if lines else ""
