import csv
import json
import logging
import sys
from pathlib import Path

import httpx
import typer

from .extract import extract_contacts, find_page_links
from .fetch import Fetcher, RobotsDisallowed
from .find_directory import find_directory_link
from .forms import parse_form
from .models import Contact
from .state_directory import parse_state_directory

app = typer.Typer(help="AutoReach: find contacts in staff directories.", no_args_is_help=True)


def _describe_fetch_error(e: Exception, url: str, render: bool) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        msg = f"HTTP {status} fetching {url}"
        if status in (403, 429) and not render:
            msg += " - the site may be blocking non-browser requests; try again with --render"
        return msg
    return f"Could not fetch {url}: {e}"


@app.callback()
def main() -> None:
    pass


@app.command()
def extract(
    source: str = typer.Argument(..., help="Directory page URL, or a saved .html file."),
    output: Path = typer.Option(None, "-o", "--output", help="CSV file to write (default: print to screen)."),
    pages: int = typer.Option(1, "--pages", help="Follow up to this many directory pages (next / A-Z links)."),
    render: bool = typer.Option(False, "--render", help="Load the page in a browser first, for JavaScript-built pages."),
    delay: float = typer.Option(1.0, "--delay", help="Seconds to wait between requests to the same site."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Download pages again instead of using saved copies."),
    cache_dir: Path = typer.Option(Path(".cache/html"), "--cache-dir"),
) -> None:
    """Pull names, titles, departments and emails from a staff directory page."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    contacts: list[Contact] = []
    fetched = 0
    if Path(source).is_file():
        contacts = extract_contacts(Path(source).read_text(encoding="utf-8"), source)
        fetched = 1
    else:
        fetcher = Fetcher(cache_dir=cache_dir, delay=delay, use_cache=not no_cache)
        queue, seen = [source], set()
        while queue and fetched < pages:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                html = fetcher.get_html(url, render=render)
            except RobotsDisallowed as e:
                typer.echo(f"Skipped: {e}", err=True)
                continue
            except (httpx.HTTPError, RuntimeError) as e:
                typer.echo(f"Skipped: {_describe_fetch_error(e, url, render)}", err=True)
                continue
            fetched += 1
            contacts.extend(extract_contacts(html, url))
            queue.extend(u for u in find_page_links(html, url) if u not in seen)
        typer.echo(f"Downloaded {fetcher.requests_made} page(s); the rest came from the cache.", err=True)

    unique: dict[str, Contact] = {}
    for c in contacts:
        unique.setdefault(c.email or c.contact_form_url, c)
    contacts = list(unique.values())

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
            typer.echo(f"Skipped: {_describe_fetch_error(e, source, render)}", err=True)
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
            typer.echo(f"Skipped: {_describe_fetch_error(e, source, render)}", err=True)
            raise typer.Exit(code=1) from None
        base_url = source

    url = find_directory_link(html, base_url)
    if url is None:
        typer.echo("No staff directory link found on that page.", err=True)
        raise typer.Exit(code=1)
    typer.echo(url)
