---
name: sector-etfs
description: Find and record, for each sector the radar's rotation overview shows (the 11 GICS sectors and the European supersectors with a UCITS ETF of their own), the go-to UCITS ETF for a Danish investor and its closest peers, with their costs (TER, size, distribution, domicile, tracking difference) read from the issuers, checked against SKAT's positive list and the radar's ranking rule, and saved directly (the user isn't asked). The first run picks every sector; on the Sector ETFs page the user marks a go-to they don't want for replacement, and the next run re-selects only those sectors (`reselect-all` re-selects every one). The page shows them with returns in DKK and vs ACWI and their tax status. Use when the user asks which ETF to buy to get exposure to a sector, wants to refresh, replace or check the sector ETF list, asks for a UCITS alternative to XLK/XLE and the like, or runs /sector-etfs.
argument-hint: "[sector …] [reselect-all]"
---

# Sector ETFs: the go-to UCITS ETF per sector

The rotation overview says which sectors lead and lag, but it measures them with US-listed ETFs (XLK, XLE …) that a Danish retail investor can't buy (no KID), and with STOXX 600 sector funds. `/sector-etfs` answers the next question: **if I want exposure to this sector, which UCITS ETF do I buy?** For each sector it records one go-to ETF and up to seven peers, with what they cost and how they are taxed in Denmark, so the *Sector ETFs* page can show them next to today's returns.

It is run by hand, not on a schedule. The first run picks every sector. After that the user marks a go-to they don't want (not traded at their broker, too expensive …) with *Mark for replacement* on the page, and the next run replaces only those. Claude picks and saves; the user doesn't approve each sector, they mark what they don't want afterwards. This is analysis to support the user's own decisions, not advice.

Read and write through the `mcp__radar__*` tools; their descriptions carry the units and the fields. If the `radar` tools aren't connected, use the CLI instead: `uv run radar paths --json` for the folders, `uv run radar sector-etfs --json`, `uv run radar sector-etfs candidates <SECTOR> --json`, `uv run radar sector-etfs history --json`, and read `notes/investor.md`. Without the tools there is no `sector_etfs_save`: write the memo, tell the user the record was not saved, and list the per-sector fields so it can be saved in a later session with the tools.

**Write the memo and your reply in Danish.** Follow `guide/STIL.md` for tone ("du", plain and precise), number format (decimal comma, "0,25 %") and its fixed terms (positivlisten, aktiebaseret, lagerbeskatning, ASK / frie midler …). Keep tickers, ISINs and fund names as they are.

## Which sectors this run re-selects

- **No arguments:** `run_scope` of `sector_etfs_view` decides, so the page, the CLI and the skill agree.
  - `first` (no record yet): every sector. Pick and save them all without asking.
  - `replace`: only `run_scope.sectors`. Those are the sectors whose go-to the user marked for replacement on the page (`replace`, with their reason), plus any sector not covered yet. Every other sector keeps its go-to, even when it is stale or flagged `recheck`.
  - `none`: nothing is marked. Do no research. Reply in two or three lines:
    - nothing is marked for replacement;
    - the record is stale (`stale`) or some sectors are flagged `recheck`, if so;
    - a go-to is marked on the *Sector ETFs* page, and `/sector-etfs reselect-all` re-selects everything.

    Then stop.
- **`reselect-all`:** every sector, from scratch.
- **Sector keys** (`/sector-etfs Technology Banks`; the keys of `sector_etfs_view`, e.g. `Financial Services`, `Autos & Parts`): just those, re-selected.

A run that covers some sectors keeps the others as they were (they are carried over with their own date).

**Rejected funds.** A fund the user marked for replacement in a sector is `rejected` there (`sector_etf_candidates` marks it, with `rejected_reason`), also under `reselect-all`.
- Never pick it as that sector's go-to: `sector_etfs_save` refuses it. It may stay as a peer.
- Read the reason and act on it. "Not traded at my broker" means the new go-to must be a fund or listing that broker offers (check `investor_notes`); "too expensive" means a cheaper one.

## The rule the code ranks by (say it in the memo)

1. **Tax first:** on SKAT's positive list for the year (aktiebaseret: lagerbeskattet as share income, allowed on an aktiesparekonto) before unknown, before off the list (capital income, not on an ASK).
2. **Size:** a fund smaller than `min_aum_musd` (USD millions) ranks below every fund that isn't; a small fund can close or be merged.
3. **TER**, lowest first.
4. **Tracking difference** (the fund's return minus its index's, a year), highest first, when known.
5. **Accumulating before distributing** (no dividend to reinvest; lagerbeskatning taxes both alike).

The go-to is normally the ranking's first. Pick another only for a reason the rule can't see, then set `rank_override` and write the reason in one sentence. Such reasons:
- a better index for a Danish investor;
- a fund about to close;
- a share class that the user's broker doesn't offer;
- a broad world fund rather than a US-only one;
- the user rejected the first.

