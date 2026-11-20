---
name: sector-etfs
description: Find and record, for each sector the radar's rotation overview shows (the 11 GICS sectors and the European supersectors with a UCITS ETF of their own), the go-to UCITS ETF for a Danish investor and its closest peers, with their costs (TER, size, distribution, domicile, tracking difference) read from the issuers, checked against SKAT's positive list and the radar's ranking rule, and saved after the user confirms each sector. The Sector ETFs page then shows them with returns in DKK and vs ACWI and their tax status. Use when the user asks which ETF to buy to get exposure to a sector, wants to refresh or check the sector ETF list, asks for a UCITS alternative to XLK/XLE and the like, or runs /sector-etfs.
argument-hint: "[sector …] [--all]"
---

# Sector ETFs: the go-to UCITS ETF per sector

The rotation overview says which sectors lead and lag, but it measures them with US-listed ETFs (XLK, XLE …) that a Danish retail investor can't buy (no KID), and with STOXX 600 sector funds. `/sector-etfs` answers the next question: **if I want exposure to this sector, which UCITS ETF do I buy?** For each sector it records one go-to ETF and up to seven peers, with what they cost and how they are taxed in Denmark, so the *Sector ETFs* page can show them next to today's returns. It is run now and then by hand (the page says when the record is older than `stale_days`), not on a schedule. This is analysis to support the user's own decisions, not advice.

Read and write through the `mcp__radar__*` tools; their descriptions carry the units and the fields. If the `radar` tools aren't connected, use the CLI instead: `uv run radar paths --json` for the folders, `uv run radar sector-etfs --json`, `uv run radar sector-etfs candidates <SECTOR> --json`, `uv run radar sector-etfs history --json`, and read `notes/investor.md`. Without the tools there is no `sector_etfs_save`: write the memo, tell the user the record was not saved, and list the per-sector fields so it can be saved in a later session with the tools.

**Write the memo and your reply in Danish.** Follow `guide/STIL.md` for tone ("du", plain and precise), number format (decimal comma, "0,25 %") and its fixed terms (positivlisten, aktiebaseret, lagerbeskatning, ASK / frie midler …). Keep tickers, ISINs and fund names as they are.

**Arguments:** sector keys to cover (`/sector-etfs Technology Banks`; the keys are those of `sector_etfs_view`, e.g. `Financial Services`, `Autos & Parts`). Without arguments, cover the sectors that are missing, flagged `recheck` or older than `stale_days`; `--all` covers every sector. A run that covers some sectors keeps the others as they were (they are carried over with their own date).

## The rule the code ranks by (say it in the memo)

1. **Tax first:** on SKAT's positive list for the year (aktiebaseret: lagerbeskattet as share income, allowed on an aktiesparekonto) before unknown, before off the list (capital income, not on an ASK).
2. **Size:** a fund smaller than `min_aum_musd` (USD millions) ranks below every fund that isn't; a small fund can close or be merged.
3. **TER**, lowest first.
4. **Tracking difference** (the fund's return minus its index's, a year), highest first, when known.
5. **Accumulating before distributing** (no dividend to reinvest; lagerbeskatning taxes both alike).

The go-to is normally the ranking's first. Pick another only for a reason the rule can't see (a better index for a Danish investor, a fund about to close, a share class that the user's broker doesn't offer, a broad world fund rather than a US-only one), then set `rank_override` and write the reason in one sentence. Prefer a **world** (MSCI World sector) fund as the go-to for a GICS sector, list the US and Europe variants as peers, and say what the difference in exposure is. For an EU supersector the go-to is a Europe fund.

## Steps

1. **Context** (one round of calls):
   - `investor_notes`: which accounts the user has (ASK, frie midler, pension) and their broker (Saxo, Nordnet …), which matters for which listings they can buy.
   - `sector_etfs_view()`: the current record, its age, and per sector `recheck`, `stale`, the rotation rows and every ETF's tax status.
   - `summary(sections=["rotation"])`: where each sector stands now (the memo leads with the sectors in Leading or Improving).
   - The last memo, via `documents(kind="sector_etfs")` and `read_document`, if there is one.
