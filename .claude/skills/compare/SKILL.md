---
name: compare
description: Compare two or more stocks or ETFs side by side and work out, honestly, the case for each one relative to the others and to simply holding ACWI. A fixed rubric from the radar's data, bull and bear per ticker, a red-team pass, risk and sizing, and a decision record. Use when the user asks to compare, contrast or choose between tickers, or runs /compare.
argument-hint: <ticker> <ticker> [...] [--personal] [--horizon 3m]
---

# Compare tickers

Read `notes/investor.md` first if it exists: the user's accounts, horizon and preferences.

Output goes to `research/compare/YYYY-MM-DD_<T1>-<T2>[-...].md`. Reply with the summary table and a link.
Everything here is analysis of a setup, not a recommendation to buy or sell.

**Defaults:**
- **Horizon:** 3 months (the radar's 1–6-month momentum focus), unless `notes/investor.md` or the user says otherwise.
- **Personal data:** off. Use `--personal` only when the user asks for it or passes the flag. Without it, don't use
  their positions, journal or memos, and don't infer them.

## Data conventions (the JSON you'll read)
- **Units:**
  - Returns and percentages are **fractions** (0.12 = 12%).
  - `price.returns` is in the listing currency, `price.returns_dkk` in DKK. Risk statistics are in **DKK**, on
    complete weekly returns.
- **Missing data:** a missing value is `null`, never 0. Each section has `status` (`ok` / `stale` / `missing`),
  `source` and `asof`, and `context.notes` explains the gaps. Write "n/a" for them; never fill them in.
- **`gauges`:** each has `level` −4…+4 (+ favourable, − warning) and a `label`. `context.watchouts` lists the red
  ones.
- **`risk.windows`:** for 1y and 3y, `beta ± beta_se` with `r2` and an `alpha_ann` with `alpha_t`. Treat
  |t| < 2 as noise, and check whether 1y and 3y agree before leaning on either.
- **`risk.factors`:** loadings on ACWI and on tilts (factor ETFs and the sector ETF minus ACWI), with t-stats.
  This shows whether a "great stock" is really momentum, value or sector exposure.
- **`table`:** rows `{metric, direction, values: {SYM: v, ACWI: v}, best}`. Use it rather than re-deriving numbers.
- **P/E basis:** `fundamentals.forward_pe` is Yahoo's and may be on next year's EPS. Use the table rows "P/E on
  this year's / next year's EPS estimate" and always name the year. A low P/E on a cyclical's record earnings is
  a peak signal as much as a value signal; treat it as both, not as an argument for one side.
- **Analyst targets** are rescaled to the radar's dividend-adjusted prices (so they aren't round numbers);
  `rec_mean` and the monthly `recommendations` breakdown can disagree (both from Yahoo). Quote the breakdown.
- **`correlation`:** weekly DKK returns over 1y. With `--personal` it also includes the user's holdings.
- **`levels`:** the radar's mechanical stop rule. `risk.budget` is the position size (share of the portfolio) at
  which hitting that stop costs 1%. Above 1 means the stop is too close for the rule to bound risk.

## Steps

1. **Data**: run `uv run radar info <T1> <T2> ... [--personal] --out exports/<date>_<tickers>.json` and read the
   file.
   - **Errors:** stop and tell the user about any `error` entry (wrong symbol?).
   - **Stale data:** note it, e.g. if `regime.asof` is more than a week old (suggest `uv run radar run`).
   - **Gaps:** collect them per ticker from `status`, `null` values and `context.notes`.

2. **Frame**: what do the tickers share, and where do they differ (same industry, sector, region, stock vs ETF,
   currency)? Peers in one industry get head-to-head valuation. Names from different sectors are compared on
   momentum, risk and portfolio role. The comparison set always includes **ACWI** as the do-nothing
   alternative.

