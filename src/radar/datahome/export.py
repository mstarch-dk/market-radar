"""Your data in open formats, readable without Market Radar: for a spreadsheet, an accountant, another computer,
or leaving. Unlike a backup (backup.py: an exact copy for this app to restore), an export is meant to be read.

    transactions.csv     every trade and cash row in every portfolio (UTF-8 with BOM so Excel reads æøå)
    portfolios.json      the portfolios: name, real/virtual, tax kind, dividends, tags, notes
    views.json           your market views with exposures and indicators
    rules.json           your trading rules
    watchlist.csv        the watchlist edits made in the app
    regime_votes.json    which indicator groups vote in the regime
    tax.json             the tax estimate's persons (and the portfolios they own), instruments and openings
    notes/ briefs/ research/ journal/   your Markdown documents
    EXPORT.md            what every file and column holds
    export.json          export format, date, app version

`load()` reads one back (another computer, a reinstall). The holdings bundle (`radar bundle-holdings`) is the
same portfolio part as one base64 text; `restore_holdings()` reads both.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import manifest, paths, userstore
from ..jsonsafe import dumps
from ..portfolios import trades
from ..userstore import rulestore, viewstore
from . import home

EXPORT_FORMAT = 1
TX = "transactions.csv"
BUNDLE_TX = "portfolio_transactions.csv"     # the same rows, as the holdings bundle names them
WATCHLIST = "watchlist.csv"
YAHOO_WATCH = "yahoo_watch.json"
VIEWS = "views.json"
RULES = "rules.json"
PORTFOLIOS = "portfolios.json"
VOTES = "regime_votes.json"
TAX = "tax.json"
LEGACY_FILES = ("holdings.csv", "transactions.csv")   # bundles made before the transaction store
DOCS = ("notes", "briefs", "research", "journal")

README = """# Market Radar export

Made {created} by Market Radar {version}. Export format {fmt}.

| File | What |
|---|---|
| `transactions.csv` | Every trade and cash row, one per line, in every portfolio (real and virtual, archived too). |
| `portfolios.json` | The portfolios: `name`, `mode` (real = yours, virtual = a simulation), `kind` (ask = aktiesparekonto, frie_midler, pension, other), `dividends` (reinvested or cash), `tags`, `note`, `archived`. |
| `views.json` | Your market views: statement, conviction 1–5, horizon, rationale, what would prove it wrong, exposures and indicators. |
| `rules.json` | Your trading rules: statement, kind and its parameters, scope (portfolios by name, account kind, tag, style), severity (hard, soft, reminder), why you have it, status. |
| `watchlist.csv` | Symbols added to (`add`) or removed from (`remove`) the watchlist in the app. |
| `regime_votes.json` | Which switchable indicator groups count in the regime vote. |
| `tax.json` | The tax estimate's inputs: tax persons (with a capital-income rate and the portfolios each owns), each symbol's ISIN and tax class, and the losses carried in from before the history. |
| `notes/`, `briefs/`, `research/`, `journal/` | Your documents as Markdown. |

## transactions.csv

UTF-8 with a byte-order mark, comma-separated, `.` as the decimal point, dates as YYYY-MM-DD.

| Column | Meaning |
|---|---|
| `symbol` | Yahoo Finance symbol (e.g. `NOVO-B.CO`); empty for cash rows |
| `date` | Trade date |
| `type` | BUY, SELL, DEPOSIT, WITHDRAW, DIVIDEND, FEE or INTEREST |
| `quantity` | Shares (trades) |
| `price` | Price per share in the security's currency (trades) |
| `fee` | Commission, in the security's currency |
| `amount` | Cash amount (cash rows) |
| `currency` | Currency of `amount`/`price` when given |
| `fx_rate` | DKK per unit of `currency`, when given |
| `portfolio` | The portfolio's name |
| `note` | Your note |
| `source` | Where the row came from (manual, an import, a simulation) |
| `ext_ref` | The broker's reference, when imported |

