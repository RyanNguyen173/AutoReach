import csv
import json
import logging
import sys
from pathlib import Path

import httpx
import typer

from .ai_fallback import find_directory_via_ai
from .crawl import crawl_directory, dedupe, describe_fetch_error, run_batch
from .env import load_dotenv
from .extract import extract_contacts
from .fetch import Fetcher, RobotsDisallowed
from .find_directory import find_directory_link
from .forms import parse_form
from .models import Contact
from .role import filter_by_role
from .state_directory import parse_state_directory

app = typer.Typer(help="AutoReach: find contacts in staff directories.", no_args_is_help=True)

ROLE_OPTION = typer.Option(None, "--role", help="Only keep contacts whose title matches one of these roles (comma-separated, e.g. 'principal,counselor').")
INCLUDE_UNLABELED_OPTION = typer.Option(False, "--include-unlabeled", help="With --role, also keep contacts that have no title at all.")


def _apply_role_filter(contacts: list[Contact], role: str | None, include_unlabeled: bool) -> list[Contact]:
    if not role:
        return contacts
    roles = [r.strip() for r in role.split(",") if r.strip()]
    before = len(contacts)
    contacts = filter_by_role(contacts, roles, include_unlabeled=include_unlabeled)
    typer.echo(f"Role filter ({', '.join(roles)}): kept {len(contacts)} of {before} contact(s).", err=True)
    return contacts


@app.callback()
def main() -> None:
    load_dotenv()


@app.command()
def extract(
    source: str = typer.Argument(..., help="Directory page URL, or a saved .html file."),
    output: Path = typer.Option(None, "-o", "--output", help="CSV file to write (default: print to screen)."),
    pages: int = typer.Option(1, "--pages", help="Follow up to this many directory pages (next / A-Z links)."),
    render: bool = typer.Option(False, "--render", help="Load the page in a browser first, for JavaScript-built pages."),
    delay: float = typer.Option(1.0, "--delay", help="Seconds to wait between requests to the same site."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Download pages again instead of using saved copies."),
    cache_dir: Path = typer.Option(Path(".cache/html"), "--cache-dir"),
    role: str = ROLE_OPTION,
    include_unlabeled: bool = INCLUDE_UNLABELED_OPTION,
) -> None:
    """Pull names, titles, departments and emails from a staff directory page."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    if Path(source).is_file():
        contacts = extract_contacts(Path(source).read_text(encoding="utf-8"), source)
        fetched = 1
    else:
        fetcher = Fetcher(cache_dir=cache_dir, delay=delay, use_cache=not no_cache)
        contacts, skips, fetched = crawl_directory(fetcher, source, pages=pages, render=render)
        for msg in skips:
            typer.echo(f"Skipped: {msg}", err=True)
        typer.echo(f"Downloaded {fetcher.requests_made} page(s); the rest came from the cache.", err=True)

    contacts = dedupe(contacts)
    contacts = _apply_role_filter(contacts, role, include_unlabeled)

    out = output.open("w", newline="", encoding="utf-8") if output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=Contact.columns())
        writer.writeheader()
        writer.writerows(c.row() for c in contacts)
    finally:
        if output:
            out.close()

    unnamed = sum(1 for c in contacts if not c.name)
    form_only = sum(1 for c in contacts if not c.email and c.contact_form_url)
    typer.echo(
        f"Read {fetched} page(s), found {len(contacts)} contact(s), {unnamed} without a name, "
        f"{form_only} reachable only through a contact form (no email shown on the site).",
        err=True,
    )
    if fetched == 0:
        raise typer.Exit(code=1)


@app.command()
def form(
    source: str = typer.Argument(..., help="A contact_form_url from a CSV, or a saved .html file."),
    render: bool = typer.Option(False, "--render", help="Load the page in a browser first, for JavaScript-built pages."),
    delay: float = typer.Option(1.0, "--delay"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    cache_dir: Path = typer.Option(Path(".cache/html"), "--cache-dir"),
) -> None:
    """Show the fields on a "contact this person" form page, so you know what a
    submission needs. This only reads the page - it never fills in or sends
    anything."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    if Path(source).is_file():
        html = Path(source).read_text(encoding="utf-8")
    else:
        fetcher = Fetcher(cache_dir=cache_dir, delay=delay, use_cache=not no_cache)
        try:
            html = fetcher.get_html(source, render=render)
        except RobotsDisallowed as e:
            typer.echo(f"Skipped: {e}", err=True)
            raise typer.Exit(code=1) from None
        except (httpx.HTTPError, RuntimeError) as e:
            typer.echo(f"Skipped: {describe_fetch_error(e, source, render)}", err=True)
            raise typer.Exit(code=1) from None

    cform = parse_form(html, base_url=source)
    if cform is None:
        typer.echo("No <form> found on that page.", err=True)
        raise typer.Exit(code=1)

    typer.echo(json.dumps({
        "action": cform.action,
        "method": cform.method,
        "has_captcha": cform.has_captcha,
        "fields": [
            {"label": f.label, "name": f.name, "kind": f.kind, "required": f.required}
            for f in cform.visible_fields()
        ],
    }, indent=2))

    if cform.has_captcha:
        typer.echo(
            "\nThis form uses CAPTCHA verification. AutoReach does not solve CAPTCHAs, so "
            "this contact will likely need to be filled in and submitted by a person, not "
            "sent automatically.",
            err=True,
        )


@app.command("import-state-directory")
def import_state_directory_cmd(
    source: Path = typer.Argument(..., help="A state education department's directory .xlsx file."),
    output: Path = typer.Option(..., "-o", "--output", help="CSV file to write."),
) -> None:
    """Read a state-published school directory spreadsheet (one principal
    email per school) straight into a contacts CSV. No scraping needed."""
    contacts = parse_state_directory(source, source_url=str(source))

    with output.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=Contact.columns())
        writer.writeheader()
        writer.writerows(c.row() for c in contacts)

    typer.echo(f"Read {source}, wrote {len(contacts)} contact(s) with an email to {output}.", err=True)


