# F12 My trading rules: your own rules, and whether an action breaks them: implementation plan

*Written 2026-10-27, against `main` at `f4021c5`. A new feature, not in [the product owner review](analyses/product_owner.md);
it sits in its 0.6 theme "Your own rules" next to F9–F11. Analysis, not advice.*

## 1. Goal and non-goals

**Goal.** A place where you write down the rules you want to trade by. Typical rules: "no single stock above 10 %",
"no buying back within 30 days of a sale", "no adding to a momentum position below its 200-day average", "never
sell more than 15 % of the portfolio in one week". You can then ask the ruleset about a **proposed action**
("buy 20,000 DKK of X in *frie midler*"). The answer says, rule by rule, whether the action breaks the rule, comes
close, or complies, and gives the numbers behind each verdict. It also says what would make the action comply: the
largest amount that fits, or the first day a buy-back is allowed. The rules are a mirror, never a gate. The radar
blocks nothing, sends nothing to a broker and never says "do it".

The feature is surfaced and maintained the way *My market views* is. It has a page under *Mine* with an editor,
templates to start from, an archive and undo-delete, `radar rules [--json]` for the skills, and an export in the
holdings bundle. The data lives in `radar.db` (tier personal).

User stories (MVP):

1. On *Mine handelsregler* I see my active rules, each with its statement in my words, the rule type and its
   numbers, its scope (all real portfolios, one portfolio, an account kind, or a style such as momentum), its
   severity (*hard* / *soft* / *reminder*) and *why I have it*. Archived rules sit in a fold below.
2. I add a rule from a template (e.g. *"Max weight per stock"*, preset to 10 %) or from scratch. A rule the radar
   can check has a type and parameters. A rule it can't check (e.g. "only buy what I can explain in two sentences")
   is a *judgment* rule. It is shown as a question to ask myself, and Claude weighs it in the skills.
3. *Test an action*: I enter buy/sell, ticker, portfolio, an amount (DKK, shares or "all"), and optionally the
   style (momentum / value / core / tactical) and horizon. I get one row per rule, with a verdict (*Bryder* /
   *Tæt på* / *Overholder* / *Gælder ikke* / *Ukendt*), the evidence ("XYZ would be 16.2 % of your real portfolios;
   your cap is 10 %") and the way to comply ("at most 6,400 DKK fits under the cap").
4. *Standing breaches*: without any action, the page lists rules my portfolios break right now (a stock that has
   grown past the cap, a sector above its cap, the core below its floor). The holdings page (*Beholdninger*) gets a
   flag per position, and the monthly brief a short list.
5. From the CLI: `uv run radar rules check buy XYZ 20000 --portfolio "frie midler" [--style momentum] [--json]`.
   Claude uses the same command: "Would selling half my XYZ break any of my rules?" → the `/journal` skill (or a
   plain question) runs it and answers from the verdicts, adding its own reading of the *judgment* rules.
6. When I record a BUY/SELL in the Portfolio editor, its rule verdicts show next to the existing plausibility
   warnings, in the same confirm-before-save flow. When I go ahead anyway, I can give a reason (an *override*),
   and the `/journal` entry records it.
7. *Would my rules have helped?* (PR 5): the rules replayed over my own past transactions, each one checked against
   what was known that day. The page lists which trades a rule would have flagged and how those trades did
   afterwards vs ACWI.

**Non-goals** (backlog, section 6):

- Enforcing anything, or sending an order anywhere. Rules never block a save. They are warnings to confirm, like
  `checks.py`'s.
- A rule language or DSL. Rules are typed (a fixed catalogue with parameters) plus free-text *judgment* rules.
- Statistical claims about a rule's edge. The replay is descriptive and small-n, and it says so (F9 is the place
  for tested rules).
