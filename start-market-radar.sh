#!/bin/bash
# Market Radar for Linux: run ./start-market-radar.sh from this folder (or double-click it if your file manager
# runs scripts). Same steps as the Windows and Mac start scripts.
cd "$(dirname "$0")" || exit 1
echo
echo " Market Radar is starting..."
echo

fail() {
  echo
  echo " Something went wrong. Checking what is missing:"
  echo
  uv run --no-sync radar doctor
  echo
  echo " If you can't fix it, send a copy of this output to whoever gave you Market Radar."
  exit 1
}

# uv runs Market Radar's Python. It installs into your home folder; no root needed.
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo " First start: installing uv, the small tool that runs Market Radar, from astral.sh ..."
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
    echo " Could not install uv. Check the internet connection, then try again (README.md, Troubleshooting)."
    exit 1
  fi
  export PATH="$HOME/.local/bin:$PATH"
fi

echo " Preparing Python and packages. The first time this takes a minute or two..."
uv sync --locked --no-dev || fail

echo
echo " Market Radar runs at http://127.0.0.1:8780 and your browser opens in a moment."
echo " Keep this terminal open while you use it. Press Ctrl+C to stop Market Radar."
echo
uv run --no-sync radar serve --open || fail
