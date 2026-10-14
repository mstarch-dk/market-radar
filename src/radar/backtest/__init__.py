"""Point-in-time backtests on your own trades.

- `pit.Context`: what the radar would have known on a past day D (prices up to D, the momentum percentile against
  the stock universe that day, the regime as of the last week's close with publication lags on macro data,
  analyst consensus fetched by D). Nothing after D is read.
- `exits`: replays your real portfolios with the stop-loss / take-profit rule of signals/levels.py applied day by
  day, into simulated (virtual) portfolios, with a per-exit report of what the rule saved or cost.

Conventions and limitations: docs/data-conventions.md, "Point-in-time backtests".
"""
