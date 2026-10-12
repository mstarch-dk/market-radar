"""Builds reports/radar.html and reports/summary.json from local data."""
from __future__ import annotations

import json
import math
from datetime import date, datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader

from . import snapshot, universe
from .config import REPORTS, TEMPLATES, settings, universe_config
from .ingest import load_fred, load_prices, wide
from .signals import momentum, regime, rotation

# Reference palette (dataviz skill) – categorical slots in fixed order + quadrant/status colours.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
QUAD_COLORS = {"Leading": "#008300", "Weakening": "#c98500", "Lagging": "#e34948", "Improving": "#2a78d6", "n/a": "#8a8985"}
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"


# ---------------- charts ----------------

def _layout(fig: go.Figure, title: str, height: int = 360, **kw) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0, "font": {"size": 15, "color": INK}},
        height=height, margin={"l": 48, "r": 16, "t": 48, "b": 36},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Segoe UI, system-ui, sans-serif", "size": 12, "color": INK_2},
        legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right", "yanchor": "bottom"},
        **{"hovermode": "x unified", **kw},
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="outside", tickcolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def _html(fig: go.Figure) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False, "responsive": True})


def chart_lines(series: dict[str, pd.Series], title: str, fmt: str = ".2f", hlines=(), days: int = 365) -> str:
    fig = go.Figure()
    for i, (name, s) in enumerate(series.items()):
        s = s.dropna().iloc[-days:]
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, mode="lines",
                                 line={"width": 2, "color": SERIES[i % len(SERIES)]},
                                 hovertemplate=f"%{{y:{fmt}}}"))
    for y in hlines:
        fig.add_hline(y=y, line={"width": 1, "dash": "dot", "color": "#8a8985"})
    return _html(_layout(fig, title, showlegend=len(series) > 1))


