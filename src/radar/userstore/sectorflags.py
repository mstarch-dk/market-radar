"""Your marks on /sector-etfs' go-to funds in radar.db: a go-to you marked for replacement on the Sector ETFs page
(open), and the funds a later run replaced because of it (resolved). Both are rejected as that sector's go-to: the
next run picks another fund, and no run picks them again until you allow them (the row is deleted). A rejected fund
may still be listed as a peer. The records themselves stay frozen JSON (sector_etfs.py)."""
from __future__ import annotations

from contextlib import closing

from . import connect, exists, timestamp

REASON_MAX = 200


def flags(sector: str | None = None) -> list[dict]:
    """Every mark ([] without a database), oldest first; only one sector's with `sector`."""
    if not exists():
        return []
    with closing(connect()) as con:
        where, args = ("WHERE sector = ?", (sector,)) if sector else ("", ())
        return [dict(r) for r in con.execute(f"SELECT * FROM sector_etf_flags {where} ORDER BY id", args)]


def open_flags() -> dict[str, dict]:
    """Sector → its open mark (the go-to you want replaced and the next run hasn't yet)."""
    return {f["sector"]: f for f in flags() if f["resolved_at"] is None}


def rejected(sector: str) -> dict[str, dict]:
    """ISIN → mark, for every fund rejected as `sector`'s go-to (marked, whether replaced yet or not)."""
    return {f["isin"]: f for f in flags(sector)}


def flag(sector: str, isin: str, reason: str | None = None) -> dict:
    """Mark `isin` as `sector`'s go-to to replace. Marking it again keeps the first date and updates the reason."""
    reason = (reason or "").strip()[:REASON_MAX] or None
    with closing(connect()) as con, con:
        con.execute("INSERT INTO sector_etf_flags (sector, isin, reason, flagged_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(sector, isin) DO UPDATE SET reason = excluded.reason",
                    (sector, isin, reason, timestamp()))
        return dict(con.execute("SELECT * FROM sector_etf_flags WHERE sector = ? AND isin = ?",
                                (sector, isin)).fetchone())


def remove(sector: str, isin: str) -> bool:
    """Undo a mark, or allow a replaced fund as the go-to again. False when there was no such mark."""
    if not exists():
        return False
    with closing(connect()) as con, con:
        return con.execute("DELETE FROM sector_etf_flags WHERE sector = ? AND isin = ?", (sector, isin)).rowcount > 0


def resolve(sector: str, isin: str, record_id: str) -> None:
    """A saved record (`record_id`) picked another go-to for `sector`: the open mark on `isin` is done."""
    with closing(connect()) as con, con:
        con.execute("UPDATE sector_etf_flags SET resolved_at = ?, record_id = ? "
                    "WHERE sector = ? AND isin = ? AND resolved_at IS NULL", (timestamp(), record_id, sector, isin))


def signature() -> tuple:
    """Every mark as a tuple, for a cache key (the app and the MCP server are separate processes)."""
    return tuple((f["id"], f["sector"], f["isin"], f["reason"], f["resolved_at"]) for f in flags())
