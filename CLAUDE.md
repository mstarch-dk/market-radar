# Market Radar

A personal investing toolkit for a Danish investor (frie midler + aktiesparekonto). The user's own accounts, horizon and preferences are in `notes/investor.md` (local, gitignored; template: `investor.example.md`): read it before advising on placement or writing a journal entry. It focuses on proactively spotting trends, sector and theme rotation, and 1–6-month momentum, and keeps the user's portfolios: real ones (the accounts) and virtual ones for simulations and A/B tests, with returns over time vs ACWI. Benchmark: MSCI ACWI. Everything produced here is analysis, not advice.

## Always
- Run Python through uv (`uv run radar …`, `uv run pytest -q`); the frontend through pnpm (`pnpm -C web …`).
- Truthfulness first: missing data shows as missing, never as 0. A source that parses to nothing fails loudly and keeps its cache.
- Prefer the proper fix over a workaround. If a better data source or tool would clearly help, propose it.
- `data/`, `reports/`, `imports/*`, `notes/`, `userdata/`, `exports/`, `briefs/`, `research/` and `journal/` are local and personal: never commit them.

## Main commands
- `uv run radar run`: update all data, then build `reports/dashboard.json` (the web app's data) and `summary.json`
- `uv run radar info <TICKER>` / `uv run radar serve`: one ticker's profile as JSON / the local web app (the dashboard UI)
- `uv run radar info <T1> <T2> … [--personal] [--out PATH]`: several tickers side by side with ACWI (personal data left out unless `--personal`)
- `uv run radar portfolios list [--json]` / `uv run radar performance [NAME…] [--tag T]`: the portfolios (real ones are "yours"; virtual ones only when named) and their returns over time vs ACWI
- `uv run radar ops [--errors]`: the operations log (external requests per host, errors, 429s, paused hosts, jobs); the app's Operations page shows the same
- `uv run pytest -q`: the tests

## Skills
- `/market-brief` → `briefs/YYYY-MM-DD.md` (also run monthly by a Claude desktop scheduled task on this machine)
- `/research <ticker>` → `research/<TICKER>.md`
- `/compare <t1> <t2> … [--personal]` → `research/compare/YYYY-MM-DD_<tickers>.md` (rubric incl. ACWI, bull/bear, red team, sizing, decision record)
- `/journal …` and `/journal review` → `journal/`
- `/marketing` → `marketing/` (Danish brochure, HTML + PDF, with screenshots of a demo copy holding a fictional investor; the PDF and its sources are committed, the screenshots aren't)

## Documentation for the user (Danish)
- `guide/` holds the user guide (`brugervejledning/`) and the textbook (`laerebog/`), served on the app's Guide page. When a change is visible to the user (a page, column, command, threshold or method), update the matching chapter in the same change; follow `guide/STIL.md`, quote thresholds with `{{settings:…}}`, and run `uv run pytest -q tests/test_guide.py`.

## Read before working on…
- [docs/commands.md](docs/commands.md): every CLI command (imports, holdings bundle, ticker tools)
- [docs/architecture.md](docs/architecture.md): config files, modules in `src/radar/`, what is committed, the monthly brief. Read it before changing code.
- [docs/data-conventions.md](docs/data-conventions.md): adjusted prices, re-basing, DKK returns, Yahoo units and gaps. Read it before touching any calculation or data source.
- [docs/testing.md](docs/testing.md): fixtures, the synthetic world, test practice
- [docs/web-app.md](docs/web-app.md): `radar serve`, the API contract, regenerating TypeScript types
