$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root "myaibot\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found at $Python"
}

Set-Location $Root
& $Python "server.py" "--host" "127.0.0.1" "--port" "8000"
