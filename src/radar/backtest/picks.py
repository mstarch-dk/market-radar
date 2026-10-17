"""Hindsight baskets (`radar sim picks`, `/hindsight`): a basket chosen on a past day D from what the radar knew
then, simulated from there into virtual portfolios (never yours) next to ACWI, the score's own top N and random
baskets. Single-date illustrations for inspiration; the evidence is the rolling study (backtest/study.py).

How to use and read it: guide/brugervejledning/scoretest.md (*En kurv valgt på en dag i fortiden*)."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .. import money, performance, simulate, tracked, universe, userstore
from ..config import settings, write_text
from ..jsonsafe import clean as _clean
from ..jsonsafe import dumps
from ..model import panels as mp
from ..model.select import capped
from ..model.stats import cross_section
from ..paths import REPORTS
from ..simulate import basket_rows  # noqa: F401 (re-exported)
from ..userstore import viewstore
from . import exits as ex
from . import study

STRATEGIES = {"hold": "picks-hold", "exits": "picks-exits", "control": "picks-control"}
REPORT_DIR = "sim-picks"
LOOKBACK = re.compile(r"^(\d+)\s*([MY])$", re.I)
BLIND = re.compile(r"^C\d{3,}$")
EPS = 1e-9


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:24] or "basket"


def resolve_asof(spec: str, sessions: pd.DatetimeIndex, fill: str = "next") -> tuple[pd.Timestamp, str | None]:
    """'1M' / '3M' / '6M' / '1Y' back from the latest session, 'today', or a date: the last session on or before
    it. 'today' with fill next is the session before the latest (so the basket can be bought at the latest close)."""
    s = str(spec).strip()
    last = sessions[-1]
    if s.lower() == "today":
        if fill == "next":
            return sessions[-2], f"ranked at the close of {sessions[-2]:%Y-%m-%d}, bought at the latest close ({last:%Y-%m-%d})"
        return last, None
    m = LOOKBACK.match(s)
    if m:
        n, unit = int(m.group(1)), m.group(2).upper()
        target = last - (pd.DateOffset(months=n) if unit == "M" else pd.DateOffset(years=n))
    else:
        target = pd.Timestamp(s)
    before = sessions[sessions <= target]
    if before.empty:
        raise ValueError(f"no prices on or before {target:%Y-%m-%d}")
    return before[-1], None


def _fill(sessions: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp:
    fi = mp.fill_session(sessions, day, (settings().get("backtest") or {}).get("fill", "next"))
    if fi is None:
        raise ValueError(f"no session after {day:%Y-%m-%d} to buy at yet: pick an earlier day (or 'today')")
    return sessions[fi]


# ---------------- candidates ----------------

ranked = mp.ranked


def candidates(market, asof, blind: bool = False, views: bool = False, top: int | None = None,
               model_cutoff: str | None = None, p: mp.Panels | None = None, fund: bool = False) -> dict:
    """The stock universe ranked on D (mp.Panels, row D): score, its components, trend, volatility, close; nothing
    after D. `blind` replaces tickers and names with C001… by rank on D (so the same data gives the same ids), for
    picking on a date before the picker's knowledge cutoff. `views` adds your market views created by D."""
    p = p or mp.panels(market)
    day, note = resolve_asof(asof, p.sessions, (settings().get("backtest") or {}).get("fill", "next"))
    df = ranked(p, day)
    sec = universe.sectors(list(df["ticker"]))
    df["industry"] = df["ticker"].map(sec["industry"])
    names = universe.names(list(df["ticker"]))
    df["name"] = df["ticker"].map(names)
    align = _views_at(market, day, list(df["ticker"])) if views else None
    ft = None
    if fund:                               # K+V, kvalitet and værdi as known on the day (US, SEC EDGAR)
        from .fund import FundPIT

        ft = FundPIT(market).table(day)
    rows = []
    for _, r in df.iterrows():
        if top and len(rows) >= top:
            break
        row = {"id": r["id"], "ticker": None if blind else r["ticker"], "name": None if blind else r["name"],
               **{k: _clean(r[k]) for k in ("rank", "score", "score_region", "r1m", "r3m", "r6m", "r12_1", "from_high",
                                            "trend_ok", "above200", "vol", "group", "sector", "industry", "dkk")}}
        if not blind:
            row["close"] = _clean(r["close"])
        if ft is not None:
            for k in ("qv", "quality", "value"):
                row[k] = _clean(ft.at[r["ticker"], k]) if r["ticker"] in ft.index and k in ft else None
        if align is not None:
            a = align["names"].get(r["ticker"])
            row["views"] = a
        rows.append(row)
    out = {"asof": day.date().isoformat(), "fill": _fill(p.sessions, day).date().isoformat() if day < p.sessions[-1] else None,
           "note": note, "blind": blind, "universe": int(len(df)), "ranked": int(df["score"].notna().sum()),
           "no_price": int(p.m["last"].loc[day].isna().sum()),
           "after_cutoff": _after_cutoff(day, model_cutoff),
           "model_cutoff": model_cutoff,
           "columns": {"score": "momentum score 0-100 (pooled percentile of 12-1, 6- and 3-month returns, as on My holdings)",
                       "score_region": "the same ranked within the stock's region (as on the Momentum page)",
                       "vol": "63-session realised volatility, annualised",
                       "from_high": "close against the 52-week high",
                       "sector": "today's Yahoo sector (not as of D)",
                       "dkk": "false: no DKK rate for its currency, so it can't be bought in a simulation"},
           "caveats": ["Every value is from prices up to the as-of day; sector and industry are today's.",
                       "The universe is today's: names that left it since are missing (survivorship)."],
           "candidates": rows}
    if align is not None:
        out["views"] = align["views"]
    if ft is not None:
        out["columns"] |= {"qv": "K+V 0-100 (mean of kvalitet and værdi), from SEC EDGAR statements filed by the day; "
                                 "US stocks only, ranked among US peers",
                           "quality": "kvalitetsscore 0-100, as known on the day", "value": "værdiscore 0-100, as known on the day"}
        out["fund_scored"] = int(ft["qv"].notna().sum()) if "qv" in ft else 0
        out["caveats"].append("K+V, kvalitet and værdi: US stocks only (SEC EDGAR has filing dates); peers are the US names.")
    return out


