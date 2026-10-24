# Testing

- `uv run pytest -q`: parsers, signals, holdings import, config integrity, ticker profiles, the API, the user store,
  portfolios and their upgrade from accounts (`test_portfolios.py`), the cash ledger (`test_cash.py`), returns over
  time with hand-checkable numbers (`test_performance.py`), forks and simulated runs (`test_simulate.py`), the
  point-in-time stop/take-profit backtest (`test_backtest_exits.py`: parity of each as-of input with the live
  function, no look-ahead, exits, funding, and "rule off = your real returns"), and an end-to-end `report.build()`
  (summary.json keys, dashboard.json against the API models). `test_valuation.py`: the valuation and sentiment parsers
  on trimmed real payloads, P/E on Yahoo's mixed currencies, revisions and percentiles, and the switchable regime
  votes. `test_marketing.py` keeps `marketing/` consistent (shots ↔ features ↔ page, seed dates and names).
- `pnpm -C web test`: frontend formatters and the table state (URL round trip, filters, sorting, CSV). `pnpm -C web
  build` type-checks the UI against the generated API schema.

## Fixtures
- `tests/fixtures/` holds small samples in each source's format: trimmed real answers from the open sources (FRED,
  ECB, OECD, CFTC, SEC EDGAR, Damodaran), and from the others only a few numbers in their layout. A source's prose
  is never committed: the FactSet excerpt is invented text in the report's wording, and the Yahoo business
  summaries are placeholders (DATA_LICENSE.md, *Test fixtures*). When a source changes format, fix the parser and
  refresh its fixture from a real response, trimmed the same way.
- `tests/world.py` is a small synthetic market whose answers are known in advance (geometric prices, one holding, one
  watchlist name). It is shared by the report, profile and API tests; `world.install()` patches config, caches and
  Yahoo lookups.
- An autouse fixture in `tests/conftest.py` points every data path at a fresh temp directory
  (`paths.configure(paths.Locations.flat(...))`), clears `MARKET_RADAR_*` env vars and keeps the pointer file and
  default folders in temp too, so no test can read or write the real data folder. `tmp_data` does the same for
  `tmp_path` and returns it (every tier in one folder, `radar.db` in `userdata/`). Paths are `paths.Lazy`, so never
  monkeypatch a module's path constant: configure the locations instead (`paths.Locations.at(home, cache)` for a real
  data folder, `.legacy(root)` for the old layout).