- Alerts or notifications (F5's feed).
- Target-weight rebalancing (F10). A weight cap here only says "you're above it", not how to trade back.

## 2. Licence check

No new data source. Rules read prices (Yahoo, already licensed), the user's transactions and journal (personal),
and the X-ray's exposures. `DATA_LICENSE.md` and `datalicenser.md` don't change.

## 3. What the code does today (findings that shape the design)

| # | Finding | Where | Consequence |
|---|---|---|---|
| C1 | *My market views* is the pattern to copy. The `views`, `view_exposures` and `view_indicators` tables come from an append-only migration. `userstore/viewstore.py` has CRUD, `delete` returning the row for `restore` (undo), `views_version()` and JSON export/import. `market_views.py` (domain layer) has `validate`, `templates()` and `catalogue()` from `config/views.yaml`, plus a `DISCLAIMER`. `api/views.py` has GET/POST/PUT/DELETE/restore, each returning the whole page. `Views.tsx` + `ViewEditor.tsx`. `radar views --json` is read by the skills | `userstore/__init__.py`, `userstore/viewstore.py`, `market_views.py`, `api/views.py`, `web/src/pages/Views.tsx` | A mirror set: `rulestore.py`, `trading_rules.py`, `api/rules.py`, `Rules.tsx` + `RuleEditor.tsx`, `radar rules`. Same shapes, same undo, same page-returning responses. |
| C2 | View exposures already match names to a theme by `etf` (correlation of returns vs ACWI), `sector`, `industry`, `region` and `ticker` | `signals/views.py`, `config/views.yaml` | A *theme cap* rule reuses the same exposure vocabulary and matcher ("AI chips ≤ 25 %" = `etf: SMH` + `industry: Semiconductors`), rather than inventing a second one. |
| C3 | The X-ray computes weights by name, sector, region and currency for any selection of portfolios, with coverage | `xray.py` (`_book`, `_exposure`, `cached`) | Weight and cap rules evaluate *before* and *after* the action on the X-ray's book, so the page and the check agree. The pre/post book is the X-ray's `_book` with the proposed trade applied. Expose a small public function rather than calling `_book`. |
| C4 | `checks.py` already returns `{level, field, message}` issues for a transaction, with warnings that must be confirmed before save | `portfolios/checks.py` (`validate`, `checked`, `effect`) | The editor integration (story 6) adds rule verdicts as extra *warning* issues there. Nothing new in the save flow. |
| C5 | Positions with average cost come from replaying transactions | `portfolios/trades.py` (`replay`, `positions`) | "Average down" and "unrealised loss" rules read the average cost from there. The "last sale of this symbol" comes from the same transaction frame. |
| C6 | 50/200-day averages, 1/3/6-month returns and the momentum score with its rank are in the profile and `radar info` | `signals/technicals.py` (`sma_cross`), `profile.py`, `signals/score.py` | Trend and chase rules read these as of the check day. In the replay they are point-in-time (prices up to that day only). |
| C7 | Journal entries have YAML front matter (`ticker`, `action`, `account`, `horizon`, `views`, `review_by`, `status`) and an *Exit rules* section. `notebook.py` lists them | `.claude/skills/journal/SKILL.md`, `notebook.py` | "Write an exit rule before buying" is checked by looking for an open entry for the ticker. A new front-matter field `style:` (momentum / value / core / tactical) labels a position, so style-scoped rules apply to standing positions too. |
| C8 | Fees are often 0 or missing on imported transactions | the transaction store | Amount-based rules use price × quantity in DKK (`money.py`), never assume a fee. A fee-based rule shows *Ukendt* when fees are missing, never "complies". |

## 4. Design

### 4.1 Modules, by layer

| Layer | Module | Change |
|---|---|---|
| infrastructure | `userstore/__init__.py` | Append-only migration: tables `trading_rules` and `rule_checks` (4.2). |
| domain | `userstore/rulestore.py` | Mirror of `viewstore`: `rules(status)`, `get_rule`, `save_rule`, `delete_rule` (returns the row), `restore_rule`, `rules_version`, `export_rules_json` / `import_rules_json` (all-or-nothing, backup first). `log_check(action, verdicts)`, `set_decision(check_id, decision, reason)`. |
| domain | `trading_rules.py` | Like `market_views.py`: `DISCLAIMER`, `config()` from `config/rules.yaml`, `validate(rule)` (known kind, parameters in range, scope resolvable; `Invalid` naming the first problem), `templates()`, `catalogue()` (kinds with parameter schemas, styles, scopes, the view-exposure vocabulary). |
| pure readings | `signals/rules.py` | One pure function per kind: `(params, ctx) → Verdict{status, value, limit, message, comply}`. `ctx` is a plain dict of numbers and dates, so no I/O. Missing input → `unknown` with the reason. Unit tested per kind, including every "missing" path. |
| features | `rulecheck.py` (new top-level, like `xray.py`) | `context(market, action, scope, today)` builds `ctx` from the X-ray book (pre/post weights by name, sector, theme, core), transactions (last sale, sales in the last N days, trades this month, average cost), technicals (SMA 50/200, 1/3/6 m return, score rank) and the journal (open entry, `style`, exit rules present). `check(action)` runs every active rule whose scope matches. `standing(selection)` evaluates state-only kinds without an action. `replay(start, end)` comes in PR 5. |
| features | `api_models/rules.py` | `RuleIn`, `RuleRow`, `RulesPage`, `ActionIn`, `RuleVerdict`, `CheckResult`, `StandingResult` (`extra="forbid"`), re-exported by `api_models`. |
| interfaces | `api/rules.py` | `GET/POST /api/rules`, `PUT/DELETE /api/rules/{id}`, `POST /api/rules/restore`, `POST /api/rules/check`, `GET /api/rules/standing`, `POST /api/rules/checks/{id}/decision`. |
| interfaces | `cli/portfolios.py` | `radar rules [--json] [--archived]`, `radar rules check ACTION TICKER AMOUNT [--portfolio P] [--style S] [--horizon H] [--date D] [--json]`, `radar rules replay` (PR 5). |
| feature hook | `portfolios/checks.py` | `checked()` gets an optional `rule_issues` callback, passed in from the API so the domain layer doesn't import `rulecheck` (the layers contract). It turns *Bryder*/*Tæt på* into `warning` issues with field `rules`. |
| web | `pages/Rules.tsx`, `components/RuleEditor.tsx`, `components/ActionCheck.tsx`, `components/RuleVerdicts.tsx` | Page `/rules` in *Mine* right after *Market views*. `RuleVerdicts` is reused in the Portfolio editor's confirm dialog. |
| skills | `journal`, `propose-portfolio`, `market-brief`, new `rules` | 4.7. |

Layers (`pyproject.toml`): `trading_rules` joins the domain layer with `market_views`, and `rulecheck` joins the
features layer with `xray`. `signals/rules.py` is in the pure layer, so `tests/test_layers.py` needs no exception.

### 4.2 Data model

```sql
CREATE TABLE trading_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  statement TEXT NOT NULL CHECK (length(trim(statement)) > 0),   -- in the user's words
  kind TEXT NOT NULL,                       -- a key of config/rules.yaml kinds, or 'judgment'
  params TEXT NOT NULL DEFAULT '{}',        -- JSON, validated against the kind's schema
  scope TEXT NOT NULL DEFAULT '{"portfolios": "real"}',  -- JSON: portfolios real|all|[ids], kind, tag, style
  severity TEXT NOT NULL DEFAULT 'soft' CHECK (severity IN ('hard', 'soft', 'reminder')),
  rationale TEXT,                           -- why I have this rule (the lesson behind it)
  template TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE rule_checks (                  -- every check asked from the app or CLI with --log (personal)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL, action TEXT NOT NULL,   -- JSON ActionIn
  rules_version TEXT NOT NULL, verdicts TEXT NOT NULL,   -- JSON, as returned
  decision TEXT CHECK (decision IN ('went_ahead', 'changed', 'dropped')),
  reason TEXT,                              -- the override reason, when going ahead against a rule
  transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL);
```

`params` and `scope` are JSON rather than child tables. A rule has a few scalar parameters (unlike a view's lists
of exposures), except `theme_cap`, whose exposure list is stored inside `params` in the views' `{kind, key, effect}`
shape. Rule severity is the user's own label. The radar shows it and never acts on it.

### 4.3 The rule catalogue (`config/rules.yaml`)

Each kind declares its parameters, what it needs from `ctx`, whether it is *action* (needs a proposed action),
*state* (also checked standing) or both, and its *Tæt på* band. MVP kinds:

| Kind | Params | Breaks when | Comply hint | Needs |
|---|---|---|---|---|
| `max_position_weight` | `pct` | post-trade weight of the name > pct | largest amount that fits | X-ray book |
| `max_exposure_weight` | `pct`, `exposures` (sector / industry / region / etf / ticker list) | post-trade weight of matching names > pct | amount that fits | book + view matcher (C2) |
| `min_core_weight` | `pct`, `core` (tickers or tag) | core share after the trade < pct | – | book |
| `min_ticket` | `dkk` | trade value < dkk | – | price, FX |
| `max_positions` | `n` | number of names after a buy > n | – | positions |
| `no_rebuy_within` | `days` | buy of a symbol sold within `days` | first allowed date | transactions |
| `sell_cooling` | `pct`, `days` | sales in the last `days` + this one > pct of the portfolio | date the window clears | transactions, book |
| `max_trades_per_month` | `n` | trades this calendar month + 1 > n | – | transactions |
| `no_average_down` | `loss_pct` | buy into a position more than `loss_pct` below its average cost | – | `trades.replay` |
| `trend_filter` | `ma` (50/200), `side` buy | buy below the moving average | price level to wait for | technicals |
| `no_chase` | `ret_3m_pct` | buy after a 3-month rise > pct | – | returns |
| `min_score_rank` | `pct` | buy with momentum rank below pct (style momentum) | – | score |
| `account_placement` | `horizon_max`, `account_kind` | tactical action (horizon ≤ max) outside that account kind | – | action horizon |
| `exit_rule_first` | – | buy without an open journal entry with exit rules | "write the entry first" | journal |
| `judgment` | – | never machine-checked: shown as a question | – | – |

Verdict statuses: `breaks`, `near` (inside the kind's band of the limit), `complies`, `not_applicable` (out of
scope, wrong side, or the style doesn't match), `unknown` (an input is missing, named in the message). An
`unknown` never counts as complying. A summary line counts each status per severity.

Templates (`config/rules.yaml` → `templates`) are generic starting points with a suggested `rationale`. Examples:
caps per name and per theme, a core floor, a 30-day buy-back pause, sell cooling-off, no averaging down in
momentum positions, no buying after a 3-month rise above 100 %, exit rule first, a minimum ticket. Committed
config holds only generic templates, never the user's own rules or numbers.

### 4.4 The proposed action and `ctx`

`ActionIn = {side: buy|sell, ticker, portfolio, amount_dkk | quantity | fraction (sell), price?, date? (default
today), style?, horizon?, note?}`. The price defaults to the last close (`checks.session_close`), converted to DKK
with `money`. A sell of `fraction: 1` is a full exit.

`ctx` is built once per check. It holds pre/post weights for the name, every exposure a rule mentions and the core,
the portfolio value, sales and trades in the windows the active rules ask for, the last sale date of the symbol,
the average cost, the SMAs, 1/3/6-month returns, the score rank, the open journal entry (if any) with its `style`,
and whether it has exit rules. Scope is resolved first. A rule scoped to *frie midler* is `not_applicable` to an
ASK action. A style-scoped rule uses the action's `style`, else the open journal entry's, else `unknown`
("unlabelled position").

Selection for weights follows the X-ray's default (real portfolios), so "10 % of what" is always shown: "of your
real portfolios (N DKK, cash unknown)". Without a cash ledger the denominator excludes cash, and the message
says so (as the X-ray does).

### 4.5 Standing checks

`standing(selection)` runs the *state* kinds without an action: name and exposure caps, the core floor and
`max_positions`. Results feed:

- the *Brud lige nu* panel on the Rules page,
- a flag on the holdings table (`/api/me`: `rule_flags` per symbol, from the same function),
- `summary.json["rules"]` → the monthly brief's short list.

### 4.6 API and CLI

- `GET /api/rules` → `RulesPage {disclaimer, rules, templates, catalogue, standing}`. All mutations return the
  page, as in the views API. `DELETE` returns the row for undo.
- `POST /api/rules/check` (`ActionIn`, `log: bool`) → `CheckResult {action (resolved: price, DKK value, date),
  verdicts[], summary, check_id?}`. A `decision` endpoint stores went_ahead/changed/dropped + reason.
- `radar rules check …` prints a table (rule, verdict, evidence, comply hint). `--json` is for the skills. `--log`
  stores it. Exit code 0 in every case: a check that finds breaks has still succeeded.

### 4.7 Skills

- **`/rules`** (new): maintain the ruleset in conversation. It can draft rules from a behavioural review of the
  user's own trades (e.g. "you sold many positions on one day after a drawdown" → a `sell_cooling` draft with the
  rationale in the user's words). It writes only after the user confirms each rule (via the API or a
  `radar rules add --from-json` command). `/rules check <action>` runs the check and reads the *judgment* rules
  against the context.
- **`/journal`**: before writing a buy/sell entry, run `radar rules check … --json --log` and add a *Rules* section
  (breaks/near, and the override reason if the user goes ahead). Add `style:` to the front matter. `/journal review`
  lists open positions that now break a rule (standing) and how past overrides turned out.
- **`/propose-portfolio`**: reads `radar rules --json` and treats `max_position_weight`, `max_exposure_weight`,
  `min_ticket` and `max_positions` as extra caps in its basket. Each pick is checked, and the memo lists any rule
  the basket would break.
- **`/market-brief`**: a line per standing break from `summary.json["rules"]`.

### 4.8 Web

`Rules.tsx` copies `Views.tsx`'s structure: disclaimer, *Brud lige nu* (standing), active rules as cards (statement,
kind and numbers, scope, severity chip, rationale, edit/archive/delete with undo), the archive fold, and *Ny regel* →
`RuleEditor` (template picker, kind-specific parameter fields from `catalogue`, scope picker reusing the portfolio
picker, the views' exposure picker for theme caps). `ActionCheck` is a compact form at the top of the page (side,
ticker search, portfolio, amount, style, horizon). Its result is `RuleVerdicts`, a table ordered breaks → near →
unknown → complies → n/a, with severity. The Portfolio editor's confirm dialog renders `RuleVerdicts` for the row
being saved, with an optional *reason* field when a *hard* rule breaks.

