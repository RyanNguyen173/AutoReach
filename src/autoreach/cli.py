import csv
import logging
import sys
from pathlib import Path

import typer

from .extract import extract_contacts, find_page_links
from .fetch import Fetcher, RobotsDisallowed
from .models import Contact

app = typer.Typer(help="AutoReach: find contacts in staff directories.", no_args_is_help=True)


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
            fetched += 1
            contacts.extend(extract_contacts(html, url))
            queue.extend(u for u in find_page_links(html, url) if u not in seen)
        typer.echo(f"Downloaded {fetcher.requests_made} page(s); the rest came from the cache.", err=True)

    unique: dict[str, Contact] = {}
    for c in contacts:
        unique.setdefault(c.email, c)
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
    typer.echo(f"Read {fetched} page(s), found {len(contacts)} contact(s), {unnamed} without a name.", err=True)
    if fetched == 0:
        raise typer.Exit(code=1)
