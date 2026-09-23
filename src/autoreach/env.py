"""Load a local .env file (GEMINI_API_KEY, etc.) into the environment.

No new dependency for something this small: KEY=VALUE lines, '#' comments,
blank lines ignored. Never overrides a variable already set in the real
environment, so `GEMINI_API_KEY=x autoreach ...` on the command line still
wins over whatever .env says.
"""
import os
from pathlib import Path


def load_dotenv(path: Path | str = ".env") -> None:
    path = Path(path)
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value
