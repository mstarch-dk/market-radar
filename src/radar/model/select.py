"""Picking the best names under caps, as the hindsight baskets, the random baskets and the A/B test do."""
from __future__ import annotations


def capped(rows: list, n: int, max_sector, max_group) -> list:
    """The first `n` rows (best first) with at most `max_sector` per sector and `max_group` per stock group (None or
    0: no cap). Rows need `ticker`, `sector` and `group`; an unknown sector ("") counts as its own."""
    out: list = []
    sec: dict[str, int] = {}
    grp: dict[str, int] = {}
    for r in rows:
        s = r.sector or f"?{r.ticker}"
        if max_sector and sec.get(s, 0) >= max_sector:
            continue
        if max_group and grp.get(r.group, 0) >= max_group:
            continue
        out.append(r)
        sec[s], grp[r.group] = sec.get(s, 0) + 1, grp.get(r.group, 0) + 1
        if len(out) >= n:
            break
    return out
