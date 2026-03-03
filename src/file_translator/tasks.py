from __future__ import annotations

from pathlib import Path

from .core import translate_file

TASK_DIR = Path.home() / ".file_translator" / "tasks"


def process_translation_task(
    file_bytes: bytes,
    filename: str,
    src_lang: str,
    tgt_lang: str,
    engine: str,
    domain: str | None,
    max_workers: int = 4,
):
    from rq import get_current_job

    job = get_current_job()
    job_id = job.id if job else "sync"

    work_dir = TASK_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    in_path = work_dir / filename
    out_path = work_dir / f"translated_{filename}"
    in_path.write_bytes(file_bytes)

    translate_file(
        in_path=in_path,
        out_path=out_path,
        src=src_lang,
        tgt=tgt_lang,
        engine=engine,
        domain=domain,
        max_workers=max_workers,
    )

    return {
        "output_path": str(out_path),
        "download_name": out_path.name,
        "engine": engine,
        "src_lang": src_lang,
        "tgt_lang": tgt_lang,
    }
