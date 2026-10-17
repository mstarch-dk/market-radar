"""Reading trades from broker exports and spreadsheets into transaction rows for the portfolio store.

One pipeline for every source: read the file (CSV with any delimiter and encoding, UTF-16, or Excel) → find the
columns (a preset, or a mapping chosen by hand) → normalize numbers, dates and buy/sell words → match each
instrument to a Yahoo symbol → validate → preview → commit as one import (which can be undone).

Nothing is guessed silently: rows that aren't trades (dividends, transfers) are listed as skipped with the reason,
unclear symbols need confirming, and the preview shows exactly what would be saved.
"""
from __future__ import annotations

import csv
import io
import math
import re
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import NamedTuple

import pandas as pd
import yaml

from .. import money, trades

FIELDS = ["date", "type", "symbol", "isin", "name", "quantity", "price", "fee", "currency", "account", "ext_ref",
          "cash_amount"]
REQUIRED = ["date", "quantity", "price"]          # plus one of symbol / isin / name
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

# generic column names (any language) for files without a preset
GENERIC = {
    "date": ["date", "trade date", "dato", "handelsdato", "handelsdag", "datum"],
    "type": ["type", "transaction type", "side", "buy/sell", "køb/salg", "transaktion", "action"],
    "symbol": ["symbol", "ticker", "yahoo symbol"],
    "isin": ["isin"],
    "name": ["name", "security", "instrument", "navn", "værdipapir"],
    "quantity": ["quantity", "qty", "shares", "antal", "amount", "stk"],
    "price": ["price", "kurs", "pris", "purchase price"],
    "fee": ["fee", "fees", "commission", "kurtage", "gebyr", "courtage"],
    "currency": ["currency", "valuta"],
    "account": ["account", "konto", "depot", "portfolio"],
    "ext_ref": ["id", "trade id", "reference", "nota"],
    "cash_amount": ["beløb", "net amount", "nettobeløb", "cash amount", "belopp", "beløp", "booked amount"],
}
DEFAULT_BUY = ["BUY", "B", "BOUGHT", "KØB", "KØBT", "K"]
DEFAULT_SELL = ["SELL", "S", "SOLD", "SALG", "SOLGT"]
# cash rows (kept only with a cash amount in DKK; a preset may list its own words under the same keys)
DEFAULT_CASH = {
    "DEPOSIT": ["DEPOSIT", "INDBETALING", "INDSÆTNING", "INSÄTTNING", "INNSKUDD", "CASH DEPOSIT"],
    "WITHDRAW": ["WITHDRAWAL", "WITHDRAW", "UDBETALING", "HÆVNING", "UTTAG", "UTTAK", "CASH WITHDRAWAL"],
    "DIVIDEND": ["DIVIDEND", "UDBYTTE", "UTDELNING", "UTBYTTE", "CASH DIVIDEND"],
    "INTEREST": ["INTEREST", "RENTE", "RENTER", "RÄNTA", "CREDIT INTEREST"],
}


@cache
def presets() -> dict:
    return yaml.safe_load((Path(__file__).with_name("presets.yaml")).read_text(encoding="utf-8"))


# ---------------- reading ----------------

def decode(data: bytes) -> str:
    """Text from bytes: UTF-16 (Nordnet) by its BOM, else UTF-8, else Windows-1252 (Danish exports)."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _excel_cell(v) -> tuple[str, bool]:
    """(text, whether it was a number in the sheet). A number stays its value: re-reading it as text with a
    preset's decimal comma would turn 1234.5 into 12345."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "", False
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return format(float(v), ".15g"), True
    return str(v), False


