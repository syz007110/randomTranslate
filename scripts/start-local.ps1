# 切换到仓库根目录（scripts 的上一级）
Set-Location (Join-Path $PSScriptRoot "..")

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

Write-Host "Start Redis / Worker / Web"
Write-Host "Tip: Windows建议直接用 Docker Compose 方式启动完整服务"
file-translator-web
