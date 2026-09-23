# AutoReach
A website that matches you to anything and makes tailored cold emails showing your purpose.

## Status: Phase 1 prototype (contact extractor)
Give it a staff directory page and it returns a CSV of names, titles, departments and emails.
It uses no AI and has no web interface yet.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# Optional, for directories that load their staff list with JavaScript:
pip install -e ".[render]" && playwright install chromium
```

## Usage
```bash
# One directory page -> CSV
autoreach extract https://www.example-schools.org/staff -o contacts.csv

# Follow "Next" / A-Z / ?page= links, up to 10 pages
autoreach extract https://www.example-schools.org/staff --pages 10 -o contacts.csv

# Page builds its staff list with JavaScript
autoreach extract https://www.example-schools.org/staff --render -o contacts.csv

# A page you saved from your browser (File > Save Page As)
autoreach extract saved_page.html -o contacts.csv

# Some states publish an official directory of every school's principal as a
# spreadsheet - no scraping needed
autoreach import-state-directory directory.xlsx -o contacts.csv
```

What it does:
- Checks `robots.txt` and skips pages it disallows.
- Waits 1 second between requests to the same site (`--delay` changes this).
- Saves downloaded pages in `.cache/html/`, so re-runs download nothing. Use `--no-cache` to refresh.
- Finds emails in `mailto:` links, plain text, `name [at] school [dot] org` text and
  Cloudflare-hidden addresses.
- Matches each email to the name, title and department in the same table row or card.
  Emails with no clear owner (such as `info@`) are still exported, with the name left blank.

## Tests
```bash
pytest
```
The test pages in `tests/fixtures/` are made up (fictional people, `example.org` addresses) and copy
common directory layouts: a table, a card grid, hidden emails, and a JavaScript-built page.

## Roadmap
See the full checklist: https://claude.ai/artifact/5btJtHKbRqecGiAs7Du9mD