@app.command("find-directory")
def find_directory_cmd(
    source: str = typer.Argument(..., help="A school/company homepage URL, or a saved .html file."),
    render: bool = typer.Option(False, "--render", help="Load the page in a browser first, for JavaScript-built pages."),
    delay: float = typer.Option(1.0, "--delay"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    cache_dir: Path = typer.Option(Path(".cache/html"), "--cache-dir"),
) -> None:
    """Find the staff directory page linked from a homepage, so you don't
    have to hunt for the URL yourself before running `extract`."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    if Path(source).is_file():
        html = Path(source).read_text(encoding="utf-8")
        base_url = source
    else:
        fetcher = Fetcher(cache_dir=cache_dir, delay=delay, use_cache=not no_cache)
        try:
            html = fetcher.get_html(source, render=render)
        except RobotsDisallowed as e:
            typer.echo(f"Skipped: {e}", err=True)
            raise typer.Exit(code=1) from None
        except (httpx.HTTPError, RuntimeError) as e:
            typer.echo(f"Skipped: {describe_fetch_error(e, source, render)}", err=True)
            raise typer.Exit(code=1) from None
        base_url = source

    url = find_directory_link(html, base_url)
    if url is None:
        url = find_directory_via_ai(html, base_url)
        if url is not None:
            typer.echo("(heuristic found nothing; used the AI fallback)", err=True)
    if url is None:
        typer.echo("No staff directory link found on that page.", err=True)
        raise typer.Exit(code=1)
    typer.echo(url)


@app.command()
def batch(
    domains: Path = typer.Argument(..., help="A text file of homepage URLs, one per line (# comments allowed)."),
    output: Path = typer.Option(..., "-o", "--output", help="Combined CSV file to write."),
    pages: int = typer.Option(1, "--pages", help="Follow up to this many directory pages per site."),
    render: bool = typer.Option(False, "--render", help="Load pages in a browser first, for JavaScript-built ones."),
    delay: float = typer.Option(1.0, "--delay", help="Seconds to wait between requests to the same site."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Download pages again instead of using saved copies."),
    cache_dir: Path = typer.Option(Path(".cache/html"), "--cache-dir"),
    role: str = ROLE_OPTION,
    include_unlabeled: bool = INCLUDE_UNLABELED_OPTION,
) -> None:
    """Find and extract each site's staff directory, from a list of
    homepages, into one combined CSV. Combines find-directory and extract
    so you don't have to run them one site at a time."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    sites = [
        line for raw in domains.read_text(encoding="utf-8").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    ]
    if not sites:
        typer.echo(f"No URLs found in {domains}.", err=True)
        raise typer.Exit(code=1)

    fetcher = Fetcher(cache_dir=cache_dir, delay=delay, use_cache=not no_cache)
    results = run_batch(sites, fetcher, pages=pages, render=render)

    contacts: list[Contact] = []
    sites_with_contacts = 0
    for r in results:
        for msg in r.skips:
            typer.echo(f"{r.site}: skipped - {msg}", err=True)
        if r.directory_url is None:
            if not r.skips:
                typer.echo(f"{r.site}: no staff directory link found", err=True)
            continue
        contacts.extend(r.contacts)
        if r.contacts:
            sites_with_contacts += 1
        typer.echo(f"{r.site}: {r.directory_url} -> {len(r.contacts)} contact(s)", err=True)

    contacts = dedupe(contacts)
    contacts = _apply_role_filter(contacts, role, include_unlabeled)
    with output.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=Contact.columns())
        writer.writeheader()
        writer.writerows(c.row() for c in contacts)

    typer.echo(
        f"Found directories on {sites_with_contacts} of {len(sites)} site(s), "
        f"wrote {len(contacts)} contact(s) total to {output}.",
        err=True,
    )
