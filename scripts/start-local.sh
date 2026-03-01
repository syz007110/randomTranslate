#!/usr/bin/env bash
set -e

# 切换到仓库根目录（scripts 的上一级）
cd "$(dirname "$0")/.."

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

echo "[1/2] start worker"
nohup file-translator-worker > /tmp/file-translator-worker.log 2>&1 &

echo "[2/2] start web"
file-translator-web
