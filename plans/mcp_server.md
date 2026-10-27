# MCP server: the radar as tools for the skills: assessment and implementation plan

*Written 2026-10-26 against `main` at `59f4236` (after the Evidence page's study runs). Analysis, not advice.*

## 1. Goal and non-goals

**Goal.** The skills (`/market-brief`, `/research`, `/compare`, `/journal`, `/propose-portfolio`, `/hindsight`) reach
the radar through typed, discoverable tools rather than shell calls and file paths. That means fewer calls, smaller
reads, no Windows quoting, and one permission for Claude to ask for. The server exposes the same feature functions
the CLI and the web API call (`docs/architecture.md`, *one function per job*). It adds no new numbers and no new
data source.

**Verdict.** Worth doing, as a **small, task-shaped, mostly read-only** MCP server that runs **in-process** (stdio,
`uv run radar mcp`) on the feature functions. It should not be a generated wrapper around the ~100 REST endpoints,
and it should not depend on `radar serve` running. The project is gated: after phase 1, two skills are migrated
and measured, and phases 2–3 go ahead only if the saving is real (section 7).

User stories (MVP = phase 1):

1. `/research NVDA` reads the profile, the sector's rotation, my holdings and journal history for NVDA, my views
   and the next earnings date in a handful of tool calls. It never runs `radar paths` and never reads the whole
   `summary.json`.
2. `/compare` gets the side-by-side table for several tickers, with the units in the tool's description, not in a
   schema section of the skill.
3. A tool result says how old its data is (`asof`, `age_days`, `stale`), so a skill never works out freshness by
   hand.
4. Missing data is `null` in every tool result, never 0.
5. One permission (`mcp__radar__*`) covers the reads. Writes are separate, clearly named tools (phase 3).

**Non-goals.**

- A generated tool per REST route (`FastMCP.from_fastapi`). That would be page-shaped, about 100 tools, many of
  them destructive (data-home restore, imports, tax openings).
- An HTTP or network transport. stdio only, so nothing listens on a port.
- Tools for deleting, restoring, importing or changing settings.
- `/marketing`. It drives a browser and a demo copy and stays on the shell.
- A remote or claude.ai connector. The server is local, for the user's own Claude clients.

## 2. Licence and privacy check

There is no new data source, so no terms change. Add one line to `DATA_LICENSE.md` and
`guide/brugervejledning/datalicenser.md`: the MCP server serves already-downloaded data and the user's own data
only to the user's own local Claude client, over stdio, with no network listener. Nothing is redistributed.
`.mcp.json` is committed and holds only the launch command, no personal data. Personal data (holdings, journal,
notes) can be reached only through tools that a local client calls. `scripts/leak_check.py` covers the repo as
before.

## 3. What the code and skills do today (findings that shape the design)

| # | Finding | Where | Consequence |
|---|---|---|---|
| M1 | Six skills repeat the *Where files are* paragraph, run `radar paths --json` and build full Windows paths for every read, write and `--out` | e.g. `.claude/skills/propose-portfolio/SKILL.md:12` | A `paths` tool, and tools that address files by kind and name, so prompts no longer carry paths |
| M2 | Large JSON is read whole: `summary.json` (market-brief reads about 15 sections), multi-ticker `info`, propose `evaluate`. Skills carry long schema sections to make up for it | market-brief L20–36, compare L24–55, propose L28–52 | Sliced tools (`summary(sections)`) and tool descriptions that carry the units |
| M3 | Freshness is checked by hand: discovery under 10 days, score study under 35 days, propose study `stale`, whether `live-YYYY-MM` exists | market-brief, hindsight, propose | Tools return `asof`/`age_days`/`stale`, reusing the rule in `api/common.reading` |
| M4 | Picks JSON is written by hand, then frozen, then the printed path is tracked, then evaluated | propose L77–98, hindsight L77–92 | Phase 2: `propose_freeze(picks)` takes structured input and returns the id |
| M5 | Loops make one shell call per ticker: the journal review runs `info` per open entry; the whole `calendar --json` is read for one name | journal L53, research L26 | Tools take several symbols and a symbol filter |
| M6 | The CLI and the API already call the same feature functions | `xray.build`/`cached`, `attribution.build`, `agenda.collect`, `evidence.build`, `tax.year_report`, `portfolios.performance.compare`, `profile.build`/`compare`, `market_views.with_evidence` | The MCP layer is thin glue over them, like `cli/` and `api/` |
| M7 | `cli/common.portfolio_ids` resolves names but raises `SystemExit`. `api/common.selection` takes ids and raises `HTTPException` | `cli/common.py`, `api/common.py` | `radar.mcp` resolves names itself (`userstore.portfolio_by_name`) and raises `errors.NotFound` |
| M8 | Long jobs record themselves in `ops.db` and lock across processes (`locks.Busy`, `study.lock`) | `cli/common.job`, `updater.UpdateJob`, `studyrun.StudyJob` | Phase 2 job tools run in the MCP process and still show on the Operations page |
| M9 | The layers contract is exhaustive (`pyproject.toml`, `tests/test_layers.py`) | – | `mcp` joins the interfaces layer, and is added to the forbidden lists of `model`/`backtest` and to the "app never runs a study" sources |
| M10 | The desktop scheduled task runs `/market-brief` monthly | `CLAUDE.md` | Each skill keeps one line as a CLI fallback when the `radar` tools aren't connected |

## 4. Design

### 4.1 Modules, by layer

| Layer | Module | Change |
|---|---|---|
| interfaces | `src/radar/mcp/` (new package) | `server.py` builds the `FastMCP("radar")` instance and registers the tools from `tools_*.py`. `common.py` has the glue: market loading, portfolio selection, freshness, JSON-safe results |
| interfaces | `cli/server.py` | `radar mcp`: runs the server over stdio. It is gated like other data commands (it needs a data folder) |
| – | `pyproject.toml` | Dependency `mcp`. Layers `"__main__ : api : cli : mcp"`. `radar.mcp` added to the forbidden lists of `model` and `backtest` and to the "app never runs a study" sources |
| – | `.mcp.json` | `{"mcpServers": {"radar": {"command": "uv", "args": ["run", "radar", "mcp"]}}}` |
| tests | `tests/test_mcp.py` | Drives the server through the SDK's in-memory client on the synthetic world |

### 4.2 Output contract

- A tool returns the same view dict as the matching `--json` command or API route, made JSON-safe by `jsonsafe`.
  NaN and inf become `null`, and missing values stay `null`.
- Each tool's description names the units: returns and weights are fractions (0.12 = 12 %), money is DKK, and
  `null` means n/a.
- Errors are `errors.RadarError` subclasses. The SDK turns them into a tool error carrying the message.
- Readings from `dashboard.json`/`summary.json` carry `asof`, `age_days`, `stale` (the price-age limit in settings).
  Study reports carry their own age.

### 4.3 Tools by phase

**Phase 1: read-only.**

| Tool | Feature function | Replaces |
|---|---|---|
| `data_paths()` | `datahome.home.status`, `paths.folders` | `radar paths --json` |
| `investor_notes()` | the data folder's `notes/investor.md` | reading the file by path |
| `market_views(archived=False)` | `market_views.with_evidence` | `radar views --json` |
| `summary(sections=None)` | `reports/summary.json`, sliced, with its age | reading the whole file |
| `ticker_profile(symbols, personal=False, portfolios=None)` | `profile.build` + `legacy_info` / `profile.compare` | `radar info` |
| `portfolios()` | `userstore` listing | `radar portfolios list --json` |
| `performance(portfolios=None, tags=None, start=None)` | `portfolios.performance.compare` | `radar performance --json` |
| `portfolio_xray(...)`, `attribution(...)` | `xray.build`, `attribution.build` | `radar xray/attribution --json` |
| `calendar(..., days=None, symbols=None)` | `agenda.collect`, filtered by symbol | `radar calendar --json` |
| `evidence_view()` | `evidence.build` | `radar evidence --json` |
| `study_reports()` | `reports/*-study.json`: asof, age, `stale` | file age checks by hand |
| `journal_entries(status=None, symbol=None)` | `notebook` listing, front matter | grepping `journal/` |
| `documents(kind=None, ticker=None)` | `notebook.listing` | listing folders by hand |
| `read_document(kind, name)` | `notebook.document`: research memo, brief, proposal, journal entry | reading a file by path |

**Phase 2: jobs and engines.** `job_start(kind)` / `job_status(kind)` on `updater.JOB`, `REPORT_JOB` and
`studyrun.STUDY_JOB`. `propose_candidates`, `propose_freeze(picks)`, `propose_evaluate(id)`, `propose_check`,
`propose_review`. `sim_picks_candidates`, `sim_picks`.

**Phase 3: narrow writes.** `write_memo(kind, name, markdown)` writes atomically (`guard`) to a folder from
`paths.REGISTRY`. `add_trade(..., confirm=False)`: without `confirm` it returns the checks' warnings and saves
nothing, the same flow as `--yes` in the CLI.

### 4.4 Skill migration

Each skill prefers the `mcp__radar__*` tools and keeps one line of CLI fallback. The *Where files are* paragraph
and the schema sections that tool descriptions now cover are removed. One skill per PR: `/research` and
`/compare` (phase 1, the gate), then `/journal`, `/market-brief`, `/propose-portfolio` and `/hindsight`.

## 5. Increments (backlog tasks)

| # | Increment | Depends on |
|---|---|---|
| 1 | Scaffold `radar.mcp`, the `radar mcp` command, `.mcp.json`, dependency and layer contracts | – |
| 2 | Shared glue: market loading, portfolio selection by name or tag, freshness, errors | 1 |
| 3 | Read tools: paths, investor notes, views, summary sections | 2 |
| 4 | Read tools: ticker profile, portfolios, performance, X-ray, attribution, calendar, evidence | 2 |
| 5 | Read tools: journal entries, documents, study reports with age | 2 |
| 6 | `tests/test_mcp.py` on the synthetic world | 3, 4, 5 |
| 7 | Migrate `/research` and `/compare` (with CLI fallback); measure calls and tokens | 6 |
| 8 | Go/no-go gate for phases 2–3 | 7 |
| 9 | Job tools (update, report, study) | 8 |
| 10 | Engine tools: propose and sim picks | 8 |
| 11 | Write tools: `write_memo`, `add_trade` with `confirm` | 8 |
| 12 | Migrate `/journal`, `/market-brief`, `/propose-portfolio`, `/hindsight` | 9, 10, 11 |
| 13 | Docs, guide chapter `claude-mcp.md`, licence lines, `CHANGELOG.md` and *Nyheder* | 12 |

## 6. Verification

- `uv run pytest -q`, including `tests/test_mcp.py`, which checks that:
  - every tool runs on the synthetic world;
  - results are JSON-safe, and `null` stays `null`;
  - an unknown portfolio or ticker gives a tool error with a message;
  - phase 3 writes touch only `REGISTRY` paths.
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports`.
- `uv run pytest -q tests/test_guide.py` once the guide chapter exists.
- By hand: `/mcp` in Claude Code shows `radar` connected. `/research` with the migrated skill makes no `radar
  paths` call and reads no whole `summary.json`.
- The scheduled brief: check whether the desktop scheduled task picks up the project `.mcp.json`. If it doesn't,
  the CLI fallback still produces the brief.

## 7. The go/no-go gate

After increment 7, run `/research` and `/compare` on the same tickers with the CLI version and the MCP version, and
record the tool calls and input tokens of each run here. Continue with phases 2–3 if the MCP version saves about
30 % or more. Otherwise, stop at phase 1, move the slicing (`summary --section`, `calendar --symbol`) into the CLI,
and leave the other skills on the shell.

**Measured 2026-10-26 (TASK-6.7)** on the user's data folder, `/research NVDA` and `/compare NVDA AMD` (a second set,
`/research MU` and `/compare MU 000660.KS AMD`, gave the same picture). The script ran each skill's data phase both
ways: the CLI commands and file reads the old skill text prescribes, and the same tool wrappers the server
registers, so each result is the text the client gets. The web research and writing the memo are the same either
way and are left out. Sizes are characters put into context; tokens ≈ characters / 4 (JSON is a little denser).
This is not a live agent run: an agent may skip an optional step (views, calendar), and every result is resent
with each later turn, which scales both versions alike.

| Skill | Version | Calls | Context from calls | ≈ tokens | Skill text |
|---|---|---|---|---|---|
| `/research` | CLI | 10 | 209,600 chars | 52,000 | 8,200 chars |
| `/research` | MCP | 8 | 72,100 chars | 18,000 | 7,000 chars |
| `/compare` | CLI | 6 | 142,000 chars + `longrun-study.json` (1,187,000) | 35,500 + see below | 10,900 chars |
| `/compare` | MCP | 5 | 164,000 chars | 41,000 | 10,400 chars |

- `/research`: **−66 %** context, 2 calls fewer. Most of the saving: `summary.json` whole (140k) vs
  `summary(["rotation"])` (27k), `calendar --json` (14k) vs `calendar(symbols)` (1k). No `radar paths` call;
  `data_paths` (0.9k) is called only to write the memo.
- `/compare`: the profiles are 22 % smaller over MCP (54k vs 70k for the `--out` JSON, read by the skill and again
  by its red team). The CLI red team was pointed at `longrun-study.json`, which at 1.19M chars no agent reads whole.
  The Read tool stops at about 25k tokens, so in practice it read some part and maybe not the base rates.
  `evidence_view(sections=["longrun"])` (added for this; 53k) returns the card with `base_rates`. Counting the CLI
  red team's read at the Read limit (about 100k chars), the CLI total is about 242k against 164k: **−32 %**. Without
  the red team's long-run read: −22 %.
- One-off cost: the 15 tool descriptions add about 7,000 chars (≈ 1,800 tokens) to a session that has the `radar`
  server connected, whether or not a skill runs.
- Not yet checked by hand: a live `/research` in a session with `radar` connected (`/mcp`), and whether the desktop
  scheduled task loads `.mcp.json` (section 8, question 1).

**Decision 2026-10-27 (TASK-6.8): go.** Phases 2–3 go ahead (tasks 6.9–6.13 kept). Both skills together:

| Counting `/compare`'s long-run read | CLI | MCP | Saving |
|---|---|---|---|
| Both sides left out (CLI file, MCP `evidence_view`) | 352k chars | 183k chars | −48 % |
| CLI at the Read limit, MCP as measured | 452k chars | 236k chars | −48 % |

Both clear the 30 % bar, and `/research` alone (−66 %) would. `/compare` alone sits at −22 % to −32 %, because its
bulk is the profiles, which are the same data either way. That is not a reason to stop: the skills left for phase 2
have more of what the tools cut. `/market-brief` reads about 15 sections of `summary.json`, the journal review runs
`info` once per open entry, and propose and hindsight write picks JSON by hand (findings M2, M4, M5). The fixed cost
(about 1,800 tokens of tool descriptions per session) is small next to one run's saving. Phase 2 is still to be
measured on what it migrates: `/market-brief`'s data step is compared against the CLI the same way before task 6.13
releases it.

## 8. Open questions

1. Does the Claude desktop scheduled task load project MCP servers? This decides whether `/market-brief` can rely
   on the tools or needs the fallback for good.
2. Should `ticker_profile` for an untracked ticker be allowed to download prices (about 10 s, like the profile
   page), or only read what is tracked unless `refresh=True`?
3. Phase 2 job tools: should the MCP process run the update itself (as the CLI does), or hand it to a running app
   when there is one, so that the app's progress bar shows it?
