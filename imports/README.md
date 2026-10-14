Drop local inputs here (gitignored):

- Your trades now live in `userdata/radar.db` (the Portfolio page in the app). Old `holdings.csv` / `transactions.csv`
  files found here are moved into it once, automatically, and renamed `*.migrated.csv`.
- `yahoo_portfolio.csv` – a Yahoo Finance portfolio export, if you prefer the command line: `radar import-yahoo imports/yahoo_portfolio.csv`
  (the app's *Import…* does the same, plus broker exports).
- `positivliste.xlsx` – SKAT's list of aktiebaserede investeringsselskaber (search skat.dk for "positivliste investeringsselskaber"). Used to flag ETFs by ISIN.
