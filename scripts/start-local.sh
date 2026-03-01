#!/usr/bin/env bash
set -e

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

echo "[1/3] start redis"
redis-server --daemonize yes || true

echo "[2/3] start worker"
nohup file-translator-worker > /tmp/file-translator-worker.log 2>&1 &

echo "[3/3] start web"
file-translator-web
