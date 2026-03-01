from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from redis import Redis
from starlette.requests import Request

from .core import DB_PATH, translate_file
from .db import connect, init_schema

app = FastAPI(title="File Translator UI", version="0.3.0")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
QUEUE_KEY = "ft:jobs"
TASK_PREFIX = "ft:task:"
TASK_DIR = Path.home() / ".file_translator" / "tasks"


def _redis() -> Redis:
    return Redis.from_url(REDIS_URL, decode_responses=True)


def _task_key(task_id: str) -> str:
    return f"{TASK_PREFIX}{task_id}"


@app.on_event("startup")
def _startup() -> None:
    conn = connect(DB_PATH)
    init_schema(conn)
    conn.close()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.post("/translate")
async def translate_sync(
    file: UploadFile = File(...),
    src_lang: str = Form(...),
    tgt_lang: str = Form(...),
    engine: str = Form("xfyun"),
    domain: str = Form(""),
    max_workers: int = Form(4),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".docx", ".md", ".json", ".txt"}:
        raise HTTPException(status_code=400, detail="Only docx/md/json/txt are supported")

    work_dir = Path.home() / ".file_translator" / "sync"
    work_dir.mkdir(parents=True, exist_ok=True)
    in_path = work_dir / file.filename
    out_path = work_dir / f"translated_{file.filename}"
    in_path.write_bytes(await file.read())

    translate_file(in_path, out_path, src_lang, tgt_lang, engine, domain or None, max_workers=max_workers)
    return FileResponse(path=out_path, filename=out_path.name, media_type="application/octet-stream")


@app.post("/api/tasks")
async def create_task(
    file: UploadFile = File(...),
    src_lang: str = Form(...),
    tgt_lang: str = Form(...),
    engine: str = Form("xfyun"),
    domain: str = Form(""),
    max_workers: int = Form(4),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".docx", ".md", ".json", ".txt"}:
        raise HTTPException(status_code=400, detail="Only docx/md/json/txt are supported")

    task_id = uuid.uuid4().hex
    work_dir = TASK_DIR / task_id
    work_dir.mkdir(parents=True, exist_ok=True)
    in_path = work_dir / file.filename
    in_path.write_bytes(await file.read())

    task_data = {
        "task_id": task_id,
        "status": "queued",
        "filename": file.filename,
        "input_path": str(in_path),
        "src_lang": src_lang,
        "tgt_lang": tgt_lang,
        "engine": engine,
        "domain": domain or "",
        "max_workers": str(max_workers),
        "error": "",
        "output_path": "",
        "download_name": "",
    }

    r = _redis()
    r.hset(_task_key(task_id), mapping=task_data)
    r.lpush(QUEUE_KEY, task_id)

    return {"task_id": task_id, "status": "queued"}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    r = _redis()
    data = r.hgetall(_task_key(task_id))
    if not data:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "task_id": task_id,
        "status": data.get("status", "unknown"),
        "error": data.get("error", ""),
        "result": {
            "output_path": data.get("output_path", ""),
            "download_name": data.get("download_name", ""),
        },
    }


@app.get("/api/tasks/{task_id}/download")
def download_task_result(task_id: str):
    r = _redis()
    data = r.hgetall(_task_key(task_id))
    if not data:
        raise HTTPException(status_code=404, detail="task not found")
    if data.get("status") != "finished":
        raise HTTPException(status_code=409, detail="task not finished")

    output_path = data.get("output_path")
    download_name = data.get("download_name", "translated_output")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="output not found")
    return FileResponse(path=output_path, filename=download_name, media_type="application/octet-stream")


def run() -> None:
    import uvicorn

    uvicorn.run("file_translator.app:app", host="0.0.0.0", port=8088, reload=False)
