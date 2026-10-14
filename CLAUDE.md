# Market Radar

A personal investing toolkit for a Danish investor (frie midler + aktiesparekonto). It focuses on proactively spotting trends, sector and theme rotation, and 1–6-month momentum. Portfolio tracking itself stays in Yahoo Finance. Benchmark: MSCI ACWI. Everything produced here is analysis, not advice.

## Always
- Run Python through uv (`uv run radar …`, `uv run pytest -q`); the frontend through pnpm (`pnpm -C web …`).
- Truthfulness first: missing data shows as missing, never as 0. A source that parses to nothing fails loudly and keeps its cache.
- Prefer the proper fix over a workaround. If a better data source or tool would clearly help, propose it.
- `data/`, `reports/`, `imports/*`, `notes/`, `userdata/` and `exports/` are local and personal: never commit them (except `data/snapshots/`).

## Main commands
- `uv run radar run`: update all data, then build `reports/dashboard.json` (the web app's data) and `summary.json`
- `uv run radar info <TICKER>` / `uv run radar serve`: one ticker's profile as JSON / the local web app (the dashboard UI)
- `uv run radar info <T1> <T2> … [--personal] [--out PATH]`: several tickers side by side with ACWI (personal data left out unless `--personal`)
- `uv run pytest -q`: the tests

## Skills
- `/market-brief` → `briefs/YYYY-MM-DD.md`
- `/research <ticker>` → `research/<TICKER>.md`
- `/compare <t1> <t2> … [--personal]` → `research/compare/YYYY-MM-DD_<tickers>.md` (rubric incl. ACWI, bull/bear, red team, sizing, decision record)
- `/journal …` and `/journal review` → `journal/`

## Read before working on…
- [docs/commands.md](docs/commands.md): every CLI command (imports, holdings bundle, ticker tools)
- [docs/architecture.md](docs/architecture.md): config files, modules in `src/radar/`, what is committed, CI. Read it before changing code.
- [docs/data-conventions.md](docs/data-conventions.md): adjusted prices, re-basing, DKK returns, Yahoo units and gaps. Read it before touching any calculation or data source.
- [docs/testing.md](docs/testing.md): fixtures, the synthetic world, test practice
- [docs/web-app.md](docs/web-app.md): `radar serve`, the API contract, regenerating TypeScript types
