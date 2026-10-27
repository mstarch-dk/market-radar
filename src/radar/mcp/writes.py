"""The two tools that write: a memo into the notebook's folders, and one trade into a portfolio. Narrow on purpose:
a memo goes only to a folder of its kind (all in the data folder's `home` tier, paths.REGISTRY), written atomically
and never over an existing one unless asked; a trade is checked as the app checks it and saved only on `confirm`."""
from __future__ import annotations

import re
from datetime import date as _date

from .. import errors, notebook, paths, profile, userstore
from ..config import write_text
from ..portfolios import checks, trades

FOLDERS = notebook.FOLDERS | {"hindsight": paths.HOME / "research" / "hindsight",   # the /hindsight memos
                             "listening": paths.HOME / "briefs" / "lyt"}             # a brief's NotebookLM version
NAME = re.compile(r"\w[\w.^+ -]{0,150}")      # a file name, no folders: NVDA, 2026-10-27_NVDA-AMD, NOVO-B.CO


def write_memo(kind: str, name: str, markdown: str, replace: bool = False) -> dict:
    """Write a skill's Markdown document into the data folder: `kind` research (research/<TICKER>), compare,
    proposals, proposal_reviews, hindsight, briefs, listening (a brief's NotebookLM version), journal or reviews;
    `name` the file name without .md (e.g. NVDA, 2026-10-27_NVDA-AMD). An existing document is replaced only with
    `replace` (read it first with `read_document` and keep its content). Written whole or not at all; returns where
    it went."""
    if kind not in FOLDERS:
        raise errors.Invalid(f"kind must be one of {', '.join(FOLDERS)}")
    stem = name.removesuffix(".md").strip()
    if not NAME.fullmatch(stem) or ".." in stem:
        raise errors.Invalid(f"{name!r} isn't a file name: letters, digits, . _ - + ^ and spaces, no folders.")
    if not markdown.strip():
        raise errors.Invalid("The document is empty.")
    f = FOLDERS[kind] / f"{stem}.md"
    existed = f.is_file()
    if existed and not replace:
        raise errors.Conflict(f"{kind}/{stem} exists: read it with read_document, keep what it says, and write it "
                              f"again with replace=true.")
    f.parent.mkdir(parents=True, exist_ok=True)
    write_text(f, markdown if markdown.endswith("\n") else markdown + "\n")
    return {"kind": kind, "name": stem, "file": str(f), "replaced": existed}


def add_trade(type: str, symbol: str, quantity: float, price: float, date: str | None = None, fee: float = 0.0,
              portfolio: str | None = None, note: str | None = None, confirm: bool = False) -> dict:
    """Record one trade (`type` BUY or SELL; `price` and `fee` in the price's currency; `date` YYYY-MM-DD, default
    today) in `portfolio` (by name; default: the default portfolio). Without `confirm` nothing is saved: it returns
    the checks' issues (errors always block, warnings need the user's yes) and the position before and after. Show
    them to the user, and call again with `confirm` only once the user has agreed to save this trade."""
    trades.ensure_migrated()
    sym = symbol.strip().upper()
    row = {"symbol": sym, "date": date or _date.today().isoformat(), "type": type.strip().upper(),
           "quantity": quantity, "price": price, "fee": fee, "portfolio": portfolio, "note": note}
    m = profile.ensure_prices(sym)                     # an untracked ticker is downloaded, as in the app
    if not confirm:
        issues = checks.validate(row, m)
        return {"saved": False, "trade": row, "issues": issues, "effect": checks.effect(row),
                "blocked": any(i["level"] == "error" for i in issues)}
    issues = checks.checked(row, m, confirm=True)      # Invalid (with the issues) on an error
    tx_id = userstore.add_tx(row)
    saved = userstore.get_tx(tx_id) or {}
    return {"saved": True, "id": tx_id, "portfolio": saved.get("portfolio"), "trade": row, "issues": issues,
            "effect": checks.effect(row, exclude_id=tx_id)}


TOOLS = (write_memo, add_trade)
