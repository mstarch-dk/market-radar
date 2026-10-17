"""The statement items' catalogue (fundamentals/items.py): every item can be read from at least one source, keys
are unique, and every item the scores read exists."""
import re
from pathlib import Path

import radar
from radar.fundamentals import items
from radar.signals import periods


def test_keys_are_unique_and_indexed():
    keys = [i.key for i in items.ITEMS]
    assert len(keys) == len(set(keys)) and set(items.BY_KEY) == set(keys)
    assert {i.key for i in items.ITEMS if i.flow} == items.FLOWS
    assert {i.key for i in items.ITEMS if i.unit == "shares"} == periods.SHARE_COUNTS   # the TTM rule's share counts


def test_every_item_has_a_source_and_a_known_unit():
    for i in items.ITEMS:
        assert i.edgar or i.yahoo, f"{i.key}: neither an EDGAR recipe nor a Yahoo line"
        assert i.unit in ("money", "shares", "per_share"), i.key
        assert not i.outflow or i.flow, f"{i.key}: an outflow is a period's amount"


def test_edgar_tags_are_every_recipes_tags():
    assert items.edgar_tags() == {t for i in items.ITEMS for recipe in i.edgar for t in recipe}
    assert all(t and " " not in t for t in items.edgar_tags())


def test_every_item_the_scores_read_is_in_the_catalogue():
    src = (Path(radar.__file__).parent / "signals" / "fundamentals.py").read_text(encoding="utf-8")
    read = set(re.findall(r"""\b(?:ttm|bal|annual)\(["']([a-z_]+)["']""", src))
    assert read and read <= set(items.BY_KEY), sorted(read - set(items.BY_KEY))
