"""marketing/ stays consistent: every shot belongs to a feature, every feature has its section and images in the
page, and the demo seed is fictional and dated relative to the build (scripts/marketing.py)."""
import re
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MKT = ROOT / "marketing"
sys.path.insert(0, str(ROOT / "scripts"))
import marketing  # noqa: E402


def _load(name: str) -> dict:
    return yaml.safe_load((MKT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html() -> str:
    return (MKT / "site" / "index.html").read_text(encoding="utf-8")


def test_shots_and_features_point_at_each_other(html):
    shots = {s["id"]: s for s in _load("shots.yaml")["shots"]}
    features = {f["id"]: f for f in _load("features.yaml")["features"]}
    assert len(shots) == len(_load("shots.yaml")["shots"]), "duplicate shot id"
    for s in shots.values():
        assert s["feature"] in features, f"shot {s['id']}: unknown feature {s['feature']}"
        assert s["id"] in features[s["feature"]]["shots"], f"shot {s['id']} not listed under {s['feature']}"
        assert s["path"].startswith("/"), s["id"]
        assert s.get("viewport", "desktop") in marketing.VIEWPORTS
    for f in features.values():
        assert f'id="{f["section"]}"' in html, f"feature {f['id']}: no section {f['section']} in index.html"
        for sid in f["shots"]:
            assert sid in shots, f"feature {f['id']}: unknown shot {sid}"


def test_every_image_in_the_page_has_a_shot(html):
    """The images themselves are local build output (gitignored; `shots` makes them), so only names are checked."""
    used = re.findall(r'src="img/([^"]+)\.png"', html)
    ids = {s["id"] for s in _load("shots.yaml")["shots"]}
    assert used, "no images in index.html"
    for name in used:
        assert name in ids, f"img/{name}.png is not in shots.yaml"
    assert ids <= set(used), f"shots not used in the page: {sorted(ids - set(used))}"


@pytest.mark.parametrize("spec, expected", [("-12mo", date(2025, 10, 14)), ("-8mo", date(2026, 2, 14)),
                                            ("-3w", date(2026, 9, 23)), ("-10d", date(2026, 10, 4)),
                                            ("-1mo", date(2026, 2, 28))])
def test_relative_dates(spec, expected):
    today = date(2026, 3, 31) if spec == "-1mo" else date(2026, 10, 14)  # month ends clamp (31 Mar → 28 Feb)
    assert marketing.months_back(today, spec) == expected


def test_relative_dates_reject_anything_else():
    for bad in ("12mo", "-1y", "2026-01-01", "-mo"):
        with pytest.raises(ValueError):
            marketing.months_back(date(2026, 10, 14), bad)


def test_seed_is_fictional_and_relative():
    seed = _load("demo/seed.yaml")
    names = [p["name"] for p in seed["portfolios"]] + [f["name"] for f in seed.get("forks", [])]
    assert seed["default"] in names
    for p in seed["portfolios"]:
        assert "Demo" in (p.get("note") or ""), f"{p['name']}: say it is a demo in the note"
        for r in p["rows"] + [r for f in seed.get("forks", []) for r in f.get("rows", [])]:
            marketing.months_back(date(2026, 10, 14), r["at"])  # raises on a fixed date
    patterns = ROOT / "notes" / "leak-patterns.txt"
    if patterns.exists():  # local only: the owner's names, accounts and holdings must not be in the demo
        sys.path.insert(0, str(ROOT / "scripts"))
        import publish_public

        text = (MKT / "demo" / "seed.yaml").read_text(encoding="utf-8")
        hits = [p for p in publish_public.leak_patterns() if p.lower() in text.lower()]
        assert not hits, "the demo seed contains a personal pattern (see notes/leak-patterns.txt)"
