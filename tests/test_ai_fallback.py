import httpx

from autoreach import ai_fallback

HOMEPAGE = """
<html><body><nav>
  <a href="https://example.org/about">About</a>
  <a href="https://example.org/connect">Connect with Us</a>
  <a href="https://example.org/donate">Donate</a>
</nav></body></html>
"""


def _fake_response(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": text}]}}]},
        request=httpx.Request("POST", "https://example.org"),
    )


def test_no_api_key_is_a_silent_noop(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(1))

    result = ai_fallback.find_directory_via_ai(HOMEPAGE, "https://example.org", cache_dir=tmp_path)

    assert result is None
    assert calls == []  # never even tried to call out


def test_returns_the_models_pick_when_its_a_real_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _fake_response("https://example.org/connect"))

    result = ai_fallback.find_directory_via_ai(
        HOMEPAGE, "https://example.org", api_key="fake-key", cache_dir=tmp_path,
    )

    assert result == "https://example.org/connect"


def test_model_saying_none_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _fake_response("NONE"))

    result = ai_fallback.find_directory_via_ai(
        HOMEPAGE, "https://example.org", api_key="fake-key", cache_dir=tmp_path,
    )

    assert result is None


def test_hallucinated_url_not_in_candidates_is_rejected(monkeypatch, tmp_path):
    """A URL the model invents (not one of the page's own links) is a sign
    of hallucination, not a real find - never trust it."""
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _fake_response("https://totally-different.example/staff"))

    result = ai_fallback.find_directory_via_ai(
        HOMEPAGE, "https://example.org", api_key="fake-key", cache_dir=tmp_path,
    )

    assert result is None


def test_http_error_is_caught_not_raised(monkeypatch, tmp_path):
    def raise_error(*a, **k):
        raise httpx.HTTPError("boom")
    monkeypatch.setattr(httpx, "post", raise_error)

    result = ai_fallback.find_directory_via_ai(
        HOMEPAGE, "https://example.org", api_key="fake-key", cache_dir=tmp_path,
    )

    assert result is None


def test_result_is_cached_across_calls(monkeypatch, tmp_path):
    calls = []
    def track(*a, **k):
        calls.append(1)
        return _fake_response("https://example.org/connect")
    monkeypatch.setattr(httpx, "post", track)

    first = ai_fallback.find_directory_via_ai(HOMEPAGE, "https://example.org", api_key="fake-key", cache_dir=tmp_path)
    second = ai_fallback.find_directory_via_ai(HOMEPAGE, "https://example.org", api_key="fake-key", cache_dir=tmp_path)

    assert first == second == "https://example.org/connect"
    assert len(calls) == 1  # second call served from cache


def test_combined_find_directory_prefers_heuristic_over_ai(monkeypatch, tmp_path):
    """When the heuristic already finds a confident match, the AI fallback
    should never even be called - it costs money, the heuristic doesn't."""
    strong_html = '<html><body><a href="https://example.org/staff-directory">Staff Directory</a></body></html>'
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(1))

    result = ai_fallback.find_directory(strong_html, "https://example.org", api_key="fake-key", cache_dir=tmp_path)

    assert result == "https://example.org/staff-directory"
    assert calls == []
