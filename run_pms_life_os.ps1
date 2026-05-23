$ErrorActionPreference = "Stop"

$Python = "C:\Users\ADMIN\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$App = Join-Path $PSScriptRoot "pms_life_os_web.py"

if (-not (Test-Path $Python)) {
    Write-Host "Python runtime was not found at: $Python"
    Write-Host "Install Python, then run: python pms_life_os_web.py"
    exit 1
}

Write-Host "Starting PMS Life OS..."
Write-Host "Open this link on this PC:"
Write-Host "http://127.0.0.1:8501"
Write-Host ""
Write-Host "Mobile links on the same Wi-Fi:"
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    ForEach-Object { Write-Host ("http://" + $_.IPAddress + ":8501") }
Write-Host ""
& $Python $App