## 5. Steps as PRs

Each PR is green on `uv run pytest -q`, `uv run ruff check`, `uv run mypy` and `uv run lint-imports`, and carries
its guide changes.

| # | PR | Contents | Behaviour change |
|---|---|---|---|
| 1 | **Rule store** | Migration, `rulestore.py`, `trading_rules.py`, `config/rules.yaml` (kinds + templates), `radar rules [--json]`, export/import in the holdings bundle and `radar export`. Upgrade fixture (`scripts/release.py` homes) gains the tables. | New command (list only) |
| 2 | **Evaluator and check** | `signals/rules.py` (all MVP kinds), `rulecheck.py` (`context`, `check`, `standing`), `xray` public book function, `radar rules check`. Layers. `docs/commands.md`, `CLAUDE.md` main commands. | New command |
| 3 | **API and page** | `api_models/rules.py`, `api/rules.py`, `Rules.tsx`, `RuleEditor`, `ActionCheck`, `RuleVerdicts`, nav, route, client, TS types, glossary. New chapter `guide/brugervejledning/handelsregler.md` in `guide.yaml` after *markedssyn*. `navigation.md`. Textbook `adfaerd.md` links to it. `docs/web-app.md`. | New page |
| 4 | **Integration** | `checks.py` hook + editor dialog, `rule_flags` on `/api/me` + `beholdninger.md` *Flagene*, `summary["rules"]`, `rule_checks` decisions. Skills: new `rules`, plus `journal` (`style:`, Rules section), `propose-portfolio` (caps), `market-brief`. `maanedsbrief.md`, `claude-code.md`. | Editor shows rule warnings; flags; brief line |
| 5 | **Replay** | `rulecheck.replay(start, end)`: each real BUY/SELL checked point-in-time (positions before it, prices up to that day, the *current* rules). The page section *Ville reglerne have hjulpet?*: per rule, the trades it would have flagged and their return since vs ACWI over the same days, with n and no significance claim. `radar rules replay [--json]`. | New section and command |
| 6 | **Release** | `CHANGELOG.md`, *Nyheder*, marketing `features.yaml` (the demo copy gets a fictional ruleset). | – |

