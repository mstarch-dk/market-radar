"""The opt-in check for a new version: silent until switched on, at most once a day, offline is fine."""

import pytest

from conftest import with_settings
from radar import home, manifest, net, updates


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


@pytest.fixture
def checks(tmp_path, monkeypatch):
    home.create(tmp_path / "h", tmp_path / "c")
    with_settings(monkeypatch, updates={"repo": "someone/market-radar"})
    monkeypatch.setattr(manifest, "app_version", lambda: "0.2.0")
    calls = []

    def fake(url, **kw):
        calls.append(url)
        return Resp(200, {"tag_name": "v0.3.0", "html_url": "https://github.com/someone/market-radar/releases/v0.3.0",
                          "published_at": "2026-11-01T10:00:00Z"})
    monkeypatch.setattr(net, "get", fake)
    return calls


def test_nothing_is_asked_until_switched_on(checks):
    assert updates.status() == updates.status() and not updates.status()["enabled"]
    assert checks == []


def test_a_newer_release_is_found_once_a_day(checks):
    updates.set_enabled(True)
    s = updates.status()
    assert s["newer"] and s["latest"] == "v0.3.0" and s["published"] == "2026-11-01"
    assert updates.status()["newer"] and len(checks) == 1                  # cached until tomorrow
    assert checks[0] == "https://api.github.com/repos/someone/market-radar/releases/latest"


def test_offline_is_not_an_error_page(checks, monkeypatch):
    def down(url, **kw):
        raise ConnectionError("offline")
    monkeypatch.setattr(net, "get", down)
    updates.set_enabled(True)
    s = updates.status()
    assert not s["newer"] and "offline" in s["error"]