Analysis, not advice. The market data itself is not exported: it belongs to its sources (see DATA_LICENSE.md).
"""


def holdings_zip(z: zipfile.ZipFile, include_virtual: bool = False, tx_name: str = BUNDLE_TX) -> None:
    """Write the portfolio part: portfolios, their transactions, watchlists, views, trading rules, vote choices and the
    tax inputs."""
    universe_migrated()
    scope = "all" if include_virtual else "real"
    z.writestr(PORTFOLIOS, userstore.export_portfolios_json(scope))
    tx = userstore.export_transactions_csv(userstore.portfolio_ids(scope, include_archived=True))
    z.writestr(tx_name, ("﻿" + tx) if tx_name == TX else tx)
    z.writestr(WATCHLIST, userstore.export_watchlist_csv())
    z.writestr(YAHOO_WATCH, dumps(userstore.meta_get("yahoo_watch", [])))
    z.writestr(VIEWS, viewstore.export_views_json())
    z.writestr(RULES, rulestore.export_rules_json())
    z.writestr(VOTES, dumps(userstore.meta_get("regime_votes", {})))
    z.writestr(TAX, userstore.export_tax_json())


def universe_migrated() -> None:

    trades.ensure_migrated()


def restore_holdings(z: zipfile.ZipFile, reason: str = "before-unbundle") -> dict:
    """Read the portfolio part back (an export or a holdings bundle). Each portfolio in it gets exactly its rows;
    a copy of radar.db is taken first."""
    names = set(z.namelist())
    userstore.backup(reason)
    n_pf = userstore.import_portfolios_json(z.read(PORTFOLIOS).decode("utf-8")) if PORTFOLIOS in names else 0
    tx = next((n for n in (TX, BUNDLE_TX) if n in names), None)
    out: dict[str, Any] = {"portfolios": n_pf, "transactions": 0, "legacy_files": []}
    if tx:
        out["transactions"] = userstore.import_transactions_csv(z.read(tx).decode("utf-8-sig"))
        if YAHOO_WATCH in names:
            userstore.meta_set("yahoo_watch", json.loads(z.read(YAHOO_WATCH)))
        userstore.meta_set("legacy_csv", {"status": "migrated", "at": "bundle"})
    elif any(n in names for n in LEGACY_FILES):   # an older bundle: the CSV files, moved into the store on first use
        paths.IMPORTS.mkdir(parents=True, exist_ok=True)
        for n in LEGACY_FILES:
            if n in names:
                (paths.IMPORTS / n).write_bytes(z.read(n))
                out["legacy_files"].append(n)
        universe_migrated()
    out["watchlist"] = userstore.import_watchlist_csv(z.read(WATCHLIST).decode("utf-8")) if WATCHLIST in names else 0
    if VOTES in names:
        userstore.meta_set("regime_votes", json.loads(z.read(VOTES)))
    out["views"] = viewstore.import_views_json(z.read(VIEWS).decode("utf-8")) if VIEWS in names else 0
    out["rules"] = rulestore.import_rules_json(z.read(RULES).decode("utf-8")) if RULES in names else 0
    out["tax"] = userstore.import_tax_json(z.read(TAX).decode("utf-8")) if TAX in names else 0
    return out


def build() -> bytes:
    """The whole export as zip bytes."""
    buf = io.BytesIO()
    created = datetime.now().isoformat(timespec="seconds")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        holdings_zip(z, include_virtual=True, tx_name=TX)
        for d in DOCS:
            root = paths.HOME / d
            for p in home.files_under(root.now()):
                z.write(p, f"{d}/{p.relative_to(root.now()).as_posix()}")
        z.writestr("EXPORT.md", README.format(created=created, version=manifest.app_version(), fmt=EXPORT_FORMAT))
        z.writestr("export.json", dumps({"export_format": EXPORT_FORMAT, "created": created,
                                              "app_version": manifest.app_version()}, indent=1))
    return buf.getvalue()


def write(out: Path | None = None) -> Path:
    out = Path(out) if out else (paths.HOME / "exports").now() / f"market-radar-export-{datetime.now():%Y-%m-%d}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build())
    return out


def preview(f: Path) -> dict:
    """What an export holds, without changing anything."""
    with zipfile.ZipFile(f) as z:
        names = z.namelist()
        meta = json.loads(z.read("export.json")) if "export.json" in names else {}
        if meta.get("export_format", 0) > EXPORT_FORMAT:
            raise ValueError(f"made by Market Radar {meta.get('app_version')}: export format "
                             f"{meta['export_format']} is newer than this version reads")
        tx = next((n for n in (TX, BUNDLE_TX) if n in names), None)
        rows = z.read(tx).decode("utf-8-sig").count("\n") - 1 if tx else 0
        docs = [n for n in names if n.split("/")[0] in DOCS and not n.endswith("/")]
        return {"meta": meta, "transactions": rows,
                "portfolios": len(json.loads(z.read(PORTFOLIOS))) if PORTFOLIOS in names else 0,
                "documents": docs, "new_documents": [n for n in docs if not (paths.HOME / n).exists()]}


def load(f: Path) -> dict:
    """Read an export back: portfolios and transactions are replaced portfolio by portfolio, documents that aren't
    here yet are added (one that exists is left as it is)."""
    pv = preview(f)
    with zipfile.ZipFile(f) as z:
        out = restore_holdings(z, "before-import-export")
        for n in pv["new_documents"]:
            dst = (paths.HOME / n).now()
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(z.read(n))
    return out | {"documents_added": len(pv["new_documents"]),
                  "documents_kept": len(pv["documents"]) - len(pv["new_documents"])}
