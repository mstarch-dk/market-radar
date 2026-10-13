# Testing

- `uv run pytest -q`: parsers, signals, holdings import, config integrity, ticker profiles, the API, and an end-to-end `report.build()`. Also run in CI.
- `pnpm -C web test`: frontend formatters. `pnpm -C web build` type-checks the UI against the generated API schema.

## Fixtures
- `tests/fixtures/` holds trimmed copies of real payloads (FRED, OECD, CFTC, FactSet text, Yahoo ticker detail). When a source changes format, fix the parser and refresh its fixture from a real response.
- `tests/world.py` is a small synthetic market whose answers are known in advance (geometric prices, one holding, one watchlist name). It is shared by the report, profile and API tests; `world.install()` patches config, caches and Yahoo lookups.
- `tests/conftest.py`'s `tmp_data` points every module-level data path at a temp directory.

## Practice
- For a bug fix, write the test first and watch it fail on the old code.
- Pin method-sensitive numbers (e.g. RRG values) so a change to a method is deliberate.
- Verify locally before pushing; there is no CI on pull requests.