2. **Candidates per sector:** `sector_etf_candidates(sector)` for each sector in scope (send them together). You get the record's ETFs, the seeds of `config/sector_etfs.yaml` and matching ETFs of the discovery pool, each with returns in DKK, Yahoo's cached TER and its tax status. The pool is name-matched: drop a fund whose index isn't the sector (a biotech fund under Technology, a single-country fund).
3. **Research the facts, per candidate** (WebSearch, standard mode; send the searches together): the issuer's product page or factsheet first (iShares, Xtrackers/DWS, SPDR, Amundi, Invesco), justETF for a cross-check and for tracking difference. For each fund record:
   - `ter` (a fraction: 0.25 % is 0.0025), `aum_musd` (fund size in USD millions; convert from EUR at today's rate and say so), `distribution` acc | dist, `domicile` (IE, LU, DE), `currency` (the share class's), `index`, `issuer`
   - `tracking_diff`: the fund's return minus its index's over the latest full year, as a fraction (−0.0012 for −0,12 %), only from a source that states it; otherwise null
   - `sources`: the URLs you read, and `checked`: today's date
   - new launches and closures or mergers in the sector

   **Never invent a figure.** An unknown is null, and the memo says it is unknown. Read free pages only; never try to get around a paywall or a login. Check that the ISIN is the share class you mean (accumulating vs distributing classes have different ISINs) and that the ticker is a Yahoo listing of that share class (`ticker_profile` when in doubt); prefer a Xetra or London listing the user's broker is likely to offer.
4. **Choose per sector:** keep the go-to and up to seven peers, at least one per scope (world, us, europe) where one exists. Then call `sector_etfs_save(sectors=[…], note=…)` **without** `confirm`: a dry run that ranks each sector with today's data and returns `warnings` (the pick isn't first; the pick is off the positive list) and `changes` against the latest record (a new pick, ETFs added or dropped, a TER that moved). Fix what it refuses (a bad ISIN check digit, a TER that isn't a fraction) and run it again.
5. **Show the user one card per sector** (a few lines each, in Danish): the go-to with TER, size, acc/dist, domicile and *positivlisten ja/nej* (ASK ja/nej), the peers in one line each, the change from last time, and the reason when the pick isn't the rule's first. Then one AskUserQuestion call with one question per sector (at most four per call; ask again for the rest), the options *Gem* (save as shown) and *Spring over* (keep the current record for this sector), and room for their own words. A sector they want changed: change it and show its card again.
6. **Save** the sectors the user said yes to: `sector_etfs_save(sectors=[…], note=…, confirm=true)`. If it refuses a ticker (no Yahoo prices), use another listing of the same share class or drop that fund, and save again. Never save a sector the user didn't confirm.
7. **Write the memo** (below) with `write_memo(kind="sector_etfs", name="YYYY-MM-DD")` (if one exists for today, read it and write `YYYY-MM-DD-2`), and pass its name as `report` if you save again.
8. **Reply in Danish:** 3–6 lines: the sectors updated, the picks that changed and why, any fund that is leaving the positive list next year (`tax.next_year` = `no`), a link to the memo, and that the *Sector ETFs* page shows them. If the user wants to act on one, point to `/research <ticker>`, `/compare` and their trading rules (`/rules check`). Never suggest a trade size.

## Memo structure

```markdown
---
date: YYYY-MM-DD
sectors: [Technology, Banks]       # the sectors this run covered
record: YYYY-MM-DD                 # the id sector_etfs_save returned, or null if not saved
---
# Sektor-ETF'er – YYYY-MM-DD
*Analyse, ikke rådgivning. Go-to-fonden er den, der passer bedst til reglen nedenfor for en dansk investor, ikke en anbefaling om at købe.*

## Kort fortalt
3–5 bullets: what changed since last time, which sectors lead in the rotation and their go-to, anything to watch (a fund leaving positivlisten, a closure).

## Reglen
The ranking rule in five lines, with the size floor (`min_aum_musd`) and the year of positivlisten used.

## Sektorer
### <Sektor> (<key>) · <quadrant> i rotationen
| | Fond | Ticker | ISIN | Omfang | TER | Størrelse | Akk./udb. | Domicil | Positivlisten | 3 mdr. (DKK) | vs ACWI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ★ | … |
- **Hvorfor go-to:** one sentence (and the reason for an override)
- **Forskellen på verden, USA og Europa:** one or two sentences on the exposure
- **Ændret siden sidst:** …

## Ukendt og forbehold
Figures that are unknown and why; currency conversions; share classes not checked.

## Kilder
```
