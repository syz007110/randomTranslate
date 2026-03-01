@echo off
setlocal

REM 切换到仓库根目录（scripts 的上一级）
cd /d %~dp0\..

python -m venv .venv
call .venv\Scripts\activate.bat
pip install -e .

echo Starting web UI...
file-translator-web
