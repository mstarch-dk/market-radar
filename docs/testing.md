# Testing

- `uv run pytest -q`: parsers, signals, holdings import, config integrity, ticker profiles, the API, the user store, portfolios and their upgrade from accounts (`test_portfolios.py`), the cash ledger (`test_cash.py`), returns over time with hand-checkable numbers (`test_performance.py`), forks and simulated runs (`test_simulate.py`), the point-in-time stop/take-profit backtest (`test_backtest_exits.py`: parity of each as-of input with the live function, no look-ahead, exits, funding, and "rule off = your real returns"), and an end-to-end `report.build()` (summary.json keys, dashboard.json against the API models). `test_valuation.py`: the valuation and sentiment parsers on trimmed real payloads, P/E on Yahoo's mixed currencies, revisions and percentiles, and the switchable regime votes. `test_marketing.py` keeps `marketing/` consistent (shots ↔ features ↔ page, seed dates and names).
- `pnpm -C web test`: frontend formatters and the table state (URL round trip, filters, sorting, CSV). `pnpm -C web build` type-checks the UI against the generated API schema.

## Fixtures
- `tests/fixtures/` holds trimmed copies of real payloads (FRED, OECD, CFTC, FactSet text, Yahoo ticker detail). When a source changes format, fix the parser and refresh its fixture from a real response.
- `tests/world.py` is a small synthetic market whose answers are known in advance (geometric prices, one holding, one watchlist name). It is shared by the report, profile and API tests; `world.install()` patches config, caches and Yahoo lookups.
- An autouse fixture in `tests/conftest.py` points every data path at a fresh temp directory (`paths.configure(paths.Locations.flat(...))`), clears `MARKET_RADAR_*` env vars and keeps the pointer file and default folders in temp too, so no test can read or write the real data folder. `tmp_data` does the same for `tmp_path` and returns it (every tier in one folder, `radar.db` in `userdata/`). Paths are `paths.Lazy`, so never monkeypatch a module's path constant: configure the locations instead (`paths.Locations.at(home, cache)` for a real data folder, `.legacy(root)` for the old layout).
- `tests/fixtures/homes/`: one data folder per release plus the legacy layout, opened by `test_upgrade.py`; written by `scripts/release.py fixture` and never changed. An autouse fixture gives every test its own `ops.db` and resets the network limiter, so no test writes to `data/ops.db`.
- `test_net.py` drives the limiter, retries and cooldowns with a fake clock (`net.clock` / `net.sleep`) and a stubbed `net.requests.get`; HTTP stubs patch `net.requests.get`, since every plain request goes through `net.get`. `test_ops.py` covers the log, its housekeeping, jobs and the Operations endpoints.

## The guide (`guide/`)
- `tests/test_guide.py`: every chapter in `guide/guide.yaml` exists (and no file is left out), each H1 equals its manifest title, every `{{settings:…}}` resolves, every link reaches a real chapter, heading or app page, and `page_links`/`glossary_links` point at real pages, glossary keys and headings.
- Formulas: `uv run python -c "import json; from radar import guide; print(json.dumps({f'{b}/{s}': guide.chapter(b, s)['markdown'] for b, s, _, _ in guide.manifest()['_order']}))" | node web/scripts/check-math.mjs` compiles every `$…$` / `$$…$$` with KaTeX and lists the ones that fail.

## Practice
- For a bug fix, write the test first and watch it fail on the old code.
- Pin method-sensitive numbers (e.g. RRG values) so a change to a method is deliberate.
- Verify locally before pushing; there is no CI in this repo.
