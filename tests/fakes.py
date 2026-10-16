"""Stand-ins for the outside world, so a test can serve any source's answer (including the broken ones) offline.

- `serve(monkeypatch, {pattern: answer})`: what `net.get` gets back, by URL. Requests still go through `net.get`
  (limits, retries, the operations log); an answer is a `Resp`, an exception (raised) or a callable(url).
- `FakeYf`: the parts of yfinance the radar uses, installed with `fake_yf(monkeypatch, ...)`; `statements(…)`
  reads the captured Yahoo statement frames.
- `stored(path)`: rows and first/last date per key of a stored file, for "never shrinks" checks.
"""
from __future__ import annotations

import json as _json
import re
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import requests

from radar import net


class Resp:
    """A requests.Response as far as the radar reads one."""

    def __init__(self, status: int = 200, text: str | None = None, content: bytes | None = None, json=None,
                 headers: dict | None = None):
        if json is not None:
            text = _json.dumps(json)
        if content is None:
            content = (text or "").encode()
        self.status_code, self.content, self.headers = status, content, headers or {}
        self.text = text if text is not None else content.decode("utf-8", "replace")
        self.url = ""

    def json(self):
        return _json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for {self.url}", response=self)


def serve(monkeypatch, answers: dict, default=None) -> list[str]:
    """Answer `net.get` by URL: the first pattern (regex) found in the URL decides. No match: `default`, or a 404.
    Retries don't wait. Returns the URLs asked for, in order."""
    calls: list[str] = []
    monkeypatch.setattr(net, "sleep", lambda s: None)

    def get(url, **kw):
        calls.append(url)
        for pattern, answer in answers.items():
            if re.search(pattern, url):
                break
        else:
            answer = default if default is not None else Resp(404)
        if callable(answer) and not isinstance(answer, Resp):
            answer = answer(url)
        if isinstance(answer, BaseException):
            raise answer
        answer.url = url
        return answer
    monkeypatch.setattr(net.requests, "get", get)
    return calls


class FakeYf:
    """yfinance as the radar uses it. `info`/`funds`/`fast` map a ticker to its answer (an exception is raised);
    `download` is a callable(tickers, start) returning a frame shaped like yf.download's."""

    def __init__(self, info: dict | None = None, funds: dict | None = None, fast: dict | None = None,
                 download=None, statements: dict | None = None):
        self.info, self.funds, self.fast, self._download = info or {}, funds or {}, fast or {}, download
        self.statements = statements or {}    # ticker -> {"income yearly": DataFrame, …} or an exception
        self.asked: list[tuple[str, str]] = []

    def _answer(self, table: dict, kind: str, t: str):
        self.asked.append((kind, t))
        a = table.get(t)
        if isinstance(a, BaseException):
            raise a
        return a

    def Ticker(self, t: str):  # noqa: N802 (yfinance's name)
        fake = self

        class _T:
            @property
            def info(self):
                return fake._answer(fake.info, "info", t) or {}

            @property
            def funds_data(self):
                return SimpleNamespace(equity_holdings=fake._answer(fake.funds, "funds", t))

            @property
            def fast_info(self):
                return fake._answer(fake.fast, "fast", t) or {}

            def _statement(self, kind, freq):
                blocks = fake._answer(fake.statements, f"{kind} {freq}", t) or {}
                return blocks.get(f"{kind} {freq}", pd.DataFrame())

            def get_income_stmt(self, freq="yearly"):
                return self._statement("income", freq)

            def get_cash_flow(self, freq="yearly"):
                return self._statement("cash", freq)

            def get_balance_sheet(self, freq="yearly"):
                return self._statement("balance", freq)
        return _T()

    def download(self, tickers, start=None, **kw):
        self.asked.append(("download", ",".join(tickers if isinstance(tickers, list) else [tickers])))
        return self._download(tickers, start) if self._download else pd.DataFrame()


def statements(ticker: str) -> dict[str, pd.DataFrame]:
    """The captured Yahoo statements of AAPL or RR.L (tests/fixtures/yahoo_statements.json) as yfinance frames."""
    js = _json.loads((Path(__file__).parent / "fixtures" / "yahoo_statements.json").read_text(encoding="utf-8"))
    return {k: pd.DataFrame(v["data"], index=v["index"], columns=pd.to_datetime(v["columns"]).tz_localize(None))
            for k, v in js[ticker].items()}


def fake_yf(monkeypatch, **kw) -> FakeYf:
    """Install a FakeYf wherever the radar reaches yfinance (net.yf(), and ingest's direct yf.download)."""
    from radar import ingest

    fake = FakeYf(**kw)
    monkeypatch.setattr(net, "install_yfinance", lambda: None)
    monkeypatch.setattr(net, "yf", lambda: fake)
    monkeypatch.setattr(ingest, "yf", fake)
    return fake


def stored(path: Path, key: str | None = None, date: str | None = "date") -> dict:
    """{key: (rows, first date, last date)} of a stored parquet ("*" for the whole file); {} when absent.
    Wide files (dates as index, one column per series) are measured per column when `key` is None and `date`
    is not a column."""
    if not Path(path).exists():
        return {}
    df = pd.read_parquet(path)
    if df.empty:
        return {}
    if key is None and (date is None or date not in df.columns):     # wide: one series per column
        out = {}
        for c in df.columns:
            s = df[c].dropna()
            if not s.empty:
                out[str(c)] = (len(s), pd.Timestamp(s.index.min()), pd.Timestamp(s.index.max()))
        return out
    d = pd.to_datetime(df[date]) if date else None
    if key is None:
        return {"*": (len(df), d.min() if d is not None else None, d.max() if d is not None else None)}
    out = {}
    for k, g in df.assign(_d=d).groupby(key, observed=True):
        out[str(k)] = (len(g), g["_d"].min() if d is not None else None, g["_d"].max() if d is not None else None)
    return out


def never_shrank(before: dict, after: dict) -> list[str]:
    """What got smaller between two `stored` measurements: a key gone, fewer rows, a later start, an earlier end."""
    problems = []
    for k, (n, first, last) in before.items():
        if k not in after:
            problems.append(f"{k}: gone")
            continue
        n2, first2, last2 = after[k]
        if n2 < n:
            problems.append(f"{k}: {n} → {n2} rows")
        if first is not None and first2 is not None and first2 > first:
            problems.append(f"{k}: starts {first:%Y-%m-%d} → {first2:%Y-%m-%d}")
        if last is not None and last2 is not None and last2 < last:
            problems.append(f"{k}: ends {last:%Y-%m-%d} → {last2:%Y-%m-%d}")
    return problems