def read_table(data: bytes, filename: str = "") -> pd.DataFrame:
    """The file as a table of text cells (numbers and dates are parsed later, with the right conventions). For a
    spreadsheet, `attrs["native"]` holds the (row, column) of cells that were numbers in the sheet."""
    if data[:2] == b"PK" or filename.lower().endswith((".xlsx", ".xlsm")):
        raw = pd.read_excel(io.BytesIO(data))
        raw.columns = [str(c).strip() for c in raw.columns]
        native, cells = set(), {}
        for c in raw.columns:
            col = []
            for i, v in raw[c].items():
                text, number = _excel_cell(v)
                col.append(text)
                if number:
                    native.add((i, c))
            cells[c] = col
        df = pd.DataFrame(cells, index=raw.index)
        df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
        df = df.apply(lambda s: s.str.strip())
        df.attrs["native"] = native
        return df
    else:
        text = decode(data)
        sample = "\n".join(text.splitlines()[:20])
        try:
            sep = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            sep = "\t" if "\t" in sample else ";" if sample.count(";") > sample.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False, skipinitialspace=True)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
    return df.fillna("").astype(str).apply(lambda s: s.str.strip())


# ---------------- finding the columns ----------------

def _norm(c: str) -> str:
    return re.sub(r"\s+", " ", c.strip().lower())


def map_columns(columns: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    """field -> column, matching names case- and space-insensitively."""
    by_norm = {_norm(c): c for c in columns}
    out: dict[str, str] = {}
    for field, names in aliases.items():
        for n in names:
            if _norm(n) in by_norm and by_norm[_norm(n)] not in out.values():
                out[field] = by_norm[_norm(n)]
                break
    return out


def preset_mapping(columns: list[str], preset: str) -> dict[str, str]:
    """A preset's columns, plus generic names for fields the preset doesn't list (a 'Symbol' column in a
    file that otherwise looks like a Danske export is still used)."""
    m = map_columns(columns, presets()[preset]["columns"])
    for field, col in map_columns([c for c in columns if c not in m.values()], GENERIC).items():
        m.setdefault(field, col)
    return m


def _complete(mapping: dict) -> bool:
    return all(f in mapping for f in REQUIRED) and any(f in mapping for f in ("symbol", "isin", "name"))


class Detected(NamedTuple):
    preset: str | None               # the broker preset whose columns these are, None for the generic names
    mapping: dict[str, str]          # our field -> the file's column


def detect(columns: list[str]) -> Detected:
    """The preset whose columns fit best (all required fields found), and its mapping; else a generic guess."""
    best: tuple[str | None, dict[str, str], int] = (None, {}, 0)
    for key, p in presets().items():
        own = map_columns(columns, p["columns"])          # recognised by its own column names only
        if _complete(own) and len(own) > best[2]:
            best = (key, own, len(own))
    if best[0]:
        return Detected(best[0], preset_mapping(columns, best[0]))
    return Detected(None, map_columns(columns, GENERIC))


# ---------------- normalizing values ----------------

_AMBIGUOUS = re.compile(r"^-?[1-9]\d{0,2}[.,]\d{3}$")


def ambiguous_number(s: str) -> bool:
    """'1.234' or '1,234': a thousand with a separator, or one and a bit with a decimal mark. Only the file's
    other values (or its preset) can tell."""
    return bool(_AMBIGUOUS.match(re.sub(r"[^\d,.\-]", "", str(s).replace("−", "-"))))


def infer_decimal(values) -> str | None:
    """The decimal mark a column uses, from the values that show it: both marks in one value (the last is the
    decimal), a mark used twice (a thousands separator), or one mark not followed by exactly three digits. None
    when nothing tells, or the values contradict each other (each value is then read on its own)."""
    votes = set()
    for v in values:
        t = re.sub(r"[^\d,.]", "", str(v))
        c, d = t.count(","), t.count(".")
        if c and d:
            votes.add("," if t.rfind(",") > t.rfind(".") else ".")
        elif c > 1:
            votes.add(".")
        elif d > 1 or c == 1 and not re.search(r",\d{3}$", t):
            votes.add(",")
        elif d == 1 and not re.search(r"\.\d{3}$", t):
            votes.add(".")
    return votes.pop() if len(votes) == 1 else None


def parse_number(s: str, decimal: str = "auto") -> float | None:
    """'1.234,56', '1,234.56', '1234,5', '-12', '1 234,5 DKK' → float; empty or unreadable → None."""
    s = re.sub(r"[^\d,.\-]", "", str(s).replace("−", "-"))
    if not s or s in ("-", ".", ","):
        return None
    if decimal == "auto":
        if "," in s and "." in s:
            decimal = "," if s.rfind(",") > s.rfind(".") else "."
        elif "," in s:
            decimal = "," if re.search(r",\d{1,2}$", s) or s.count(",") == 1 and not re.search(r",\d{3}$", s) else "."
        else:
            decimal = "."
    if decimal == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s: str, formats: list[str] | None = None, dayfirst: bool = True) -> str | None:
    s = str(s).strip()
    if not s:
        return None
    for f in formats or []:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    if re.fullmatch(r"\d{8}", s):
        try:
            return datetime.strptime(s, "%Y%m%d").date().isoformat()
        except ValueError:
            return None
    try:
        d = pd.to_datetime(s, dayfirst=dayfirst and not re.match(r"^\d{4}-", s))
    except (ValueError, TypeError):
        return None
    return None if pd.isna(d) else d.date().isoformat()