def chart_rrg(ratio: pd.DataFrame, mom: pd.DataFrame, names: dict[str, str], title: str) -> str:
    fig = go.Figure()
    xs = ratio.values[np.isfinite(ratio.values)]
    ys = mom.values[np.isfinite(mom.values)]
    pad = 0.4
    xr = [min(xs.min(), 100) - pad, max(xs.max(), 100) + pad] if xs.size else [97, 103]
    yr = [min(ys.min(), 100) - pad, max(ys.max(), 100) + pad] if ys.size else [97, 103]
    for (q, (x0, x1, y0, y1)) in {
        "Leading": (100, xr[1], 100, yr[1]), "Weakening": (100, xr[1], yr[0], 100),
        "Lagging": (xr[0], 100, yr[0], 100), "Improving": (xr[0], 100, 100, yr[1]),
    }.items():
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, line_width=0,
                      fillcolor=QUAD_COLORS[q], opacity=0.06, layer="below")
        fig.add_annotation(x=x1 if x1 > 100 else x0, y=y1 if y1 > 100 else y0, text=q.upper(), showarrow=False,
                           xanchor="right" if x1 > 100 else "left", yanchor="top" if y1 > 100 else "bottom",
                           font={"size": 11, "color": QUAD_COLORS[q]})
    for t in ratio.columns:
        r, m = ratio[t], mom[t]
        ok = r.notna() & m.notna()
        if not ok.any():
            continue
        r, m = r[ok], m[ok]
        q = rotation.quadrant(r.iloc[-1], m.iloc[-1])
        color = QUAD_COLORS[q]
        fig.add_trace(go.Scatter(x=r.values, y=m.values, mode="lines", line={"width": 1.5, "color": color},
                                 opacity=0.35, hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(
            x=[r.iloc[-1]], y=[m.iloc[-1]], mode="markers+text", text=[names.get(t, t)], textposition="top center",
            textfont={"size": 11, "color": INK_2},
            marker={"size": 10, "color": color, "line": {"width": 2, "color": "#fcfcfb"}}, showlegend=False,
            hovertemplate=f"<b>{names.get(t, t)}</b> ({t})<br>{q}<br>RS-Ratio %{{x:.2f}}<br>RS-Momentum %{{y:.2f}}<extra></extra>"))
    fig.add_hline(y=100, line={"width": 1, "color": "#8a8985"})
    fig.add_vline(x=100, line={"width": 1, "color": "#8a8985"})
    _layout(fig, title, height=520, hovermode="closest")
    fig.update_xaxes(title="RS-Ratio (relative trend) →", range=xr, showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title="RS-Momentum (acceleration) →", range=yr)
    return _html(fig)


# ---------------- helpers ----------------

def _records(df: pd.DataFrame) -> list[dict]:
    def clean(v):
        if isinstance(v, (float, np.floating)) and (math.isnan(v) or math.isinf(v)):
            return None
        if isinstance(v, np.generic):
            return v.item()
        if isinstance(v, (pd.Timestamp, date)):
            return v.isoformat()[:10]
        return v
    return [{k: clean(v) for k, v in row.items()} for row in df.to_dict("records")]


def _pct_vs(dist: pd.DataFrame, row: pd.Series) -> float | None:
    vals = []
    for col in ("r12_1", "r6m", "r3m"):
        d = dist[col].dropna()
        if pd.isna(row[col]) or d.empty:
            return None
        vals.append((d < row[col]).mean())
    return round(100 * sum(vals) / len(vals), 1)


def _fx_to_dkk(closes: pd.DataFrame, ccy: str | None) -> pd.Series | None:
    """DKK per unit of quoted price (pence-quoted GBp includes the /100)."""
    if ccy not in universe.FX_DKK:
        return None
    fx = universe.FX_DKK[ccy]
    if fx is None:
        return pd.Series(1.0, index=closes.index)
    if fx not in closes:
        return None
    return closes[fx].ffill() * (0.01 if ccy == "GBp" else 1.0)


def _vs_shadow(tx: pd.DataFrame, px: pd.Series, fx: pd.Series, bench_dkk: pd.Series) -> tuple[float, float] | None:
    """Return of the open position vs. a shadow ACWI position with identical DKK cash flows.

    Buys put the same DKK amount into ACWI on the same day; sells remove the same fraction from both
    (average-cost method). Returns (position return, shadow return), both in DKK.
    """
    qty = cost = units = 0.0
    for _, t in tx.sort_values("date", kind="stable").iterrows():
        d, q = t["date"], t["quantity"]
        if t["type"] == "SELL":
            if qty <= 1e-9:
                continue
            keep = 1 - min(q, qty) / qty
            qty, cost, units = qty * keep, cost * keep, units * keep
        else:
            if qty <= 1e-9:
                qty = cost = units = 0.0
            amount = q * t["price"] * fx.asof(d)
            qty += q
            cost += amount
            units += amount / bench_dkk.asof(d)
    if qty <= 1e-9 or not np.isfinite(cost) or not np.isfinite(units) or cost <= 0:
        return None
    value = qty * px.iloc[-1] * fx.iloc[-1]
    return value / cost - 1, units * bench_dkk.iloc[-1] / cost - 1


def _me_table(closes, volumes, all_stocks: pd.DataFrame, bench: str, min_history: int) -> pd.DataFrame:
    h = universe.holdings()
    if h.empty:
        return pd.DataFrame()
    m = momentum.metrics(closes, volumes, list(h["symbol"]), min_history)
    df = h.merge(m, left_on="symbol", right_on="ticker", how="left")
    b = closes[bench].dropna()
    rel3 = b.iloc[-1] / b.iloc[-64] - 1
    df["rel_r3m"] = df["r3m"] - rel3
    df["score"] = [_pct_vs(all_stocks, r) if pd.notna(r["last"]) else None for _, r in df.iterrows()]

    ccy = universe.currencies([*df["symbol"], bench])
    bench_dkk = (b * _fx_to_dkk(closes, ccy[bench]).reindex(b.index).ffill()).dropna()
    tx = universe.transactions()
    since, bench_since, since_sell, flags = [], [], [], []
    for _, r in df.iterrows():
        s_ret = b_ret = x_ret = None
        f = []
        if r["status"] == "sold" and pd.notna(r.get("last_sell_price")) and pd.notna(r["last"]):
            x_ret = r["last"] / r["last_sell_price"] - 1
            if not -0.95 < x_ret < 20:
                x_ret = None
        since_sell.append(x_ret)
        if r["status"] == "holding" and pd.notna(r["last"]):
            fx = _fx_to_dkk(closes, ccy.get(r["symbol"]))
            res = _vs_shadow(tx[tx["symbol"] == r["symbol"]], closes[r["symbol"]].dropna(), fx, bench_dkk)                 if fx is not None else None
            if res is None:
                f.append("can't compute return")
            elif not -0.95 < res[0] < 20:  # usually a GBp/GBP (pence vs pounds) mismatch in Yahoo
                f.append("check purchase price units")
            else:
                s_ret, b_ret = res
        since.append(s_ret)
        bench_since.append(b_ret)
        if pd.isna(r["last"]):
            f.append("no data")
        else:
            if pd.notna(r["trend_ok"]) and bool(r["trend_ok"]):
                f.append("trend intact")
            if r["status"] == "holding" and not r["above50"] and r["r1m"] < 0:
                f.append("losing momentum")
            if r["status"] == "holding" and r["above200"] == False:  # noqa: E712 (NaN-safe)
                f.append("below 200d")
            if r["status"] in ("watch", "sold") and r["above50"] and r["r1m"] > 0 and r["rel_r3m"] > 0:
                f.append("turning up")
            if r["from_high"] > -0.03:
                f.append("near 52w high")
        flags.append(f)
    df["since_buy"] = since
    df["bench_since_buy"] = bench_since
    df["since_sell"] = since_sell
    df["flags"] = flags
    # holdings & watchlist by momentum score, sold positions by most recent sale
    sold_date = pd.to_datetime(df["last_sell_date"], errors="coerce")
    df["_o"] = df["status"].map({"holding": 0, "watch": 1, "sold": 2})
    df["_k"] = (-df["score"].astype(float)).where(df["status"] != "sold", -sold_date.astype("int64").astype(float))
    return df.sort_values(["_o", "_k"]).drop(columns=["_o", "_k"])


# ---------------- main ----------------

def build() -> dict:
    cfg = settings()
    ucfg = universe_config()
    bench = universe.benchmark()
    prices = load_prices()
    if prices.empty:
        raise SystemExit("No price data yet – run `radar update` first.")
    closes, volumes = wide(prices, "close"), wide(prices, "volume")
    fred = load_fred()
    today = date.today()
    asof = closes[bench].dropna().index[-1].date()

    # --- regime
    groups = universe.stock_groups()
    labels = universe.stock_group_labels()
    inds, breadth = regime.indicators(closes, fred, bench, groups, labels, universe.macro_yahoo()["VIX"], cfg["regime"])
    overall = regime.overall(inds)
    b = closes[bench].dropna()
    regime_charts = [
        chart_lines({"ACWI": b, "50-day avg": b.rolling(50).mean(), "200-day avg": b.rolling(200).mean()},
                    "Global trend – MSCI ACWI"),
        chart_lines(breadth, "Breadth – % of stocks above their 200-day average", fmt=".0f",
                    hlines=(cfg["regime"]["breadth_weak"], cfg["regime"]["breadth_strong"])),
    ]
    if "BAMLH0A0HYM2" in fred:
        regime_charts.append(chart_lines({"HY spread %": fred["BAMLH0A0HYM2"]}, "US high-yield credit spread (%)"))
    vix = universe.macro_yahoo()["VIX"]
    if vix in closes:
        regime_charts.append(chart_lines({"VIX": closes[vix]}, "Volatility – VIX", fmt=".1f",
                                         hlines=(cfg["regime"]["vix_calm"], cfg["regime"]["vix_stress"])))

    # --- rotation (sectors, regions, themes)
    insts = universe.etfs()
    rc = cfg["rotation"]
    rot = rotation.relative_table(closes, bench, insts, rc["window"], rc["tail"])
    prev_d, prev = snapshot.previous("rotation", cfg["snapshot_min_gap_days"])
    prev_rank = dict(zip(prev["ticker"], prev["rank"])) if prev is not None else {}
    rot["rank_change"] = [prev_rank[t] - r if t in prev_rank else None for t, r in zip(rot["ticker"], rot["rank"])]
    pl = universe.positive_list()
    isins, pl_year = (set(pl["isin"]), pl.attrs["year"]) if pl is not None else (None, None)
    rot["positive_list"] = [universe.positive_list_flag(i, isins) for i in rot["isin"]]

    names = {i.ticker: i.name for i in insts}
    rrg_charts = {}
    for key, g in ucfg["etf_groups"].items():
        tickers = [i.ticker for i in insts if i.group == key and i.ticker in closes.columns]
        ratio, mom = rotation.rrg(closes, bench, tickers, rc["window"], rc["tail"])
        rrg_charts[key] = chart_rrg(ratio, mom, names, f"{g['label']} vs ACWI – last {rc['tail']} weeks")
    group_tables = {key: _records(rot[rot["group"] == key]) for key in ucfg["etf_groups"]}

    # --- momentum
    mc = cfg["momentum"]
    lead = momentum.leaders(closes, volumes, groups, mc["min_history_days"])
    display = universe.names(sorted(set(lead["ticker"]) | set(universe.holdings()["symbol"].dropna())))
    lead["name"] = lead["ticker"].map(display)
    mprev_d, mprev = snapshot.previous("momentum", cfg["snapshot_min_gap_days"])
    top_n = mc["top_n"]
    momentum_tables, entrants, dropped = {}, {}, {}
    for region, df in lead.groupby("region"):
        top = df[df["rank"] <= top_n].copy()
        prev_top = set(mprev[(mprev["group"] == region) & (mprev["rank"] <= top_n)]["ticker"]) if mprev is not None else None
        top["new"] = [prev_top is not None and t not in prev_top for t in top["ticker"]]
        momentum_tables[region] = _records(top)
        entrants[region] = [t for t, n in zip(top["ticker"], top["new"]) if n]
        dropped[region] = sorted(prev_top - set(top["ticker"])) if prev_top is not None else []

    # --- me
    me = _me_table(closes, volumes, lead, bench, mc["min_history_days"])
    if not me.empty:
        me["name"] = me["symbol"].map(display)

    # --- snapshots (after comparing with previous ones)
    snapshot.save("rotation", rot.rename(columns={"rs_score": "score"}), today)
    snapshot.save("momentum", lead, today)

    # --- stale / missing data check
    last_dates = prices.groupby("ticker")["date"].max()
    stale = sorted(t for t, d in last_dates.items() if (pd.Timestamp(asof) - d).days > 7)

    ctx = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "asof": asof.isoformat(),
        "overall": overall, "indicators": inds, "regime_charts": regime_charts,
        "etf_groups": {k: g["label"] for k, g in ucfg["etf_groups"].items()},
        "rrg_charts": rrg_charts, "group_tables": group_tables,
        "rotation_prev": prev_d.isoformat() if prev_d else None,
        "momentum_tables": momentum_tables, "region_labels": labels, "entrants": entrants, "dropped": dropped,
        "momentum_prev": mprev_d.isoformat() if mprev_d else None, "top_n": top_n,
        "me": _records(me) if not me.empty else [], "positive_list_loaded": isins is not None, "stale": stale,
        "positive_list_year": pl_year,
    }

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.filters["pct"] = lambda v, d=1: "–" if v is None else f"{v * 100:+.{d}f}%"
    env.filters["num"] = lambda v, d=2: "–" if v is None else f"{v:,.{d}f}"
    env.filters["sign"] = lambda v: "" if v is None else ("pos" if v > 0 else "neg" if v < 0 else "")
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / "radar.html"
    out.write_text(env.get_template("radar.html.j2").render(**ctx), encoding="utf-8")

    summary = {
        "asof": ctx["asof"], "regime": overall, "indicators": inds,
        "rotation": {
            key: [{k: r[k] for k in ("ticker", "name", "quadrant", "rel_r1m", "rel_r3m", "rel_r6m", "rank", "rank_change", "ucits", "ucits_name", "isin", "positive_list")}
                  for r in rows] for key, rows in group_tables.items()},
        "momentum_top10": {r: [{k: x[k] for k in ("ticker", "name", "score", "r3m", "r6m", "from_high", "new")} for x in rows[:10]]
                           for r, rows in momentum_tables.items()},
        "momentum_new_entrants": entrants, "momentum_dropped_out": dropped,
        "me": [{k: x.get(k) for k in ("symbol", "name", "status", "score", "r1m", "r3m", "rel_r3m", "from_high", "since_buy", "bench_since_buy", "last_sell_date", "since_sell", "flags")}
               for x in ctx["me"]],
        "stale_tickers": stale,
    }
    (REPORTS / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return {"html": str(out), "asof": ctx["asof"], "regime": overall["label"], "stale": len(stale)}
