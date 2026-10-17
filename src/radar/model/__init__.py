"""The shared kernel: what the live app and the studies must compute the same way, defined once.

- `score`: the momentum score's percentile rule (the share of names strictly below) and its components.
- `panels`: point-in-time panels of the stock universe and the month-end / fill calendar.
- `select`: picking the best names under sector and group caps.
- `paths`: the trend exit (a close below the n-day average, sold at the next close) and basket paths with it.

The studies (backtest/) validate exactly what the app shows and the proposals act on, because both call these.
Nothing here imports the report builder, the API or the CLI."""