3. **Rubric first, from the JSON only**, before reading any news. One row per axis; columns for the tickers and
   ACWI. Each cell is a short verdict plus the field it came from (e.g. `momentum.r12_1 +48%`):
   - **Momentum:** score, 12-1m, trend, vs ACWI 3m (the radar's main, evidence-backed edge)
   - **Earnings momentum:** `analyst.eps[*].chg_30d`, target change, revisions up/down
   - **Valuation vs growth:** forward P/E, EV/EBITDA against revenue and earnings growth
   - **Quality:** margins, ROE, debt/equity
   - **Risk:** 1y vol, downside beta, 3y max drawdown, the stock-specific share (`idio_vol_ann`)
   - **Rotation tailwind:** `peers.rotation.quadrant` of the sector ETF
   - **Stretch and crowding:** RSI, %B, `from_high`, red watch-outs
   - **Practicalities:** UCITS/positive list (ETFs), currency, next earnings date inside the horizon

4. **Facts from the web** (send the searches together, extended mode if thin):
   - **What to look up:** the last 1–2 quarters vs expectations and guidance, catalysts and the earnings date
     inside the horizon, and anything step 1 listed as a gap.
   - **How to use it:** cite every fact. If a web number differs from the radar's, show both. Don't overwrite.

5. **Bull and bear per ticker**: three arguments each way, each tied to a rubric cell or a cited source. Label
   anything that rests on neither as *narrative*. Drop arguments the data contradicts; don't soften them.

6. **Red team**: launch a separate subagent (general-purpose) with only the JSON path and your step-5 text. Its
   brief:
   - attack each bull case
   - write a pre-mortem per ticker ("it's down 30% at the end of the horizon: the most likely reasons")
   - reverse-engineer what the forward P/E implies about growth and say whether that is plausible against the
     estimate trend

   Fold its strongest points into the memo, credited as red team.

7. **Relative verdict**: for each ticker, "the case for X over the others and over ACWI", and what you give up by
   choosing it.
   - "None of these beats ACWI on this rubric" is a valid outcome. Say it when it's true.
   - Check the factor reading: if a name's edge is mostly a factor or sector loading, say so. The same exposure
     might be cheaper through the sector or factor ETF.

8. **Risk and sizing**:
   - **Correlations:** between the candidates. Two names correlated above 0.7 are largely one bet. With
     `--personal`, also their correlation with current holdings, and existing positions.
   - **Sizing:** `risk.budget` at the rule stop, and the beta and downside beta behind it. Note an earnings date
     inside the horizon as event risk.

9. **Decision record**, for each name worth acting on:
   - the expected outcome over the horizon and a rough probability
   - what's priced in, per the red team
   - kill criteria the user can observe (close below the 200-day average, guidance cut, sector quadrant to
     Lagging, a red watch-out, the stop)

   Offer to log a decision with `/journal`, so `/journal review` can check it later.

## Template

```markdown
# <T1> vs <T2> [vs …] – comparison
*YYYY-MM-DD · data as of <asof> · horizon <h> · personal data: included / not included · not advice*

## Summary
| | <T1> | <T2> | ACWI |
|---|---|---|---|
| Momentum | … | … | … |
| Earnings momentum | … | … | – |
| Valuation vs growth | … | … | – |
| Quality | … | … | – |
| Risk (vol / downside β / max DD) | … | … | … |
| Rotation tailwind | … | … | – |
| Stretch / watch-outs | … | … | – |
| **Case in one line** | … | … | do-nothing alternative |

## Framing
## <T1>: bull / bear
## <T2>: bull / bear
## Red team
## Relative verdicts (vs each other and vs ACWI)
## Risk, correlation and sizing
## Decision record
| Ticker | Expected (horizon) | Probability | Priced in | Kill criteria |
## Gaps (n/a) and data freshness
## Sources
```

## Ground rules
- Facts (with their JSON field or source) and interpretation are kept apart. No invented numbers.
- The same rubric applies to every ticker. Don't add axes because one name looks good on them.
- Beta, alpha and Sharpe are descriptive and noisy. Quote the standard error or t-stat with them.
- The memo describes setups and trade-offs; it doesn't tell the user what to buy.