Prefer a **world** (MSCI World sector) fund as the go-to for a GICS sector, list the US and Europe variants as peers, and say what the difference in exposure is. For an EU supersector the go-to is a Europe fund.

## Steps

1. **Context** (one round of calls):
   - `investor_notes`: which accounts the user has (ASK, frie midler, pension) and their broker (Saxo, Nordnet …), which matters for which listings they can buy.
   - `sector_etfs_view()`: the current record, its age, `run_scope`, and per sector `replace`, `recheck`, `stale`, the rotation rows and every ETF's tax status.
   - `summary(sections=["rotation"])`: where each sector stands now (the memo leads with the sectors in Leading or Improving).
   - The last memo, via `documents(kind="sector_etfs")` and `read_document`, if there is one.

   Work out the scope (above); with `none`, reply and stop.
2. **Candidates per sector:** `sector_etf_candidates(sector)` for each sector in scope (send them together). You get the record's ETFs, the seeds of `config/sector_etfs.yaml` and matching ETFs of the discovery pool, each with returns in DKK, Yahoo's cached TER, its tax status and `rejected`. The pool is name-matched: drop a fund whose index isn't the sector (a biotech fund under Technology, a single-country fund).
3. **Research the facts, per candidate** (WebSearch, standard mode; send the searches together). Read the issuer's product page or factsheet first (iShares, Xtrackers/DWS, SPDR, Amundi, Invesco), then justETF for a cross-check and for tracking difference. For each fund record:
   - `ter` (a fraction: 0.25 % is 0.0025), `aum_musd` (fund size in USD millions; convert from EUR at today's rate and say so), `distribution` acc | dist, `domicile` (IE, LU, DE), `currency` (the share class's), `index`, `issuer`
   - `tracking_diff`: the fund's return minus its index's over the latest full year, as a fraction (−0.0012 for −0,12 %), only from a source that states it; otherwise null
   - `sources`: the URLs you read, and `checked`: today's date
   - new launches and closures or mergers in the sector

   **Never invent a figure.** An unknown is null, and the memo says it is unknown. Read free pages only; never try to get around a paywall or a login. Check that the ISIN is the share class you mean (accumulating and distributing classes have different ISINs) and that the ticker is a Yahoo listing of that share class (`ticker_profile` when in doubt). Prefer a Xetra or London listing the user's broker is likely to offer.
4. **Choose per sector:** keep the go-to and up to seven peers, at least one per scope (world, us, europe) where one exists. Never pick a `rejected` fund as the go-to. For a sector being replaced, the old go-to may stay as a peer.

   Then call `sector_etfs_save(sectors=[…], note=…)` **without** `save`. This dry run ranks each sector with today's data and returns:
   - `warnings`: the pick isn't first; the pick is off the positive list;
   - `changes` against the latest record: a new pick, ETFs added or dropped, a TER that moved.

   Fix what it refuses (a bad ISIN check digit, a TER that isn't a fraction, a rejected pick) and run it again. Handle each warning: pick the ranking's first, or set `rank_override` with the reason.
5. **Save** every sector in scope: `sector_etfs_save(sectors=[…], note=…, save=true)`. Don't ask the user first; they mark what they don't want on the page afterwards. If it refuses a ticker (no Yahoo prices), use another listing of the same share class or drop that fund, and save again. The result's `resolved` lists the marks this run dealt with.
6. **Write the memo** (below) with `write_memo(kind="sector_etfs", name="YYYY-MM-DD")`. If one exists for today, read it and write `YYYY-MM-DD-2`. Pass its name as `report` if you save again.
7. **Reply in Danish:** 3–8 lines.
   - The sectors updated. On a first run or `reselect-all`: the go-to per sector, one short line each (ticker, TER, ASK ja/nej). On a replacement run: the old → new go-to per sector, and how the new one answers the user's reason.
   - Any fund that is leaving the positive list next year (`tax.next_year` = `no`).
   - A link to the memo.
   - That the *Sector ETFs* page shows them, and that a go-to they don't want can be marked there with *Mark for replacement*; the next `/sector-etfs` replaces only those.
   - If the user wants to act on one, point to `/research <ticker>`, `/compare` and their trading rules (`/rules check`). Never suggest a trade size.

## Memo structure

```markdown
---
date: YYYY-MM-DD
mode: first                        # first | replace | reselect-all | named
sectors: [Technology, Banks]       # the sectors this run covered
record: YYYY-MM-DD                 # the id sector_etfs_save returned, or null if not saved
---
# Sektor-ETF'er – YYYY-MM-DD
*Analyse, ikke rådgivning. Go-to-fonden er den, der passer bedst til reglen nedenfor for en dansk investor, ikke en anbefaling om at købe.*

## Kort fortalt
3–5 bullets: what changed since last time, which sectors lead in the rotation and their go-to, anything to watch (a fund leaving positivlisten, a closure).

## Udskiftet
Only on a replacement run: per sector the old go-to, your reason for marking it, the new go-to and how it answers the reason.

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