SAXO_EXCHANGES = {"xcse": ".CO", "xsto": ".ST", "xosl": ".OL", "xhel": ".HE", "xetr": ".DE", "xfra": ".F",
                  "xams": ".AS", "xpar": ".PA", "xbru": ".BR", "xlon": ".L", "xmil": ".MI", "xswx": ".SW",
                  "xvtx": ".SW", "xmad": ".MC", "xlis": ".LS", "xwbo": ".VI", "xdub": ".IR", "xnas": "",
                  "xnys": "", "arcx": "", "bats": "", "xase": "", "xtks": ".T", "xhkg": ".HK"}


def saxo_to_yahoo(sym: str) -> str | None:
    """Saxo's 'NOVOb:xcse' / 'AAPL:xnas' → Yahoo's 'NOVO-B.CO' / 'AAPL'; None if the exchange is unknown."""
    m = re.fullmatch(r"([A-Za-z0-9.\-]+?)([a-z])?:([a-z0-9]+)", sym.strip())
    if not m or m.group(3) not in SAXO_EXCHANGES:
        return None
    base, share_class, ex = m.group(1).upper(), m.group(2), m.group(3)
    return f"{base}{'-' + share_class.upper() if share_class else ''}{SAXO_EXCHANGES[ex]}"


def normalize(df: pd.DataFrame, mapping: dict[str, str], preset: str | None = None) -> tuple[list[dict], list[str]]:
    """Rows as transactions (unresolved: `ident` is what identifies the instrument), plus the watch-only symbols
    (Yahoo exports). Rows that aren't buys or sells are kept with `skip` saying why. A file's account column
    names the row's portfolio (`portfolio`); without one the row goes into the portfolio chosen for the import."""
    p = presets().get(preset or "", {})
    decimal = p.get("decimal", "auto")
    native = df.attrs.get("native", set())
    # a generic file: one decimal mark per numeric column, read from all its values; a column that shows nothing
    # follows the file's other numeric columns (a file writes its numbers one way)
    numeric = [mapping[f] for f in ("quantity", "price", "fee", "cash_amount") if f in mapping]
    whole = infer_decimal([v for c in numeric for v in df[c]]) if decimal == "auto" and numeric else None
    marks = {f: (infer_decimal(df[mapping[f]]) or whole or "auto") if decimal == "auto" else decimal
             for f in ("quantity", "price", "fee", "cash_amount") if f in mapping}

    def num(r, i, f, notes):
        if f not in mapping:
            return None
        v = r[mapping[f]]
        if (i, mapping[f]) in native:
            return float(v)
        if marks[f] == "auto" and ambiguous_number(v):
            notes.append((f, v))
        return parse_number(v, marks[f])
    buy = {w.upper() for w in p.get("buy", DEFAULT_BUY)}
    sell = {w.upper() for w in p.get("sell", DEFAULT_SELL)}
    cash_words = {w.upper(): kind for kind, words in DEFAULT_CASH.items() for w in p.get(kind.lower(), words)}
    get = lambda r, f: r[mapping[f]] if f in mapping else ""  # noqa: E731
    rows, watch = [], []
    for i, r in df.iterrows():
        sym, isin, name = get(r, "symbol"), get(r, "isin").upper(), get(r, "name")
        if preset == "saxo" and sym:
            sym = saxo_to_yahoo(sym) or sym
        ident = sym or isin or name
        unclear: list[tuple[str, str]] = []
        qty = num(r, i, "quantity", unclear)
        word = get(r, "type").strip().upper()
        if sym.startswith(("^", "$$")) or "=" in sym:            # Yahoo index, FX and cash rows
            continue
        if word in cash_words:
            amount = lambda f, r=r, i=i, unclear=unclear: num(r, i, f, unclear)
            rows.append(_cash_row(r, i, get, cash_words[word], ident, sym, isin, name, amount, p) | {"ambiguous": unclear})
            continue
        if not ident:
            continue
        if qty is None and p.get("watch_without_quantity"):
            watch.append(sym)
            continue
        if not word and p.get("default_type"):
            kind = p["default_type"]
        elif word in buy:
            kind = "BUY"
        elif word in sell:
            kind = "SELL"
        elif not word and "type" not in mapping and qty is not None:
            kind = "SELL" if qty < 0 else "BUY"                     # no type column: the sign says it
        else:
            kind = None
        row = {"row": int(i) + 2, "ident": ident, "symbol_in": sym or None, "isin": isin if ISIN_RE.match(isin) else None,
               "name": name or None, "date": parse_date(get(r, "date"), p.get("date_formats"), p.get("dayfirst", True)),
               "type": kind, "quantity": abs(qty) if qty is not None else None,
               "price": abs(v) if (v := num(r, i, "price", unclear)) is not None else None,
               "fee": abs(num(r, i, "fee", unclear) or 0.0),
               "currency": get(r, "currency") or None, "portfolio": get(r, "account").strip() or None,
               "ext_ref": get(r, "ext_ref") or None, "amount": None, "skip": None, "ambiguous": unclear}
        if kind is None:
            row["skip"] = f"not a buy or sell ({word or 'no type'})"
        elif row["date"] is None:
            row["skip"] = f"unreadable date ({get(r, 'date')!r})"
        elif not row["quantity"] or not row["price"]:
            row["skip"] = "no quantity or price"
        rows.append(row)
    return rows, sorted(set(watch))


