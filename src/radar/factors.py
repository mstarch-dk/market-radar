"""Long monthly return histories for testing the radar's rules over decades (`radar study longrun`) and for the
proposals' long-run prior: portfolios and factors built by researchers from every listed stock at the time (Kenneth
R. French Data Library, JKP Global Factor Data), so they hold no survivorship bias.

The data rules (formats, excess returns, refresh and guard): docs/data-conventions.md, *Long histories*; the sources
and their terms: DATA_LICENSE.md."""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import guard, net
from .config import settings, write_parquet
from .paths import CACHE

FACTORS_FILE = CACHE / "factors" / "returns.parquet"
FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{file}.zip"
JKP_URL = "https://jkpfactors-data.s3.amazonaws.com/public/%5B{region}%5D_%5B{theme}%5D_%5Bmonthly%5D_%5B{weighting}%5D.zip"
JKP_PF_URL = ("https://jkpfactors-data.s3.amazonaws.com/public/portfolios/"
              "%5B{region}%5D_%5B{characteristic}%5D_%5Bmonthly%5D_%5B{weighting}%5D.zip")
COLUMNS = ["key", "series", "date", "ret", "fetched"]
FRENCH_MISSING = -99.99                 # this or below (-999) marks a missing value


def _cfg() -> dict:
    return settings().get("factors") or {}


# ---------------- Kenneth R. French Data Library ----------------

_MONTH = re.compile(r"^\s*(\d{6})\s*,")


def french_blocks(text: str) -> dict[str, pd.DataFrame]:
    """Every monthly block in one French CSV: {title: frame (month-end index, one column per series, decimals)}.
    A block is a header line starting with "," followed by rows dated YYYYMM; its title is the last text line before
    the header ("" when there is none). Annual blocks (YYYY) are skipped."""
    lines = text.splitlines()
    out: dict[str, pd.DataFrame] = {}
    title = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith(",") and i + 1 < len(lines) and _MONTH.match(lines[i + 1]):
            cols = [c.strip() for c in line.split(",")[1:]]
            rows = []
            i += 1
            while i < len(lines) and _MONTH.match(lines[i]):
                rows.append([v.strip() for v in lines[i].split(",")])
                i += 1
            idx = pd.PeriodIndex([r[0] for r in rows], freq="M").to_timestamp(how="end").normalize()
            vals = pd.DataFrame([r[1:len(cols) + 1] for r in rows], index=idx, columns=cols)
            vals = vals.apply(pd.to_numeric, errors="coerce")
            vals = vals.mask(vals <= FRENCH_MISSING) / 100       # -99.99 and -999: missing, never a return
            out.setdefault(title, vals)
            continue
        if line.strip() and not _MONTH.match(line):
            title = line.strip()
        i += 1
    return out


def parse_french(blob: bytes, block: str | None = None) -> pd.DataFrame:
    """The block whose title contains `block` (case-insensitive), or the first monthly block, from a French ZIP."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("no CSV in the French ZIP: has the format changed?")
        text = z.read(names[0]).decode("latin-1")
    blocks = french_blocks(text)
    if block:
        hits = [t for t in blocks if block.lower() in t.lower()]
        if not hits:
            raise ValueError(f"no block titled {block!r} in {names[0]} (found: {', '.join(map(repr, blocks)) or 'none'})")
        df = blocks[hits[0]]
    elif blocks:
        df = next(iter(blocks.values()))
    else:
        df = pd.DataFrame()
    if df.empty or df.notna().sum().sum() == 0:
        raise ValueError(f"no monthly returns in {names[0]}: has the format changed?")
    return df


# ---------------- JKP Global Factor Data ----------------

def parse_jkp(blob: bytes, series_col: str = "location", name: str | None = None) -> pd.DataFrame:
    """A JKP ZIP (one long CSV: location, name, date, ret, …) → wide, one column per `series_col` value (the
    country for market returns, the theme name for factors). `name` keeps only that factor."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("no CSV in the JKP ZIP: has the format changed?")
        csv = pd.read_csv(z.open(names[0]))
    need = {"date", "ret", series_col}
    if not need <= set(csv.columns):
        raise ValueError(f"JKP file {names[0]} lacks {', '.join(sorted(need - set(csv.columns)))}: has the format changed?")
    if name is not None and "name" in csv:
        csv = csv[csv["name"] == name]
    csv = csv.assign(date=pd.to_datetime(csv["date"]).dt.to_period("M").dt.to_timestamp(how="end").dt.normalize(),
                     ret=pd.to_numeric(csv["ret"], errors="coerce"))
    dupes = csv.duplicated(["date", series_col])
    if dupes.any():
        raise ValueError(f"{int(dupes.sum())} duplicate {series_col}/month rows in {names[0]}: the file mixes series")
    df = csv.pivot(index="date", columns=series_col, values="ret").sort_index()
    if df.empty or df.notna().sum().sum() == 0:
        raise ValueError(f"no returns in {names[0]}: has the format changed?")
    # portfolio numbers arrive as floats (1.0, 2.0, 3.0): stored as "1", "2", "3"
    df.columns = [str(int(c)) if series_col == "pf" else str(c) for c in df.columns]
    return df


# ---------------- storage ----------------

