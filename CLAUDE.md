# Market Radar

A personal investing toolkit for a Danish investor (frie midler + aktiesparekonto). The user's own accounts, horizon and preferences are in `notes/investor.md` in their data folder (`uv run radar paths` shows where; template: `investor.example.md`): read it before advising on placement or writing a journal entry. It focuses on proactively spotting trends, sector and theme rotation, and 1–6-month momentum, and keeps the user's portfolios: real ones (the accounts) and virtual ones for simulations and A/B tests, with returns over time vs ACWI. Benchmark: MSCI ACWI. Everything produced here is analysis, not advice.

## Always
- Run Python through uv (`uv run radar …`, `uv run pytest -q`); the frontend through pnpm (`pnpm -C web …`).
- Truthfulness first: missing data shows as missing, never as 0. A source that parses to nothing fails loudly and keeps its cache.
- Adding, removing or changing a data source: update `DATA_LICENSE.md` and the guide chapter `guide/brugervejledning/datalicenser.md` (its terms and what it's used for). Downloaded data is for personal, non-commercial use; never build features that redistribute it.
- Prefer the proper fix over a workaround. If a better data source or tool would clearly help, propose it.
- The user's data lives outside the repo, in the data folder (`~/Market Radar`: radar.db, notes, briefs, research, journal, exports, imports, history) and the cache folder (market data, reports); `uv run radar paths` lists them. Never commit or copy them into the repo. A checkout from before the data folder may still hold `data/`, `reports/`, `imports/*`, `notes/`, `userdata/`, `exports/`, `briefs/`, `research/`, `journal/` at its root: gitignored, never commit them.
- Every file the code writes has a tier in `src/radar/paths.py` (`REGISTRY`): personal, history (can't be downloaded again) or cache. Build paths from `paths` (never from `config.ROOT`); schema and layout migrations are append-only and never delete user data (docs/architecture.md, *Where data lives*).

## Main commands
- `uv run radar run`: update all data, then build `reports/dashboard.json` (the web app's data) and `summary.json`
- `uv run radar info <TICKER>` / `uv run radar serve`: one ticker's profile as JSON / the local web app (the dashboard UI)
- `uv run radar info <T1> <T2> … [--personal] [--out PATH]`: several tickers side by side with ACWI (personal data left out unless `--personal`)
- `uv run radar portfolios list [--json]` / `uv run radar performance [NAME…] [--tag T]`: the portfolios (real ones are "yours"; virtual ones only when named) and their returns over time vs ACWI
- `uv run radar study score [--exits 6]`: the momentum score tested at every past month-end (IC, quintiles, holdout, variants, the exit rule); `uv run radar sim picks …`: a basket picked on a past day, simulated
- `uv run radar paths [--json]` / `uv run radar setup`: where the data folder, history and cache are / choose it (first start of 0.2.0: copies an older version's data in)
- `uv run radar backup` / `backups` / `restore FILE`, `uv run radar export` / `import-export FILE`: backups of the data folder; open-format export
- `uv run radar ops [--errors]`: the operations log (external requests per host, errors, 429s, paused hosts, jobs); the app's Operations page shows the same
- `uv run pytest -q`: the tests
- Releases: `CHANGELOG.md` + guide *Nyheder*, then `uv run python scripts/release.py prepare X.Y.Z` (version, fixture data folder for the upgrade test)

## Skills
- `/market-brief` → `briefs/YYYY-MM-DD.md` (also run monthly by a Claude desktop scheduled task on this machine)
- `/research <ticker>` → `research/<TICKER>.md`
- `/compare <t1> <t2> … [--personal]` → `research/compare/YYYY-MM-DD_<tickers>.md` (rubric incl. ACWI, bull/bear, red team, sizing, decision record)
- `/journal …` and `/journal review` → `journal/`
- `/hindsight [1M 3M 6M 1Y]` → `research/hindsight/YYYY-MM-DD_<name>.md` (a basket picked on a past day by score / views / Claude's judgment, simulated against ACWI, a score-only control, the equal-weight universe and random baskets; blind before the model's cutoff)
- `/marketing` → `marketing/` (Danish brochure, HTML + PDF, with screenshots of a demo copy holding a fictional investor; the PDF and its sources are committed, the screenshots aren't)

## Documentation for the user (Danish)
- `guide/` holds the user guide (`brugervejledning/`) and the textbook (`laerebog/`), served on the app's Guide page. When a change is visible to the user (a page, column, command, threshold or method), update the matching chapter in the same change; follow `guide/STIL.md`, quote thresholds with `{{settings:…}}`, and run `uv run pytest -q tests/test_guide.py`.

## Read before working on…
- [docs/commands.md](docs/commands.md): every CLI command (imports, holdings bundle, ticker tools)
- [docs/architecture.md](docs/architecture.md): config files, modules in `src/radar/`, what is committed, the monthly brief. Read it before changing code.
- [docs/data-conventions.md](docs/data-conventions.md): adjusted prices, re-basing, DKK returns, Yahoo units and gaps. Read it before touching any calculation or data source.
- [docs/testing.md](docs/testing.md): fixtures, the synthetic world, test practice
- [docs/web-app.md](docs/web-app.md): `radar serve`, the API contract, regenerating TypeScript types
