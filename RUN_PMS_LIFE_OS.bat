@echo off
setlocal

set "PYTHON=C:\Users\ADMIN\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "APP=%~dp0pms_life_os_web.py"

if not exist "%PYTHON%" (
  echo Python runtime was not found at:
  echo %PYTHON%
  echo.
  echo Install Python, then run:
  echo python "%APP%"
  pause
  exit /b 1
)

echo Starting PMS Life OS...
echo.
echo Keep this window open.
echo Open this link on this PC:
echo http://127.0.0.1:8501
echo.
echo Mobile links on the same Wi-Fi:
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } | ForEach-Object { 'http://' + $_.IPAddress + ':8501' }"
echo.
"%PYTHON%" "%APP%"

pause