def _long(key: str, wide: pd.DataFrame, fetched: date) -> pd.DataFrame:
    s = wide.rename_axis(index="date", columns="series").stack().rename("ret").reset_index()   # drops NaN
    s.insert(0, "key", key)
    s["fetched"] = pd.Timestamp(fetched)
    return s[COLUMNS]


def datasets() -> dict[str, dict]:
    """{key: spec} for every configured dataset: key "french:<name>", "jkp:<name>" or, for JKP's long-only portfolios
    (a region's stocks in terciles by one characteristic), "jkp_pf:<region>:<characteristic>" with series "1" (low)
    to "3" (high)."""
    cfg = _cfg()
    out = {}
    for name, spec in (cfg.get("french") or {}).items():
        out[f"french:{name}"] = {"source": "french", **({"file": spec} if isinstance(spec, str) else spec)}
    for name, spec in (cfg.get("jkp") or {}).items():
        out[f"jkp:{name}"] = {"source": "jkp", **spec}
    pf = cfg.get("jkp_portfolios") or {}
    for region in pf.get("regions") or []:
        for ch in pf.get("characteristics") or []:
            out[f"jkp_pf:{region}:{ch}"] = {"source": "jkp_pf", "region": region, "characteristic": ch,
                                            "weighting": pf.get("weighting", "vw_cap")}
    return out


def _fetch(spec: dict) -> pd.DataFrame:
    if spec["source"] == "french":
        resp = net.get(FRENCH_URL.format(file=spec["file"]), timeout=120)
        resp.raise_for_status()
        return parse_french(resp.content, spec.get("block"))
    if spec["source"] == "jkp_pf":
        resp = net.get(JKP_PF_URL.format(**{k: spec[k] for k in ("region", "characteristic", "weighting")}), timeout=120)
        resp.raise_for_status()
        return parse_jkp(resp.content, "pf")
    resp = net.get(JKP_URL.format(region=spec["region"], theme=spec["theme"], weighting=spec["weighting"]), timeout=120)
    resp.raise_for_status()
    return parse_jkp(resp.content, spec.get("series", "location"), spec.get("name"))


def update_factors(today: date | None = None, force: bool = False) -> str:
    """Download the datasets whose stored copy is older than `max_age_days` (all with `force`). Each one is checked
    against what is stored (guard: the same series, starting no later, ending no earlier, not markedly fewer rows);
    one that fails keeps its stored rows, and the step then fails naming it after the rest are written."""
    today = today or date.today()
    max_age = timedelta(days=int(_cfg().get("max_age_days", 30)))
    stored = load()
    fetched = stored.groupby("key")["fetched"].max() if not stored.empty else pd.Series(dtype="datetime64[ns]")
    fresh, failed, skipped = [], [], 0
    specs = datasets()
    for key, spec in specs.items():
        if not force and key in fetched.index and pd.Timestamp(today) - fetched[key] < pd.Timedelta(max_age):
            skipped += 1
            continue
        try:
            new = _long(key, _fetch(spec), today)
            old = stored[stored["key"] == key] if not stored.empty else None
            guard.check(old, new, what=key, key="series", date="date", row_tol=0.02)
            fresh.append(new)
        except Exception as e:  # one source's trouble shouldn't cost the others their update
            failed.append(f"{key} ({type(e).__name__}: {e})")
    if fresh:
        done = {f["key"].iat[0] for f in fresh}
        rest = stored[~stored["key"].isin(done)] if not stored.empty else None
        out = pd.concat([f for f in [rest, *fresh] if f is not None and not f.empty], ignore_index=True)
        write_parquet(out.sort_values(["key", "series", "date"]), FACTORS_FILE, index=False)
    msg = f"{len(fresh)} downloaded, {skipped} up to date"
    if failed:
        raise RuntimeError(msg + "; failed (kept the stored copy): " + "; ".join(failed))
    return msg


def load() -> pd.DataFrame:
    """Every dataset, long: key, series, date (month-end), ret (a decimal), fetched. Missing months have no row."""
    return pd.read_parquet(FACTORS_FILE) if FACTORS_FILE.exists() else pd.DataFrame(columns=COLUMNS)


def panel(key: str, data: pd.DataFrame | None = None) -> pd.DataFrame:
    """One dataset wide: month-end index, one column per series, monthly returns as decimals (NaN where missing).
    Empty when the dataset hasn't been downloaded."""
    df = load() if data is None else data
    sub = df[df["key"] == key]
    if sub.empty:
        return pd.DataFrame()
    return sub.pivot(index="date", columns="series", values="ret").sort_index()


def rf(data: pd.DataFrame | None = None) -> pd.Series:
    """The US one-month T-bill return per month (French's RF), the rate JKP's excess returns are measured over."""
    p = panel("french:ff3_us", data)
    return p["RF"] if "RF" in p else pd.Series(dtype=float)


def total(excess: pd.DataFrame, data: pd.DataFrame | None = None) -> pd.DataFrame:
    """JKP's excess returns + RF = total USD returns. A month without RF stays missing."""
    r = rf(data).reindex(excess.index)
    return excess.add(r, axis=0).where(r.notna(), np.nan)


def asof(data: pd.DataFrame | None = None) -> dict[str, str]:
    """{key: last month in the data}, for the report and the guide's data-licence table."""
    df = load() if data is None else data
    if df.empty:
        return {}
    return {k: f"{pd.Timestamp(d):%Y-%m}" for k, d in df.groupby("key")["date"].max().items()}