def _after_cutoff(day: pd.Timestamp, cutoff: str | None) -> bool | None:
    if not cutoff:
        return None
    end = pd.Period(cutoff, "M").end_time.normalize()
    return bool(day > end)


def _views_at(market, day: pd.Timestamp, tickers: list[str]) -> dict:
    """Your views created by `day`, aligned with prices up to `day` (personal); a view edited after `day` is flagged
    (`edited_after`), since its text may hold hindsight."""
    from .. import market_views as mv
    from ..signals import views as sv
    from ..universe import region_for

    vs = [v for v in viewstore.views() if str(v["created_at"])[:10] <= day.date().isoformat()]
    meta = [{"id": v["id"], "statement": v["statement"], "conviction": v["conviction"], "horizon": v["horizon"],
             "created": str(v["created_at"])[:10], "status_now": v["status"],
             "edited_after": str(v["updated_at"])[:10] > day.date().isoformat()} for v in vs]
    if not vs:
        return {"views": meta, "names": {}}
    sec = universe.sectors(tickers)
    m = pd.DataFrame({"sector": sec["sector"], "industry": sec["industry"],
                      "region": [region_for(t) for t in sec.index], "country": None}, index=sec.index)
    closes = market.closes.loc[:day]
    ctxs = sv.contexts(tickers, m, closes, tracked.benchmark(), sv.view_etfs(vs), mv.ucits_map(), mv.config())
    names = {}
    for t in tickers:
        a = sv.align(ctxs.get(t) or {"ticker": t}, vs, mv.config())
        if a["label"] not in (None, "unrelated"):
            names[t] = {"label": a["label"], "score": _clean(a["score"]),
                        "views": [r["id"] for r in a["views"] if r["label"] != "unrelated"]}
    return {"views": meta, "names": names}


# ---------------- selection ----------------

def select(df: pd.DataFrame, n: int, max_per_sector: int | None = None, max_per_group: int | None = None,
           trend: bool = False, weighting: str = "equal") -> list[dict]:
    """The top `n` by score under the caps (a name without a sector counts as its own sector)."""
    if weighting not in ("equal", "score"):
        raise ValueError("weighting must be equal or score")
    pool = df[df["score"].notna() & df["dkk"].eq(True)]        # a name without a DKK rate can't be bought here
    if trend:
        pool = pool[pool["trend_ok"].eq(True)]
    chosen = capped(list(pool.itertuples(index=False)), n, max_per_sector, max_per_group)
    if not chosen:
        return []
    w = np.ones(len(chosen)) if weighting == "equal" else np.array([r.score for r in chosen], dtype=float)
    w = w / w.sum()
    return [{"ticker": r.ticker, "weight": float(x), "why": f"score {r.score:.0f} (rank {int(r.rank)})"}
            for r, x in zip(chosen, w)]


