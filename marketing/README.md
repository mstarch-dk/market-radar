# Marketing material

A Danish brochure for Market Radar: [market-radar.pdf](market-radar.pdf) (A4, the committed edition), built from
[site/index.html](site/index.html) (the page, light and dark, works on a phone). The screenshots in
`site/img/` are local build output: `shots` makes them, and they are not committed. The audience is
experienced Danish hobby investors; the text describes what each feature does, how it is calculated and
where it stops.

**All screenshots use a fictional investor** ([demo/seed.yaml](demo/seed.yaml)) on real market data, in a
demo copy of the app (`.demo/`, gitignored, in portable mode with its own data folder) that never sees the user's data folder.

## Updating
Run `/marketing` in Claude Code. It finds the features added since the last edition
([edition.json](edition.json)), explores them in the demo, adds shots and text, rebuilds and checks.

By hand (`uv run --group marketing python scripts/marketing.py …`; it drives the installed Microsoft Edge):

| Command | Does |
|---|---|
| `workspace` | rebuild `.demo/`: the working tree without personal files, the market data, `uv sync`, web build |
| `uv run --directory .demo radar serve --port 8790` | the demo app (`radar-demo` in `.claude/launch.json`) |
| `seed` | fill the demo database from `demo/seed.yaml` through the app's API, then `radar run` in `.demo/` |
| `explore /path …` | full-page captures in `.demo/explore/`, for choosing frames |
| `shots [ID…]` | [shots.yaml](shots.yaml) → `site/img/` (gitignored) |
| `pdf` | `site/index.html` → `market-radar.pdf` |
| `check` | leak check, demo database, images, [features.yaml](features.yaml) ↔ page ↔ shots, phone width |
| `edition --data-asof D` | write `edition.json` |
| `all` | workspace, server, seed, shots, pdf, check |
