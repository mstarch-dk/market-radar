# Changelog

What changed in each release, newest first. The user-facing version, in Danish, is the guide chapter *Nyheder*
(`guide/brugervejledning/nyheder.md`). `scripts/release.py prepare X.Y.Z` refuses to bump the version until both
have a `## X.Y.Z` section; the release workflow uses this file's section as the release notes.

## 0.2.0

Your data now lives apart from the program, so a new version never touches it.

- **A data folder of its own**: `~/Market Radar` by default (Windows, macOS, Linux) holds `radar.db`, your
  notes, briefs, research, journal, exports, broker files and the history the radar builds up. Downloaded market
  data and the dashboard go to the OS cache folder and can be deleted at any time. `radar paths` lists every
  location; the Data page shows them under *Your data*.
- **First start: moving your data.** The app finds an earlier version's data in its own folder or in a folder
  next to it and copies it into the data folder (checked file by file and row by row; the old folder only gets a
  `MOVED.txt`). Or `uv run radar setup`. Every later version finds the data folder by itself.
- **Backups**: automatic once a day and before a new version first uses your data, on demand, with restore
  (what is there is backed up first) and an optional second folder (cloud sync or USB). `radar backup`,
  `radar backups`, `radar restore`.
- **Export** in open formats (CSV, JSON, Markdown, with a description of every file) and loading one back on
  another computer: the Data page, `radar export`, `radar import-export`.
- **Safer updates**: data written by a newer version opens read-only in an older one; `radar --version`; an
  opt-in daily check for a new release (`radar updates --on`, needs `updates.repo` in settings.yaml).
- **Portfolio page reorganised**: only your accounts (real portfolios), with an account strip and tabs
  (*Positions*, *Transactions*, *Imports*, *Accounts*; `?tab=`); the trade form opens above the transactions table.
- **Experiments page** (`/experiments`) for virtual portfolios: the A/B test card, a list with returns vs ACWI, and
  one experiment's holdings, trades, rebalances and returns. `GET /api/portfolios/{id}/runs` lists a sim's runs.
- **Fee schedules** per account (`portfolios.fee_schedule`, `fees.py`, presets for Saxo and Danske Bank in
  `config/fee_presets.yaml`): the trade form prefills the fee with an estimate (`fee_estimate` from validate).
- Ticker lookup in the trade form: keyboard navigation, the tracked badge and the chosen name under the field.
- Linux start script `start-market-radar.sh`.

What you need to do: start 0.2.0 and choose where your data goes (the app suggests the folder and finds the
old data). Afterwards you can delete the old program folder.

## 0.1.0

The first release.
