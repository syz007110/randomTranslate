from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from redis import Redis
from rq import Queue
from starlette.requests import Request

from .core import DB_PATH, translate_file
from .db import connect, init_schema
from .tasks import process_translation_task

app = FastAPI(title="File Translator UI", version="0.2.0")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


def _get_queue() -> Queue:
    redis_conn = Redis.from_url(REDIS_URL)
    return Queue("file-translator", connection=redis_conn)


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
    engine: str = Form("mock"),
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
    engine: str = Form("mock"),
    domain: str = Form(""),
    max_workers: int = Form(4),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".docx", ".md", ".json", ".txt"}:
        raise HTTPException(status_code=400, detail="Only docx/md/json/txt are supported")

    q = _get_queue()
    job = q.enqueue(
        process_translation_task,
        await file.read(),
        file.filename,
        src_lang,
        tgt_lang,
        engine,
        domain or None,
        max_workers,
        job_timeout="30m",
        result_ttl=24 * 3600,
    )
    return {"task_id": job.id, "status": "queued"}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    q = _get_queue()
    job = q.fetch_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="task not found")

    if job.is_finished:
        return {"task_id": task_id, "status": "finished", "result": job.result}
    if job.is_failed:
        return {"task_id": task_id, "status": "failed", "error": job.exc_info}
    return {"task_id": task_id, "status": job.get_status()}


@app.get("/api/tasks/{task_id}/download")
def download_task_result(task_id: str):
    q = _get_queue()
    job = q.fetch_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="task not found")
    if not job.is_finished:
        raise HTTPException(status_code=409, detail="task not finished")
    result = job.result or {}
    output_path = result.get("output_path")
    download_name = result.get("download_name", "translated_output")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="output not found")
    return FileResponse(path=output_path, filename=download_name, media_type="application/octet-stream")


def run() -> None:
    import uvicorn

    uvicorn.run("file_translator.app:app", host="0.0.0.0", port=8088, reload=False)
