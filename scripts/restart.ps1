<#
Restart Market Radar from source after a `git pull`, in one step (Windows, for developers).

    .\scripts\restart.ps1              # sync Python packages, rebuild the web app, restart `radar serve`
    .\scripts\restart.ps1 -Pull        # git pull --ff-only first
    .\scripts\restart.ps1 -Report      # also rebuild reports/dashboard.json from the cached data (`radar report`)
    .\scripts\restart.ps1 -Open        # open the browser when the server is up
    .\scripts\restart.ps1 -Port 8781   # another port

It does every step whether or not the pull needed it. The web app is built before the running server is stopped,
so a failed build leaves the old one running; the Python packages are synced after it stops (Windows locks files
in use). The old server is stopped wherever it runs; a window opened by `Start Market Radar.cmd` is closed with it.
The new server runs in this window: Ctrl+C stops it.
#>
param(
    [switch]$Pull,
    [switch]$Report,
    [switch]$Open,
    [int]$Port = 8780
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Invoke-Step([string]$Title, [scriptblock]$Command) {
    Write-Host "`n== $Title" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n$Title failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        exit 1
    }
}

# The process tree behind the server listening on $Port: uv.exe -> radar.exe / python.exe launchers -> python.exe.
# Returns the top-most of those (killing it with /T takes the rest), or $null if nothing listens.
function Get-ServerRoot([int]$Port) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) { return $null }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($proc.Name -notin 'python.exe', 'pythonw.exe') {
        Write-Host "Port $Port is used by $($proc.Name) (PID $($proc.ProcessId)), not Market Radar. Stop it, or use -Port." -ForegroundColor Red
        exit 1
    }
    while ($true) {
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)"
        if (-not $parent -or $parent.Name -notin 'python.exe', 'pythonw.exe', 'radar.exe', 'uv.exe') { return $proc }
        $proc = $parent
    }
}

if ($Pull) { Invoke-Step 'git pull' { git pull --ff-only } }
Invoke-Step 'Web packages (pnpm install)' { pnpm -C web install --frozen-lockfile }
Invoke-Step 'Web app (pnpm build)' { pnpm -C web build }

$root = Get-ServerRoot $Port
if ($root) {
    Write-Host "`n== Stopping the running server (PID $($root.ProcessId))" -ForegroundColor Cyan
    # The start script's window would report the stop as a failure and wait for Enter: close it as well.
    $window = Get-CimInstance Win32_Process -Filter "ProcessId=$($root.ParentProcessId)"
    $target = if ($window -and $window.Name -eq 'cmd.exe' -and $window.CommandLine -like '*Start Market Radar.cmd*') { $window } else { $root }
    taskkill /PID $target.ProcessId /T /F | Out-Null
    $deadline = (Get-Date).AddSeconds(15)
    while (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) {
            Write-Host "Port $Port is still in use after 15 s." -ForegroundColor Red
            exit 1
        }
        Start-Sleep -Milliseconds 250
    }
}

Invoke-Step 'Python packages (uv sync)' { uv sync --inexact }
if ($Report) { Invoke-Step 'Dashboard (radar report)' { uv run --no-sync radar report } }

Write-Host "`n== Market Radar runs at http://127.0.0.1:$Port/ (reload the browser tab). Ctrl+C stops it." -ForegroundColor Green
$serveArgs = @('run', '--no-sync', 'radar', 'serve', '--port', $Port)
if ($Open) { $serveArgs += '--open' }
& uv @serveArgs
exit $LASTEXITCODE
