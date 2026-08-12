$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "Missing .venv. Create the virtual environment and install ui\requirements.txt first."
    exit 1
}

Set-Location -LiteralPath $projectRoot
& $python -m streamlit run "ui\app.py"
