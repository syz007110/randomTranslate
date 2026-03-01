@echo off
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -e .

echo Starting web UI...
file-translator-web
