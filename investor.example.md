# My investor profile

Copy this file to `notes/investor.md` and fill it in. `notes/` stays on your computer (it is never committed or
published). Claude Code reads it before writing briefs, research memos, comparisons or journal entries, so the
advice on accounts and horizon fits you.

## Accounts
<!-- what each account is for. Use the same names as your real portfolios in the app (Portfolio page, or
     `uv run radar portfolios list`): /journal records trades there by name. Rename either side so they match. -->
- **ASK**: aktiesparekonto (17% lager on everything). Good home for momentum trades in stocks and positive-list ETFs.
- **frie midler**: free funds at my broker. Stocks taxed on realisation; positive-list ETFs taxed lager.

Virtual portfolios (simulations, A/B tests) live only in the app; they never count as your holdings.

## Horizon and style
- Typical holding period: 1–6 months, momentum-driven, with a few long-term core positions.
- Benchmark: MSCI ACWI (in DKK).

## Preferences and limits
- Max position size: …
- Sectors or themes I avoid: …
- Anything else Claude should know (e.g. "I can't buy US-domiciled ETFs"): US ETFs aren't sold to retail investors in the EU; prefer UCITS alternatives.

## Market views
Your beliefs about where markets are heading ("AI is in a bubble", "EU rates rise", …) live in the app, on the
*My market views* page, not in this file: there each view gets a conviction, a horizon, what would change your mind,
what it helps or hurts, and the radar's evidence. The skills read them with `uv run radar views --json`.
