from datetime import date

import pandas as pd

from radar import paths, snapshot


def _df(rank_of_a=1):
    return pd.DataFrame({"ticker": ["A", "B"], "rank": [rank_of_a, 3 - rank_of_a], "score": [0.9, 0.1], "region": "us"})


def test_previous_skips_snapshots_newer_than_the_gap(tmp_path):
    paths.configure(paths.Locations.flat(tmp_path))
    for d in ("2026-09-20", "2026-10-06", "2026-10-11"):
        snapshot.save("momentum", _df(), date.fromisoformat(d))
    snapshot.save("rotation", _df().rename(columns={"region": "group"}), date(2026, 10, 12))
    d, prev = snapshot.previous("momentum", 5, asof=date(2026, 10, 13))
    assert d == date(2026, 10, 6)                               # newest at least 5 days old, not 11 Oct
    assert prev.columns.tolist() == ["ticker", "rank", "score", "group"] and prev["group"].iloc[0] == "us"
    assert snapshot.previous("momentum", 60, asof=date(2026, 10, 13)) == (None, None)


def test_a_snapshot_is_named_by_its_data_and_never_replaced(tmp_path):
    """A Saturday run stores Friday's data under Friday; a run on unchanged data (an update that failed all week)
    adds nothing, so "change since" never compares a stale rank with itself under a new date."""
    paths.configure(paths.Locations.flat(tmp_path))
    friday = date(2026, 10, 23)
    assert snapshot.save("momentum", _df(rank_of_a=1), friday)
    assert not snapshot.save("momentum", _df(rank_of_a=2), friday)       # the same data's date: kept as it was
    assert [p.name for p in paths.SNAPSHOTS.glob("*")] == ["2026-10-23_momentum.parquet"]
    assert pd.read_parquet(snapshot.path("momentum", friday))["rank"].tolist() == [1, 2]
    # a week of failed updates: the data is still Friday's, so the comparison is still with the week before
    snapshot.save("momentum", _df(), date(2026, 10, 16))
    assert snapshot.previous("momentum", 5, asof=friday)[0] == date(2026, 10, 16)
    assert snapshot.previous("momentum", 5, asof=date(2026, 10, 30))[0] == friday