- Settings the same way: never monkeypatch a module's `settings`; `with_settings(monkeypatch, backtest={"fee_bps":
  0})` (in `tests/conftest.py`) merges the changes into settings.yaml, checks them like the file and gives both
  `config.typed()` and `config.settings()` the result for the rest of the test.

- `tests/fixtures/homes/`: one data folder per release plus the legacy layout, opened by `test_upgrade.py`; written by
  `scripts/release.py fixture` and never changed. An autouse fixture gives every test its own `ops.db` and resets the
  network limiter, so no test writes to `data/ops.db`.
- `test_net.py` drives the limiter, retries and cooldowns with a fake clock (`net.clock` / `net.sleep`) and a stubbed
  `net.requests.get`; HTTP stubs patch `net.requests.get`, since every plain request goes through `net.get`.
  `test_ops.py` covers the log, its housekeeping, jobs and the Operations endpoints.

## Offline, and the outside world as stand-ins
- **Tests never reach the internet.** The autouse `_offline` fixture in `tests/conftest.py` refuses sockets to
  anything but this machine and yfinance's curl_cffi session (libcurl, which bypasses Python sockets). Production code
  often swallows errors (a failed name lookup becomes the ticker), so every attempt is also recorded and fails the
  test at teardown, naming the URL. Stub the call; the fixture yields its list of attempts for the guard's own tests.
- **`tests/fakes.py`** serves any source's answer, the broken ones included: `serve(monkeypatch, {url_pattern: Resp |
  exception})` answers `net.get` by URL (limits, retries and the operations log still run), `fake_yf(monkeypatch,
  info=…, funds=…, fast=…, download=…)` stands in for yfinance, and `stored(path)` / `never_shrank(before, after)`
  measure a stored file per series, ticker or area.
- **Dates:** the `update_*` functions take `today=` (default `date.today()`), as `sentiment.update_putcall` does; pass
  a fixed date instead of depending on the clock.
- **`tests/test_ingest_invariants.py`**: one table of sources × bad answers (an error, an empty answer, a shorter one,
  one series missing). Each source is updated with a good answer, then a bad one; nothing stored may shrink (rows,
  first date, last date, per key). Known gaps are `xfail(strict=True)` with the plan item that fixes them: a fix turns
  the entry green and the strict mark then fails until it is removed. A new source gets a row here.
- **Offline source tests** (`test_external.py`, `test_valuation.py`, `test_discovery_*.py`, `test_ingest.py`,
  `test_updater.py`): each update and parse function with small answers in the real formats, its error branches
  included (a parse that finds nothing raises). A bug one finds gets its fix in the same change.
- **Live contract checks** (`tests/test_live_contracts.py`, marker `network`, left out of the normal run): each parser
  against the real, current answer, and whether the data is recent. Run `uv run pytest -m network -q` before a release
  or when a source looks odd. A failure means updating the parser and its fixture: `uv run python
  scripts/capture_fixture.py --list` / `<source> [--dry-run]` records a trimmed real answer into `tests/fixtures/`.
- **Slow tests** (marker `slow`, left out of the normal run): a study run on real-size data, such as the long-run
  study over decades of synthetic months (`tests/test_longrun.py`). Mark a test `@pytest.mark.slow` when it takes more
  than a few seconds because of the data's size; keep a small-data test of the same code in the normal run. `uv run
  pytest -m slow -q` runs them; CI runs both.
- **Property tests** (`tests/test_properties.py`, Hypothesis): the money and stats kernels against invariants over
  generated inputs. A drawdown is never positive and doesn't depend on the unit, a worst window is missing when too
  short and never worse than the drawdown, a rate is positive and finite or missing and never from a later day, an
  amount round-trips as people write it, a replay never sells more than it holds and a sale leaves the average cost.
  A failure prints the smallest breaking input: pin it as an example test in the kernel's own file (the first one
  found `money.parse_amount("nan")`).

## Layers
- `tests/test_layers.py` runs the import-linter contracts in `pyproject.toml` (the same as `uv run lint-imports`): the
  kernel (`radar.model`) imports neither the studies nor the app, the studies (`radar.backtest`) don't import the
  report builder (`dashboard`, `mine`, `profile`) or the app, the app (`updater`, `report`, `api`, `abtest`,
  `propose`) never imports a study, and the whole package sits in layers that only import downwards (a new module
  needs a layer). A broken contract names the chain of imports; move the shared piece down a layer
  (docs/architecture.md, *Layers*) rather than adding an exception.
- The same file checks what import-linter doesn't: no module uses another one's `_private` names (none does: make the
  name public, or move it where it belongs), and there are no import cycles (a dependency points down a layer; when
  two modules need each other, the shared piece belongs below both). `uv run python tests/test_layers.py` prints the
  current findings.
- The tests don't read private names either (imported, as `module._x`, `monkeypatch.setattr(module, "_x", …)` or
  `"radar.module._x"`): test through the public function (a score variant through `study.BY_KEY[key].fn`), or use
  the public seam a module offers for what a test replaces: its config reader (`external.cfg`, `factors.cfg`,
  `longrun.cfg`, `valuation.screen_codes`), its download (`factors.fetch`, `external.cot_fetch`,
  `constituents.spy_holdings`) or the settings file (`config.load_settings`, through `conftest.with_settings`).
  `TEST_PRIVATE_ALLOWED` in `test_layers.py` is empty and only shrinks.
- In-memory caches: each module that keeps one has a public `reset()` (`api`, `dashboard`, `performance`,
  `fundamentals.context`, `valuation`, `tickers`, `market_views`; also `net.reset()`). `conftest.reset_caches()`
  empties them before and after every test and in `tmp_data`; a test that needs a fresh read mid-way calls the
  module's `reset()` rather than monkeypatching its private cache. A new module with a cache adds its `reset()` and
  its name to `conftest.CACHED`.

## The guide (`guide/`)
- `tests/test_guide.py`: every chapter in `guide/guide.yaml` exists (and no file is left out), each H1 equals its
  manifest title, every `{{settings:…}}` resolves, every link reaches a real chapter, heading or app page, and
  `page_links`/`glossary_links` point at real pages, glossary keys and headings.
- Formulas: `uv run python -c "import json; from radar import guide; print(json.dumps({f'{b}/{s}': guide.chapter(b,
  s)['markdown'] for b, s, _, _ in guide.manifest()['_order']}))" | node web/scripts/check-math.mjs` compiles every
  `$…$` / `$$…$$` with KaTeX and lists the ones that fail.

## Static checks
- `uv run ruff check`: the linter (rules and the few deliberate ignores in pyproject.toml `[tool.ruff]`; lint only,
  no formatter). `uv run mypy`: type checks all of `src/radar` (`[tool.mypy] files`), but loosely: only
  annotated functions are checked (no `check_untyped_defs` yet) and pandas is `Any`, so a wrong column name or an
  untyped `market` passes. Tighten in steps: annotate, then `check_untyped_defs`, then `disallow_incomplete_defs`
  package by package. `uv run pytest -q --cov`: coverage with a floor (`[tool.coverage.report] fail_under`):
  raise it when coverage rises, never lower it to let a change in.

## The command line
- Every `radar` command runs in a test: `tests/test_cli_smoke.py` (the data folder, market data, the app, portfolios,
  fundamentals, the A/B test), `test_cli_studies.py` (`sim`, `study`) and `test_cli_propose.py` (`propose`), each
  invoking the command once on the synthetic world and checking its exit code and a line of output; only network
  sources, the web server and the browser are stand-ins, so the printers run too.
  `test_every_command_has_a_test_that_runs_it`
  fails for a command no test invokes. A `--json` test reads stdout only (`run_json`): progress goes to stderr.

## Practice
- For a bug fix, write the test first and watch it fail on the old code.
- Pin method-sensitive numbers (e.g. RRG values) so a change to a method is deliberate.
- Verify locally before pushing. CI (`.github/workflows/ci.yml`) runs ruff, mypy, `uv run lint-imports`, `uv run
  pytest -q --cov` and `uv run pytest -q -m slow` on Ubuntu, the tests marked `os` on Windows and macOS, and the web
  tests, build and an API-types check (`pnpm -C web gen:api` must leave `web/src/api/schema.ts` unchanged) on every
  pull request and push to main.
- Mark a test file `os` (`pytestmark = pytest.mark.os`) when it exercises what differs between operating systems:
  replacing a file a reader holds open (`config.write_atomic`), `locks.file_lock`, the data folder's move, backups,
  paths with spaces and non-ASCII letters. `uv run pytest -q -m os` runs them (about 20 seconds).