def random_percentile(pool: pd.DataFrame, ret: pd.Series, n: int, actual: float, max_per_sector=None,
                      max_per_group=None, draws: int = 1000, seed: int = 0) -> dict:
    """Where `actual` sits among `draws` equal-weight random baskets of `n` names from `pool` under the same caps
    (each drawn in a random order, then capped as select does): the share that did worse, ties counted half."""
    pool = pool[pool["ticker"].isin(ret.dropna().index)]
    rows = list(pool.itertuples(index=False))
    if len(rows) < n:
        return {"draws": 0, "percentile": None, "note": "too few names with a return to draw from"}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(draws):
        order = rng.permutation(len(rows))
        b = capped([rows[i] for i in order], n, max_per_sector, max_per_group)
        if len(b) == n:
            vals.append(float(ret.reindex([r.ticker for r in b]).mean()))
    if not vals:
        return {"draws": 0, "percentile": None, "note": "the caps leave no random basket of that size"}
    v = np.array(vals)
    tie = np.isclose(v, actual, rtol=1e-12, atol=1e-12)
    return {"draws": len(v), "seed": seed, "percentile": float(((v < actual) & ~tie).mean() * 100 + tie.mean() * 50),
            "median": float(np.median(v)), "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90))}


# ---------------- the basket ----------------

def _resolve(picks: list[dict], df: pd.DataFrame) -> list[dict]:
    """Picks by ticker or blind id -> tickers with normalised weights; refuses unknown names and duplicates."""
    by_id = dict(zip(df["id"], df["ticker"]))
    known = set(df["ticker"])
    out, seen = [], set()
    for x in picks:
        t = str(x.get("ticker") or x.get("id") or "").strip()
        if BLIND.match(t) and t not in known:
            if t not in by_id:
                raise ValueError(f"{t}: no such candidate id on that day")
            t = by_id[t]
        if t not in known:
            raise ValueError(f"{t}: not in the ranked universe on that day (no price, or not a tracked stock)")
        if t in seen:
            raise ValueError(f"{t} is picked twice")
        seen.add(t)
        w = x.get("weight")
        out.append({"ticker": t, "weight": None if w is None else float(w), "why": x.get("why")})
    if not out:
        raise ValueError("no picks")
    if any(o["weight"] is None for o in out):
        if any(o["weight"] is not None for o in out):
            raise ValueError("give every pick a weight, or none (equal weights)")
        for o in out:
            o["weight"] = 1 / len(out)
    tot = sum(o["weight"] for o in out)
    if tot <= 0 or any(o["weight"] < 0 for o in out):
        raise ValueError("weights must be positive")
    for o in out:
        o["weight"] /= tot
    return out


def portfolio_name(name: str, kind: str) -> str:
    """The simulated portfolio a basket keeps for each run kind (hold, exits, control): "<name> · <kind>"."""
    return f"{name} · {kind}"


def _sim(name: str, kind: str, params: dict, tags: list[str]) -> int:
    pname = portfolio_name(name, kind)
    p = userstore.portfolio_by_name(pname)
    if p:
        if p["origin"] != "sim" or p.get("strategy") != STRATEGIES[kind]:
            raise ValueError(f"there is already a portfolio called {pname} that isn't this basket's simulation")
        userstore.save_portfolio({"params": params, "tags": sorted(set(p["tags"]) | set(tags))}, p["id"])
        return p["id"]
    return simulate.new_sim_portfolio(pname, STRATEGIES[kind], params, tags=tags)


def _ret(c: pd.DataFrame, t: str, f, e) -> float | None:
    if t not in c:
        return None
    a, b = c[t].asof(f), c[t].asof(e)
    return float(b / a - 1) if pd.notna(a) and pd.notna(b) and a > 0 else None


def run(market, asof, picks: list[dict] | None, name: str, capital: float = 100_000.0, meta: dict | None = None,
        end=None, model_cutoff: str | None = None, tags=(), write: bool = True, p: mp.Panels | None = None) -> dict:
    """Simulate a basket picked on `asof` (picks by ticker or blind id; None = the score's own top N from `meta`)
    into three simulated portfolios, and build the report (reports/sim-picks/<slug>.json). One deposit and one buy
    per pick at the fill session's traded close (`backtest.fill`), paying `backtest.fee_bps`: `<name> · hold` (kept),
    `<name> · exits` (the stop/take-profit rule followed, exits parked; exits.replay "rules") and `<name> · control`
    (the score's own top N with the same caps, equal weights). The picks and settings go into the portfolios' params,
    so `rerun` repeats the same basket."""
    meta = dict(meta or {})
    bt = settings().get("backtest") or {}
    fee = money.fee_bps(bt)
    p = p or mp.panels(market)
    fill_mode = bt.get("fill", "next")
    day, note = resolve_asof(asof, p.sessions, fill_mode)
    fday = _fill(p.sessions, day)
    df = ranked(p, day)
    caps = {k: meta.get(k) for k in ("max_per_sector", "max_per_group")}
    n = int(meta.get("n") or (len(picks) if picks else 15))
    control = select(df, n, caps["max_per_sector"], caps["max_per_group"], bool(meta.get("trend")),
                     meta.get("weighting", "equal") if picks is None else "equal")
    mechanical = picks is None
    chosen = control if mechanical else _resolve(picks, df)
    if mechanical:
        meta.setdefault("basis", "score")
    if not chosen:
        raise ValueError("no names to buy (the caps or the trend filter left none)")
    end_ts = p.sessions[p.sessions <= pd.Timestamp(end)][-1] if end else p.sessions[-1]
    if end_ts < fday:
        raise ValueError(f"the end ({end_ts:%Y-%m-%d}) is before the buy ({fday:%Y-%m-%d})")
    weights = {c["ticker"]: c["weight"] for c in chosen}
    rows, problems = basket_rows(market, weights, fday, capital, fee)
    if problems:
        raise ValueError("can't buy the basket: " + "; ".join(problems))
    same_as_control = mechanical or {c["ticker"] for c in control} == set(weights)
    cw = {c["ticker"]: c["weight"] for c in control}
    crow, cprob = basket_rows(market, cw, fday, capital, fee) if not same_as_control else ([], [])

    from .pit import Context

    park = bt.get("park") or tracked.benchmark()
    ctx = Context.build(market, set(weights) | set(cw) | {park})
    rep = ex.replay(rows, ctx, "rules", end=end_ts, fee_bps=fee)

    s = slug(name)
    tags = sorted({"picks", f"picks-{s}"[:32], *(userstore.norm_tag(t) for t in tags)})
    params = {"asof": day.date().isoformat(), "fill": fday.date().isoformat(), "end": end, "capital": capital,
              "picks": chosen, "meta": meta, "model_cutoff": model_cutoff, "fee_bps": fee,
              "fee_model": {"kind": "bps", "bps": fee}, "tags": tags}       # a basket from no account: no broker schedule
    ids = {}
    msg = f"basket of {len(weights)} picked on {day:%Y-%m-%d}"
    runs = [("hold", rows), ("exits", rep["rows"])] + ([("control", crow)] if crow else [])
    for kind, rs in runs:
        pid = _sim(name, kind, params, tags)
        simulate.write_run(pid, STRATEGIES[kind], params, day.date().isoformat(), end_ts.date().isoformat(), rs, market, msg)
        ids[kind] = pid
    cmp = performance.compare(market, list(ids.values()), start=fday.date().isoformat())

    # yardsticks: ACWI, the equal-weight universe, random baskets, the score check of that day
    fi, ei = p.sessions.get_loc(fday), p.sessions.get_loc(end_ts)
    ret_l = p.closes.loc[end_ts] / p.closes.loc[fday] - 1
    ret_d = p.dkk.loc[end_ts] / p.dkk.loc[fday] - 1
    uni = df["ticker"]
    gross = float(sum(w * ret_d.get(t, np.nan) for t, w in weights.items()))
    b = performance.bench_dkk(market)
    acwi = float(b.asof(end_ts) / b.asof(fday) - 1) if len(b) else None
    rnd = random_percentile(df[df["score"].notna()], ret_d, len(weights), gross, caps["max_per_sector"],
                            caps["max_per_group"], int(bt.get("random_baskets", 1000)), seed=_seed(day, len(weights)))
    check = cross_section(df.set_index("ticker")["score"], ret_l.reindex(uni), len(weights),
                                min(int(bt.get("study_min_names", 30)), max(len(df) // 2, 5)))
    per_pick = []
    for c in chosen:
        t = c["ticker"]
        r = df[df["ticker"] == t].iloc[0]
        rd = _clean(ret_d.get(t))
        per_pick.append({"ticker": t, "weight": c["weight"], "why": c.get("why"), "score": _clean(r["score"]),
                         "rank": _clean(r["rank"]), "sector": r["sector"], "group": r["group"],
                         "return_local": _clean(ret_l.get(t)), "return_dkk": rd,
                         "contribution_dkk": c["weight"] * rd if rd is not None else None})
    rows_by = {r["portfolio"]["id"]: r for r in cmp["rows"]}
    value_ret = {kind: performance.return_on_paid_in(rs, market, end_ts) for kind, rs in runs}
    out = {
        "name": name, "slug": s, "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
        "asof": day.date().isoformat(), "fill": fday.date().isoformat(), "end": end_ts.date().isoformat(),
        "sessions": int(ei - fi), "note": note, "capital": capital, "fee_bps": fee, "meta": meta,
        "model_cutoff": model_cutoff, "after_cutoff": _after_cutoff(day, model_cutoff),
        # return_dkk: end value over the capital, every fee included; the Returns page's TWR starts from the value
        # at the close of the buy, after the buying fees
        "portfolios": {k: {"id": v, "name": userstore.get_portfolio(v)["name"], "return_dkk": value_ret[k],
                           "excess_dkk": value_ret[k] - acwi if value_ret[k] is not None and acwi is not None else None,
                           "stats": rows_by.get(v, {}).get("stats")} for k, v in ids.items()},
        "same_as_control": same_as_control,
        "control": control,
        "picks": per_pick,
        "yardsticks": {"acwi_dkk": acwi, "universe_ew_dkk": _clean(ret_d.reindex(uni).mean()),
                       "universe_ew_local": _clean(ret_l.reindex(uni).mean()),
                       "basket_gross_dkk": gross, "random": rnd,
                       "universe_missing_end": int(ret_l.reindex(uni).isna().sum())},
        "score_check": {k: v for k, v in (check or {}).items() if k != "top"} or None,
        "exits": {"summary": ex.summary(rep), "exits": rep["exits"], "events": rep["events"], "pending": rep.get("pending")},
        "compare": cmp,
        "returns_link": f"/returns?pf={','.join(str(v) for v in ids.values())}&from={fday.date().isoformat()}",
        "caveats": [*study.CAVEATS[:3],
                    "One basket over one period is an illustration, not evidence: see `radar study score` for the "
                    "score across every month."]
                   + ([] if _after_cutoff(day, model_cutoff) in (True, None) or meta.get("basis") == "score" else
                      ["Picked on a day before the picker's knowledge cutoff: hindsight can't be ruled out, even blind."]),
    }
    if write:
        d = REPORTS / REPORT_DIR
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{s}.json"
        write_text(f, dumps(out, indent=1))
    return out


def _seed(day: pd.Timestamp, n: int) -> int:
    """The random baskets' seed: fixed by the date and the basket's size, so a rerun draws the same baskets."""
    return int(day.strftime("%Y%m%d")) * 100 + n


def baskets(tag: str | None = None) -> list[dict]:
    """The stored baskets (their hold portfolios), optionally with a tag."""
    t = userstore.norm_tag(tag) if tag else None
    return [p for p in userstore.portfolios() if p["origin"] == "sim" and p.get("strategy") == STRATEGIES["hold"]
            and (t is None or t in p["tags"])]


def find(name: str) -> list[dict]:
    """The stored baskets (their hold portfolios) by basket name, or every basket with a tag ("tag:<tag>")."""
    if name.startswith("tag:"):
        return baskets(name[4:])
    return [h for h in baskets() if h["name"] == portfolio_name(name, "hold")]


def rerun(market, hold: dict, p: mp.Panels | None = None) -> dict:
    """Run a stored basket again on the latest prices, with its own picks and settings."""
    prm = hold.get("params") or {}
    if not prm.get("picks"):
        raise ValueError(f"{hold['name']} has no stored picks")
    name = hold["name"].rsplit(" · ", 1)[0]
    extra = [t for t in prm.get("tags") or [] if t not in ("picks", f"picks-{slug(name)}")]
    return run(market, prm["asof"], [{k: x[k] for k in ("ticker", "weight", "why") if k in x} for x in prm["picks"]],
               name, prm.get("capital", 100_000.0), prm.get("meta"), prm.get("end"), prm.get("model_cutoff"), extra, p=p)
