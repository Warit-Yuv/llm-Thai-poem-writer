$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "ไม่พบ .venv กรุณาสร้าง virtual environment และติดตั้ง ui\requirements.txt ก่อน"
    exit 1
}

Set-Location -LiteralPath $projectRoot
& $python -m streamlit run "ui\app.py"
