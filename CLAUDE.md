# Market Radar

A personal investing toolkit for a Danish investor (frie midler + aktiesparekonto). The user's own accounts, horizon and preferences are in `notes/investor.md` in their data folder (`uv run radar paths` shows where; template: `investor.example.md`): read it before advising on placement or writing a journal entry. It focuses on proactively spotting trends, sector and theme rotation, and 1–6-month momentum, and keeps the user's portfolios: real ones (the accounts) and virtual ones for simulations and A/B tests, with returns over time vs ACWI. Benchmark: MSCI ACWI. Everything produced here is analysis, not advice.

## Always
- Run Python through uv (`uv run radar …`, `uv run pytest -q`); the frontend through pnpm (`pnpm -C web …`).
- Truthfulness first: missing data shows as missing, never as 0. A source that parses to nothing fails loudly and keeps its cache.
- Adding, removing or changing a data source: update `DATA_LICENSE.md` and the guide chapter `guide/brugervejledning/datalicenser.md` (its terms and what it's used for). Downloaded data is for personal, non-commercial use; never build features that redistribute it.
- Prefer the proper fix over a workaround. If a better data source or tool would clearly help, propose it.
- The user's data lives outside the repo, in the data folder (`~/Market Radar`: radar.db, notes, briefs, research, journal, exports, imports, history) and the cache folder (market data, reports); `uv run radar paths` lists them. Never commit or copy them into the repo. A checkout from before the data folder may still hold `data/`, `reports/`, `imports/*`, `notes/`, `userdata/`, `exports/`, `briefs/`, `research/`, `journal/` at its root: gitignored, never commit them.
- The repo is public: never commit personal data (holdings, account names, briefs, the user's notes). Run `uv run python scripts/leak_check.py --install-hook` once per clone; the hook checks every push.
- Every file the code writes has a tier in `src/radar/paths.py` (`REGISTRY`): personal, history (can't be downloaded again) or cache. Build paths from `paths` (never from `config.ROOT`); schema and layout migrations are append-only and never delete user data (docs/architecture.md, *Where data lives*).

## Main commands
- `uv run radar run`: update all data, then build `reports/dashboard.json` (the web app's data) and `summary.json`
- `uv run radar info <TICKER>` / `uv run radar serve`: one ticker's profile as JSON / the local web app (the dashboard UI)
- `uv run radar info <T1> <T2> … [--personal] [--out PATH]`: several tickers side by side with ACWI (personal data left out unless `--personal`)
- `uv run radar portfolios list [--json]` / `uv run radar performance [NAME…] [--tag T]`: the portfolios (real ones are "yours"; virtual ones only when named) and their returns over time vs ACWI
- `uv run radar xray [NAME…] [--tag T] [--scope real|virtual|all] [--json]`: the portfolio X-ray (exposure vs ACWI, where the risk sits, concentration, stress)
- `uv run radar attribution [NAME…] [--tag T] [--start D] [--end D] [--json]`: attribution vs ACWI (trading and fees, proxies vs ACWI, allocation / selection / interaction by sector and region, currency) and the factor regression's alpha with its t
- `uv run radar scout review [--json]`: /scout's frozen hypothesis candidates vs ACWI since their day, by decision and stage
- `uv run radar evidence [--json]`: every study's status, age and rule, the scores' IC with t and holdout, and the forward record vs ACWI (the Evidence page)
- `uv run radar tax year [YEAR] [--portfolio P] [--person N] [--json]` / `tax classify|isin|person|opening`: the Danish tax estimate per account and person (ASK and pension pools, share income with the progression limit, capital income), rules from `config/tax_dk.yaml`, and its inputs
- `uv run radar rules [--json]` / `rules check buy|sell TICKER AMOUNT [--portfolio P] [--style S] [--json] [--log]` / `rules standing|replay|add|decision`: your trading rules and whether an action breaks them, rule by rule with the numbers (a mirror, never a gate)
- `uv run radar calendar [NAME…] [--tag T] [--days N] [--json]`: the coming weeks for what you hold and watch (earnings and ex-dividend dates, your review dates, proposal time stops), each with why it is highlighted
- `uv run radar study score [--exits 6]`: the momentum score tested at every past month-end (IC, quintiles, holdout, variants, the exit rule); `uv run radar sim picks …`: a basket picked on a past day, simulated
- `uv run radar propose candidates|freeze|evaluate|shadow|review|check …` / `uv run radar study propose`: a fee-aware basket proposal for one portfolio, tested against ACWI and the alternatives; the rule tested at every past month-end
- `uv run radar paths [--json]` / `uv run radar setup`: where the data folder, history and cache are / choose it (first start of 0.2.0: copies an older version's data in)
- `uv run radar backup` / `backups` / `restore FILE`, `uv run radar export` / `import-export FILE`: backups of the data folder; open-format export
- `uv run radar mcp`: the MCP server (stdio) that `.mcp.json` starts: the radar's readings, jobs, engines and three narrow writes as `mcp__radar__*` tools, which the skills prefer (each keeps one line of CLI fallback); see docs/commands.md
- `uv run radar ops [--errors]`: the operations log (external requests per host, errors, 429s, paused hosts, jobs); the app's Operations page shows the same
- `uv run pytest -q`: the tests; `uv run ruff check` and `uv run mypy`: lint and types (CI runs them and `uv run lint-imports`; `tests/test_layers.py` guards the layers, see docs/testing.md)
- Releases: `CHANGELOG.md` + guide *Nyheder*, then `uv run python scripts/release.py prepare X.Y.Z` (version, fixture data folder for the upgrade test)

## Skills
- `/market-brief` → `briefs/YYYY-MM-DD.md` (also run monthly by a Claude desktop scheduled task on this machine)
- `/research <ticker>` → `research/<TICKER>.md`
- `/compare <t1> <t2> … [--personal]` → `research/compare/YYYY-MM-DD_<tickers>.md` (rubric incl. ACWI, bull/bear, red team, sizing, decision record)
- `/journal …` and `/journal review` → `journal/` (checks the action against the trading rules first)
- `/rules`, `/rules check <action>`, `/rules review` → `radar.db` (trading rules, written only after the user confirms each)
- `/propose-portfolio <portfolio> <amount-dkk> [momentum|value|mix]` and `/propose-portfolio review` → `research/proposals/` (picks frozen in `exports/proposals/` before the model's numbers; the drift only from `radar study propose`; ACWI as the null; exit criteria re-checked by `radar propose check`)
- `/scout [hint …]` → `research/scout/YYYY-MM-DD.md` (3–5 hypotheses from web research on what the market is starting to talk about, checked against the radar's numbers, staged whisper / confirming / consensus and red-teamed; the user adopts each as a market view through `add_view`, watches or dismisses it; every shortlisted candidate is frozen in `exports/scout/` and followed by `radar scout review` and the Evidence page; a journal entry `type: hypothesis` on the user's yes)
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
