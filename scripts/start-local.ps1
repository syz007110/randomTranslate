# 切换到仓库根目录（scripts 的上一级）
Set-Location (Join-Path $PSScriptRoot "..")

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

Start-Process powershell -ArgumentList '-NoExit','-Command','.\.venv\Scripts\Activate.ps1; file-translator-worker'
file-translator-web
