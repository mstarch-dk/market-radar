@echo off
setlocal
title Market Radar
cd /d "%~dp0"
echo.
echo  Market Radar is starting...
echo.

rem uv runs Market Radar's Python. It installs into your user folder; no admin rights needed.
where uv >nul 2>nul
if not errorlevel 1 goto have_uv
if exist "%USERPROFILE%\.local\bin\uv.exe" goto add_path
echo  First start: installing uv, the small tool that runs Market Radar, from astral.sh ...
powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
:add_path
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 goto no_uv

:have_uv
echo  Preparing Python and packages. The first time this takes a minute or two...
uv sync --locked --no-dev
if errorlevel 1 goto failed

echo.
echo  Market Radar runs at http://127.0.0.1:8780 and your browser opens in a moment.
echo  Keep this window open while you use it. Close it to stop Market Radar.
echo.
uv run --no-sync radar serve --open
if errorlevel 1 goto failed
goto end

:no_uv
echo.
echo  Could not install uv. Check the internet connection, then try again.
echo  See README.md, section Troubleshooting.
pause
exit /b 1

:failed
echo.
echo  Something went wrong. Checking what is missing:
echo.
uv run --no-sync radar doctor
echo.
echo  If you can't fix it, send a screenshot of this window to whoever gave you Market Radar.
pause
exit /b 1

:end
endlocal
