# AutoReach
A website that matches you to anything and makes tailored cold emails showing your purpose.

## Status: Phase 1 (contact extractor) + Phase 2 (directory finder)
Give it a staff directory page and it returns a CSV of names, titles, departments and emails.
Give it a homepage instead and it can find the staff directory link for you - heuristically
for free, or with an AI assist on messier pages if you set up a Gemini API key. It has no
web interface yet.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# Optional, for directories that load their staff list with JavaScript:
pip install -e ".[render]" && playwright install chromium
```

### Optional: AI fallback for `find-directory` / `batch`
`find-directory`'s heuristic is deliberately conservative - on a page where nothing looks
confidently like a staff directory, it returns nothing rather than guess wrong. To have it
ask a cheap model (Gemini) as a fallback in that case, set an API key - either in your shell:
```bash
export GEMINI_API_KEY="your-key-here"
```
or in a `.env` file in the project root (already gitignored, so it's never committed):
```
GEMINI_API_KEY=your-key-here
```
With no key set either way, this is a no-op - everything works exactly as before, just
without the fallback. Responses are cached in `.cache/ai/`, so re-running the same page
never costs a second API call. Optionally set `GEMINI_MODEL` to use a different model
(default: `gemini-2.0-flash`).

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

# Some states publish an official directory of every school's principal, or
# every district's superintendent, as a spreadsheet - no scraping needed
autoreach import-state-directory directory.xlsx -o contacts.csv

# Don't know the staff directory URL? Find it from the homepage first
autoreach find-directory https://www.example-schools.org

# A list of homepages -> one combined contacts CSV (finds each site's
# directory itself, via find-directory)
autoreach batch domains.txt -o contacts.csv
```
`domains.txt` is one homepage URL per line; `#`-prefixed lines are comments.

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