def _cash_row(r, i, get, kind, ident, sym, isin, name, num, p) -> dict:
    """A deposit, withdrawal, dividend or interest row: an amount in DKK (other currencies are skipped: convert
    them first). A dividend keeps its instrument so it can be matched to a symbol. `num(field)` reads a number."""
    amount = num("cash_amount")
    ccy = (get(r, "currency") or "DKK").strip().upper()
    row = {"row": int(i) + 2, "ident": ident if kind == "DIVIDEND" else "", "symbol_in": sym or None,
           "isin": isin if ISIN_RE.match(isin) else None, "name": name or None,
           "date": parse_date(get(r, "date"), p.get("date_formats"), p.get("dayfirst", True)), "type": kind,
           "quantity": None, "price": None, "fee": 0.0, "currency": "DKK", "amount": abs(amount) if amount else None,
           "portfolio": get(r, "account").strip() or None, "ext_ref": get(r, "ext_ref") or None, "skip": None}
    if row["date"] is None:
        row["skip"] = f"unreadable date ({get(r, 'date')!r})"
    elif not row["amount"]:
        row["skip"] = f"a {kind.lower()} without a cash amount (map the cash amount column)"
    elif ccy != "DKK":
        row["skip"] = f"a {kind.lower()} in {ccy}: only DKK cash rows are imported"
    elif kind == "DIVIDEND" and not ident:
        row["skip"] = "a dividend without its instrument"
    return row


# ---------------- the file's currency against the listing's ----------------

