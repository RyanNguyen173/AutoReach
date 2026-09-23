import pytest

from autoreach.fetch import Fetcher


class _FakePage:
    def goto(self, url, wait_until=None):
        from playwright.sync_api import Error as PlaywrightError
        raise PlaywrightError("Page.goto: Timeout 30000ms exceeded.\nCall log:\n  - navigating to ...")

    def content(self):
        return "<html></html>"


class _FakeBrowser:
    def new_page(self, user_agent=None):
        return _FakePage()

    def close(self):
        pass


class _FakeChromium:
    def launch(self, executable_path=None):
        return _FakeBrowser()


class _FakePlaywright:
    def __enter__(self):
        self.chromium = _FakeChromium()
        return self

    def __exit__(self, *exc):
        return False


def test_render_timeout_is_a_runtime_error_not_a_crash(tmp_path, monkeypatch):
    """A hung/slow site during --render must be skippable like an HTTP
    error, not an unhandled Playwright exception that kills the whole
    batch run (the real bug: one slow site took down a 233-site batch)."""
    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: _FakePlaywright())

    fetcher = Fetcher(cache_dir=tmp_path, use_cache=False)
    with pytest.raises(RuntimeError, match="Timeout"):
        fetcher.get_html("http://slow-site.test", render=True)