Dependencies: 2 needs 1. 3 and 4 need 2. 4's editor hook needs 3's `RuleVerdicts`. 5 needs 2 (and 3 for the
page section). 6 comes last.

## 6. Backlog

- Rules with a time dimension, such as a trailing stop from the highest close since purchase, or a time stop per
  style (the proposals' `check_exits` already does this for picks; a shared helper later).
- Linking a rule to a market view ("while view #4 is active, the AI cap is 30 %, else 20 %").
- Compliance statistics: share of actions checked, breaks overridden, and the outcome of overridden vs respected
  breaks (needs months of `rule_checks`).
- Calendar items (F5) for "rebuy allowed from DATE" and "cooling-off ends DATE".
- An F3 tax rule kind (e.g. "realised share losses in *frie midler* only offset against share gains: warn on a
  loss sale").
- F10 can read the caps as rebalancing bands.

## 7. Tests

- `signals/rules.py`: per kind, a breaks/near/complies case, the exact boundary, every missing input → `unknown`,
  and the comply hint (the largest amount fitting the cap equals the cap exactly when bought).
- `rulecheck.context` on the synthetic world: pre/post weights match `xray` for the same selection. A sell of
  `fraction: 1` removes the name. The FX conversion. A rule out of scope is `not_applicable`.
- Store: CRUD, undo-delete, archive, export → import round trip (all-or-nothing on bad JSON), migration on the
  fixture homes (`tests/fixtures/homes`), and no write outside `radar.db`.
- API: page shape (`extra="forbid"`), 404/409 as for views, a check with `log` stores and returns `check_id`.
- Replay: point-in-time, so a rule using the 200-day average never sees a price after the trade date (a test that
  poisons future prices).
- `tests/test_guide.py` for the new chapter. `tests/test_layers.py` passes unchanged.
- Web: `RuleVerdicts` ordering, `ActionCheck` validation (vitest, like `views.test.ts`).

## 8. Docs

- User guide: new chapter `handelsregler.md` (what a rule is, the kinds, severity, *Ukendt* ≠ complies, test an
  action, standing breaks, the replay, the disclaimer). Update `navigation.md`, `beholdninger.md` (the flag),
  `maanedsbrief.md`, `claude-code.md` (`/rules`), `kommandolinjen.md`.
- Textbook: `adfaerd.md` gets a section on pre-commitment (rules written in calm conditions, checked in stressed
  ones; cooling-off; why "sell half" lowers regret). `diversifikation.md` on caps per name and theme.
- `docs/commands.md`, `docs/web-app.md`, `docs/architecture.md` (modules, the two tables), `CLAUDE.md` main commands.

## 9. Definition of done

- I can write the rules from a behavioural review as typed rules, test "buy X for N DKK" and get per-rule verdicts
  with numbers and a comply hint, in the app, the CLI and through Claude, with the same results everywhere.
- Missing data never shows as complying. Every weight says what it is a share of.
- Standing breaches show on the Rules page, the holdings table and in the brief, all from one function.
- Nothing is blocked or sent anywhere. The page and every output carry the disclaimer.
- The replay is point-in-time and shows n, with no significance claims.
- No personal rule, rationale or check ever lands in the repo (the leak check covers `config/rules.yaml`
  templates being generic).

## 10. Decisions taken here, and open questions

**Decided.**

- Typed kinds plus *judgment* rules, no DSL. A DSL would be harder to edit in a form and to explain in Danish, and
  the catalogue covers the behaviours that matter.
- Rules never block. Hard/soft/reminder only order and colour the output.
- The weight denominator is the X-ray's selection (real portfolios by default). One definition, shown every time.
- Theme caps reuse the views' exposure vocabulary and matcher.
- `style` lives on the action and in the journal front matter, not on transactions.

**Open.**

1. Should `rule_checks` log every app check, or only those the user saves / the skills log? (Proposed: log on
   explicit "save" and from skills, to keep it meaningful.)
2. Should a style-scoped rule with an unlabelled position be `unknown` (proposed) or `not_applicable`?
3. Should the replay use today's rules (proposed: yes, it answers "would these rules have helped") or allow a
   rules snapshot as of a date?
4. Should *Test an action* also be reachable from the ticker page (a "Check against my rules" button with the
   ticker prefilled)? Cheap after PR 3. Proposed as part of PR 4.
