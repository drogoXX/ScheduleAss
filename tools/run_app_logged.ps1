# Launch the app and capture everything its own logger cannot.
#
# The application log records what happens INSIDE the Python process. When the
# process dies, the log simply stops - no traceback, no shutdown line. This
# wrapper captures the console output, the exit code, and a memory sample every
# few seconds, so a death can be told apart from a hang, and an out-of-memory
# kill from a clean exit.
#
# Usage:   powershell -ExecutionPolicy Bypass -File tools\run_app_logged.ps1
# Stop:    Ctrl+C in this window (that is a clean exit and will be recorded)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$stamp   = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir  = Join-Path $env:LOCALAPPDATA "ScheduleAss\launch-logs"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$console = Join-Path $outDir "console-$stamp.log"
$samples = Join-Path $outDir "memory-$stamp.log"

Write-Host "Console output -> $console"
Write-Host "Memory samples -> $samples"
Write-Host "Starting Streamlit. Reproduce the problem, then send both files."
Write-Host ""

# Unbuffered so the console log is complete even if the process dies abruptly.
$env:PYTHONUNBUFFERED = "1"
# Surface client-side errors in the browser during diagnosis.
$args = @(
    "run", "app.py",
    "--client.showErrorDetails=full",
    "--client.toolbarMode=auto",
    "--server.port=8501"
)

$proc = Start-Process -FilePath "streamlit" -ArgumentList $args `
    -RedirectStandardOutput $console -RedirectStandardError "$console.err" `
    -NoNewWindow -PassThru

"pid=$($proc.Id) started=$(Get-Date -Format o)" | Out-File $samples -Encoding utf8

while (-not $proc.HasExited) {
    Start-Sleep -Seconds 3
    try {
        $p = Get-Process -Id $proc.Id -ErrorAction Stop
        $line = "{0} rss_mb={1} handles={2} threads={3}" -f `
            (Get-Date -Format "HH:mm:ss"),
            [math]::Round($p.WorkingSet64 / 1MB, 1),
            $p.HandleCount, $p.Threads.Count
        Add-Content -Path $samples -Value $line -Encoding utf8
    } catch { break }
}

$proc.WaitForExit()
$msg = "EXITED at $(Get-Date -Format o) with code $($proc.ExitCode)"
Add-Content -Path $samples -Value $msg -Encoding utf8
Write-Host ""
Write-Host $msg -ForegroundColor Yellow
Write-Host "Exit code meanings: 0 = clean stop, 1 = Python error (see console log),"
Write-Host "-1073741819 = access violation (native crash), 137/-1 = killed externally."
Write-Host "Send: $console and $samples"