def _ccy(c: str | None) -> str | None:
    """A currency code for comparing; pence (GBp, GBX) and pounds count as one (the ×100 price check tells them
    apart)."""
    if not c or not str(c).strip():
        return None
    c = str(c).strip()
    return "GBP" if c.upper() in ("GBP", "GBX") or money.is_pence(c) else c.upper()


def currency_issues(file_ccy: str | None, quote_ccy: str | None, symbol: str, fee: float | None) -> list[dict]:
    """Warnings when the file says a trade was in another currency than the listing quotes in: prices are stored
    per share in the listing's currency, so a price (and a fee) in another currency would be read wrongly."""
    f, q = _ccy(file_ccy), _ccy(quote_ccy)
    if not f or not q or f == q:
        return []
    out = [{"level": "warning", "field": "price",
            "message": f"The file says {f}, but {symbol} trades in {quote_ccy}: the price must be in {quote_ccy} "
                       f"(convert it, or choose the listing that trades in {f})."}]
    if fee:
        out.append({"level": "warning", "field": "fee",
                    "message": f"The fee is stored in {quote_ccy}, the listing's currency. If it was charged in {f}, "
                               "convert it."})
    return out


# ---------------- matching instruments to Yahoo symbols ----------------

def suggest_symbols(idents: list[tuple[str, str | None, str | None, str | None]], market_has) -> dict[str, dict]:
    """For each (ident, symbol, isin, name): a suggested Yahoo symbol and how it was found, best first:
    remembered → the radar's own ISIN list → the symbol itself when Yahoo has prices → Yahoo search (ISIN, then
    name). `market_has(symbol)` says whether prices exist (it may download them)."""
    from .. import tracked, userstore

    isin_cfg = {}
    for e in tracked.etfs():
        if e.isin:
            isin_cfg[e.isin.upper()] = e.ucits or e.ticker
    out = {}
    for ident, sym, isin, name in idents:
        cands: list[dict] = []
        for key in filter(None, [isin, sym, name, ident]):
            if (m := userstore.mapped_symbol(key)):
                cands.append({"symbol": m, "how": "remembered"})
                break
        if isin and isin in isin_cfg:
            cands.append({"symbol": isin_cfg[isin], "how": "radar ISIN list"})
        if sym and market_has(sym):
            cands.append({"symbol": sym, "how": "as in the file"})
        for q in filter(None, [isin, name]):
            cands += [{"symbol": h["symbol"], "how": f"Yahoo search for {q}", "name": h.get("name"),
                       "exchange": h.get("exchange")} for h in yahoo_search(q)[:4]]
        seen, uniq = set(), []
        for c in cands:
            if c["symbol"] not in seen:
                seen.add(c["symbol"])
                uniq.append(c)
        out[ident] = {"ident": ident, "isin": isin, "name": name, "candidates": uniq,
                      "chosen": uniq[0]["symbol"] if uniq else None,
                      "certain": bool(uniq) and uniq[0]["how"] in ("remembered", "radar ISIN list", "as in the file")}
    return out


