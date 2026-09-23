"""AI fallback for locating a staff directory when the heuristic can't.

Phase 2's last no-guarantees item: find_directory_link() is deliberately
conservative (it returns None rather than guess on a page like Hale HS's
"Connect with Us", which is indistinguishable from an ordinary contact page
without more context). This asks a cheap model to look at the page's links
and pick, only when that heuristic came up empty, and only when the caller
has configured an API key - with no key set, this is a silent no-op so the
rest of the tool works exactly as before.

Responses are cached to disk (keyed on the exact set of candidate links), so
re-running the same page doesn't cost a second API call.
"""
import hashlib
import json
import logging
import os
import time
from pathlib import Path

import httpx

from .find_directory import candidate_links, find_directory_link

log = logging.getLogger("autoreach")

DEFAULT_MODEL = "gemini-2.0-flash"
_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Google's free tier caps Gemini at 15 requests/minute. A batch run calls
# this once per site with no other pacing, so without a delay here it burns
# through the quota fast and every call after that fails as a 429 - silently,
# since a failed AI call is treated the same as "the model found nothing".
# AUTOREACH_AI_MIN_INTERVAL overrides this for a paid key with a higher limit.
_DEFAULT_MIN_INTERVAL = 4.5
_last_call = 0.0


def _throttle() -> None:
    global _last_call
    min_interval = float(os.environ.get("AUTOREACH_AI_MIN_INTERVAL", _DEFAULT_MIN_INTERVAL))
    elapsed = time.monotonic() - _last_call
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_call = time.monotonic()

_PROMPT = """You are helping find a staff/faculty directory page on a school or \
company website. Below is a numbered list of links found on the homepage, as \
"link text -> URL". Pick the ONE link that most likely leads to a staff or \
faculty directory (a page listing multiple people's names, titles and/or \
emails) - not a single person's bio page, not a general "About" or "Contact" \
page with no roster, not a news article.

Reply with ONLY the URL of your pick, exactly as it appears in the list below, \
and nothing else. If none of the links look like a staff directory, reply with \
exactly: NONE

Links:
{links}
"""


def _cache_key(base_url: str, links: list[tuple[str, str]]) -> str:
    payload = base_url + "\n" + "\n".join(f"{t}\t{u}" for t, u in links)
    return hashlib.sha1(payload.encode()).hexdigest()


def _extract_answer(raw_text: str, valid_urls: set[str]) -> str | None:
    """Pull the model's pick out of its reply. Despite being told to answer
    with ONLY the URL, models often wrap it in a code fence, add a trailing
    period, or preface it with a word or two - so this tries an exact match
    first, then a substring search for one of the *actual* candidate URLs
    (never anything the model might have invented) before giving up."""
    text = raw_text.strip().strip("`").strip()
    if text in valid_urls:
        return text
    if text.upper() == "NONE":
        return None
    found = [u for u in valid_urls if u in text]
    if len(found) == 1:
        return found[0]
    return None


def find_directory_via_ai(
    html: str,
    base_url: str,
    api_key: str | None = None,
    model: str | None = None,
    cache_dir: Path | str = ".cache/ai",
) -> str | None:
    """Ask a cheap model to pick the staff directory link from this page's
    candidate links. Returns None if no API key is configured, the model
    can't tell, or anything about the call fails - this is a best-effort
    fallback, never a hard dependency."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    links = candidate_links(html, base_url)
    if not links:
        return None

    model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    cache_path = Path(cache_dir) / f"{_cache_key(base_url, links)}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached["result"]

    listing = "\n".join(f"{i}. {text or '(no text)'} -> {url}" for i, (text, url) in enumerate(links, 1))
    prompt = _PROMPT.format(links=listing)
    valid_urls = {url for _, url in links}

    result = None
    try:
        _throttle()
        resp = httpx.post(
            _API_URL.format(model=model),
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30.0,
        )
        resp.raise_for_status()
        raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        result = _extract_answer(raw_text, valid_urls)
        if result is None and raw_text.strip().upper() != "NONE":
            log.info("AI fallback: model's answer didn't match a candidate link: %r", raw_text.strip())
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        log.warning("AI fallback failed for %s: %s", base_url, e)
        return None

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"result": result}), encoding="utf-8")
    return result


def find_directory(
    html: str,
    base_url: str,
    api_key: str | None = None,
    model: str | None = None,
    cache_dir: Path | str = ".cache/ai",
) -> str | None:
    """find_directory_link(), falling back to the AI pick only when the
    heuristic comes up empty."""
    url = find_directory_link(html, base_url)
    if url is not None:
        return url
    return find_directory_via_ai(html, base_url, api_key=api_key, model=model, cache_dir=cache_dir)
