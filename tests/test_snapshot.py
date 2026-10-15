from datetime import date

import pandas as pd

from radar import paths, snapshot


def test_previous_skips_snapshots_newer_than_the_gap(tmp_path):
    paths.configure(paths.Locations.flat(tmp_path))
    df = pd.DataFrame({"ticker": ["A", "B"], "rank": [1, 2], "score": [0.9, 0.1], "region": "us"})
    for d in ("2026-09-20", "2026-10-06", "2026-10-11"):
        snapshot.save("momentum", df, date.fromisoformat(d))
    snapshot.save("rotation", df.rename(columns={"region": "group"}), date(2026, 10, 12))
    d, prev = snapshot.previous("momentum", 5, today=date(2026, 10, 13))
    assert d == date(2026, 10, 6)                               # newest at least 5 days old, not 11 Oct
    assert prev.columns.tolist() == ["ticker", "rank", "score", "group"] and prev["group"].iloc[0] == "us"
    assert snapshot.previous("momentum", 60, today=date(2026, 10, 13)) == (None, None)