def yahoo_search(q: str) -> list[dict]:
    try:
        from .. import net

        quotes = net.yf().Search(q, max_results=6, news_count=0).quotes
    except Exception:
        return []
    return [{"symbol": x["symbol"], "name": x.get("longname") or x.get("shortname"),
             "exchange": x.get("exchDisp") or x.get("exchange")}
            for x in quotes if x.get("symbol") and x.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")]


# ---------------- preview and commit ----------------

def preview(data: bytes, filename: str, get_market, market_has, preset: str | None = None,
            mapping: dict[str, str] | None = None, portfolio: int | None = None,
            symbols: dict[str, str] | None = None) -> dict:
    """What an import would do, without saving anything: the detected format and column mapping, every row
    with its Yahoo symbol (suggested or chosen in `symbols`), skipped rows with the reason, duplicates of stored
    trades, and validation issues. Rows are checked in order, together with the stored trades, so a sale later
    in the file is fine after its buy. `market_has(symbol)` makes sure prices exist (downloading them if needed);
    `get_market()` returns the current price store. Rows go into `portfolio` (an id; default: the default
    portfolio) unless the file names one."""
    from .. import portfolio as checks
    from .. import userstore

    df = read_table(data, filename)
    detected, guessed = detect(list(df.columns))
    preset = preset if preset in presets() else detected
    if mapping is None:
        mapping = preset_mapping(list(df.columns), preset) if preset else guessed
    rows, watch = normalize(df, mapping, preset)
    target = portfolio if portfolio is not None else userstore.default_portfolio()
    if target is not None and not userstore.get_portfolio(target):
        raise ValueError(f"no portfolio {target}")
    idents = {r["ident"]: (r["ident"], r["symbol_in"], r["isin"], r["name"]) for r in rows if not r["skip"] and r["ident"]}
    matches = suggest_symbols(list(idents.values()), market_has)
    for ident, sym in (symbols or {}).items():
        if ident in matches and sym:
            matches[ident]["chosen"] = sym.strip().upper()
            matches[ident]["certain"] = True

    p = presets().get(preset or "", {})
    stored = userstore.transactions()
    if p.get("snapshot"):                                  # a snapshot replaces its own earlier rows (in the target)
        stored = [t for t in stored if not (t["source"] == preset and t["portfolio_id"] == target)]
    real = set(userstore.portfolio_ids("real", include_archived=True))
    scope = real if target is None or target in real else set()       # as add_import checks duplicates
    seen = [t for t in stored if t["portfolio_id"] in scope or t["portfolio_id"] == target]
    keys = {userstore.trade_key(t) for t in seen}
    refs = {t["ext_ref"] for t in seen if t.get("ext_ref")}
    known = {x["name"]: x["id"] for x in userstore.portfolios()}
    new_ids: dict[str, int] = {}                           # portfolios named in the file, created on commit
    so_far: list[dict] = []
    for r in rows:
        r["symbol"] = matches.get(r["ident"], {}).get("chosen") if r["ident"] else None
        r["issues"], r["duplicate"] = [], False
        if r["skip"]:
            continue
        if not r["symbol"] and r["ident"]:
            r["issues"] = [{"level": "error", "field": "symbol", "message": f"No Yahoo symbol for {r['ident']}: choose one."}]
            continue
        name = r["portfolio"]
        pid = known.get(name) if name in known else (new_ids.setdefault(name, -len(new_ids) - 1) if name else target)
        tx = {k: r[k] for k in ("symbol", "date", "type", "quantity", "price", "fee", "amount")} | {"portfolio_id": pid}
        if r["amount"] is not None:
            tx["currency"] = "DKK"
        r["duplicate"] = (r["ext_ref"] in refs) if r["ext_ref"] else userstore.trade_key(tx) in keys
        if r["duplicate"]:
            continue
        if tx["symbol"]:
            market_has(tx["symbol"])
        r["issues"] = checks.validate(tx, get_market(), others=stored + so_far)
        if r["type"] in ("BUY", "SELL") and r.get("currency") and tx["symbol"]:
            from .. import fxrates
            quote = fxrates.currencies([tx["symbol"]]).get(tx["symbol"])
            r["issues"] += currency_issues(r["currency"], quote, tx["symbol"], r["fee"])
        for field, value in r.get("ambiguous") or []:
            dot, comma = parse_number(value, "."), parse_number(value, ",")
            r["issues"].append({"level": "warning", "field": {"cash_amount": "amount"}.get(field, field),
                                "message": f"{value!r} could be {dot:g} or {comma:g}: the file doesn't show which "
                                           "decimal mark it uses. Check the value, or choose the broker's format."})
        so_far.append(tx | {"id": -len(so_far) - 1})
    for r in rows:
        r.pop("ambiguous", None)                           # said as warnings above
    counts = {"rows": len(rows), "new": sum(1 for r in rows if not r["skip"] and not r["duplicate"]),
              "duplicates": sum(r["duplicate"] for r in rows), "skipped": sum(bool(r["skip"]) for r in rows),
              "errors": sum(any(i["level"] == "error" for i in r["issues"]) for r in rows),
              "warnings": sum(any(i["level"] == "warning" for i in r["issues"]) for r in rows)}
    return {"preset": preset, "preset_label": p.get("label"), "verified": p.get("verified", True) if preset else None,
            "snapshot": bool(p.get("snapshot")), "columns": list(df.columns), "mapping": mapping, "rows": rows,
            "symbols": list(matches.values()), "watch": watch, "counts": counts, "portfolio_id": target,
            "new_portfolios": sorted(new_ids)}


def commit(pv: dict, filename: str, confirm_warnings: bool) -> dict:
    """Save a preview as one import. Refuses if any row has an error, or warnings that weren't confirmed.
    Confirmed symbol matches are remembered for next time."""
    from .. import userstore

    bad = [r for r in pv["rows"] if any(i["level"] == "error" for i in r["issues"])]
    warn = [r for r in pv["rows"] if any(i["level"] == "warning" for i in r["issues"])]
    if bad or (warn and not confirm_warnings):
        raise ValueError(f"{len(bad)} row(s) with errors" if bad else f"{len(warn)} row(s) with warnings to confirm")
    rows = [{k: r[k] for k in ("symbol", "date", "type", "quantity", "price", "fee", "amount", "portfolio", "ext_ref")}
            | {"note": None, "currency": "DKK" if r["amount"] is not None else None}
            for r in pv["rows"] if not r["skip"] and not r["duplicate"]]
    source = pv["preset"] or "csv"
    res = userstore.add_import(rows, source, filename, replace_source=pv["snapshot"], portfolio_id=pv["portfolio_id"])
    if pv["snapshot"]:
        userstore.meta_set(f"{source}_watch", pv["watch"])
    for m in pv["symbols"]:
        if m["chosen"]:
            for key in filter(None, [m["isin"], m["ident"]]):
                if key.upper() != m["chosen"]:
                    userstore.map_symbol(key, m["chosen"])
    return res | {"source": source}


# ---------- the Yahoo Finance portfolio export (a full snapshot) ----------

class YahooExport(NamedTuple):
    rows: list[dict]                 # the buys and sells as transaction rows
    watch: list[str]                 # symbols without a transaction: the export's watchlist
    skipped: dict[str, list[str]]    # per symbol, rows left out (types other than BUY/SELL)
    unreadable: list[str]            # buys / sells without a price or a date: "SYMBOL (row n)"


def _yahoo_rows(path: str) -> YahooExport:
    """A Yahoo Finance portfolio export as transaction rows, the symbols without transactions (its watchlist),
    a note per symbol for rows that were skipped (types other than BUY/SELL), and the buys/sells that can't be read
    (no purchase price or trade date: "SYMBOL (row n)"). Indices, futures, FX and cash rows are left out."""
    raw = pd.read_csv(path)
    raw.columns = [c.strip() for c in raw.columns]
    raw["Quantity"] = pd.to_numeric(raw.get("Quantity"), errors="coerce")
    raw["Purchase Price"] = pd.to_numeric(raw.get("Purchase Price"), errors="coerce")
    raw["Commission"] = pd.to_numeric(raw.get("Commission"), errors="coerce")
    trade = pd.to_numeric(raw.get("Trade Date"), errors="coerce").astype("Int64").astype("string")
    raw["Trade Date"] = pd.to_datetime(trade, format="%Y%m%d", errors="coerce")
    # older exports have no type: their lots are buys
    kind = raw.get("Transaction Type", pd.Series("", index=raw.index)).fillna("").astype(str).str.strip().str.upper()
    raw["Transaction Type"] = kind.replace("", "BUY")
    raw = raw[~raw["Symbol"].map(trades.is_market_symbol)]
    watch = sorted(s for s, lots in raw.groupby("Symbol") if lots["Quantity"].isna().all())
    skipped: dict[str, list[str]] = {}
    for _, r in raw[~raw["Transaction Type"].isin(["BUY", "SELL"]) & raw["Quantity"].notna()].iterrows():
        day = f" on {r['Trade Date']:%Y-%m-%d}" if pd.notna(r["Trade Date"]) else ""
        skipped.setdefault(r["Symbol"], []).append(
            f"skipped a {r['Transaction Type']} transaction{day}: only BUY/SELL are replayed")
    deals = raw[raw["Transaction Type"].isin(["BUY", "SELL"]) & raw["Quantity"].notna()]
    bad = deals[deals["Purchase Price"].isna() | deals["Trade Date"].isna()]
    unreadable = [f"{r['Symbol']} (row {i + 2}: no {'purchase price' if pd.isna(r['Purchase Price']) else 'trade date'})"
                  for i, r in bad.iterrows()]
    tx = deals.drop(bad.index)
    rows = [{"symbol": r["Symbol"], "date": r["Trade Date"].date().isoformat(), "type": r["Transaction Type"],
             "quantity": float(r["Quantity"]), "price": float(r["Purchase Price"]),
             "fee": 0.0 if pd.isna(r["Commission"]) else float(r["Commission"])} for _, r in tx.iterrows()]
    return YahooExport(rows, watch, skipped, unreadable)


def _import_market():
    """The stored prices, to check imported prices against the day's close; None before the first download."""
    from ..market import Market
    from ..paths import PRICES_FILE

    return Market.load() if PRICES_FILE.exists() else None   # no prices yet: the import works, unchecked


def import_yahoo_csv(path: str) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Import a Yahoo Finance portfolio export into the transaction store.

    The export is a full snapshot of that Yahoo portfolio, so it replaces the default portfolio's rows from the
    previous Yahoo import (manual entries, other brokers' imports and trades moved to another portfolio are
    kept) and its watchlist. Because it replaces, a file with a buy or sell that can't be read (no purchase price
    or trade date) or one dated in the future is refused before anything changes: importing it would silently
    drop that lot. Prices about 100× off or far from the day's close are noted. Returns the positions of the
    exported symbols and the notes per symbol (skipped rows, price checks, replay warnings)."""
    from .. import portfolio, userstore

    trades.ensure_migrated()
    rows, watch, skipped, unreadable = _yahoo_rows(path)   # read everything before writing anything
    if unreadable:
        raise ValueError(f"{len(unreadable)} buy/sell rows can't be read: {'; '.join(unreadable[:8])}"
                         + (f" and {len(unreadable) - 8} more" if len(unreadable) > 8 else "")
                         + ". Importing would drop those lots, so nothing was changed: fill them in on Yahoo and "
                           "export again, or use the import wizard (Portfolio → Import) to enter them.")
    future = sorted({r["symbol"] for r in rows if r["date"] > date.today().isoformat()})
    if future:
        raise ValueError(f"trades dated in the future for {', '.join(future)}: nothing was changed")
    market = _import_market()
    if market is not None:
        for r in rows:
            pc = portfolio.price_check(market, r["symbol"], r["date"], r["price"])
            if pc["verdict"] in ("x100", "div100", "far"):
                skipped.setdefault(r["symbol"], []).append(f"{r['date']}: {pc['message']}")
    userstore.add_import(rows, "yahoo", Path(path).name, replace_source=True)
    userstore.meta_set("yahoo_watch", watch)
    exported = {r["symbol"] for r in rows} | set(watch)
    pos, warnings = trades.positions(trades.transactions())
    pos = pos[pos["symbol"].isin(exported)]
    watch_rows = pd.DataFrame({"symbol": [w for w in watch if w not in set(pos["symbol"])], "status": "watch"})
    df = pd.concat([pos, watch_rows], ignore_index=True)[trades.HOLDING_COLS]
    notes = {k: skipped.get(k, []) + warnings.get(k, []) for k in exported if skipped.get(k) or warnings.get(k)}
    return df.sort_values("symbol").reset_index(drop=True), notes
