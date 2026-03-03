from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis

from .core import translate_file

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
QUEUE_KEY = "ft:jobs"
TASK_PREFIX = "ft:task:"


def _task_key(task_id: str) -> str:
    return f"{TASK_PREFIX}{task_id}"


def run() -> None:
    r = Redis.from_url(REDIS_URL, decode_responses=True)
    print("[worker] started, waiting for jobs...")

    while True:
        item = r.brpop(QUEUE_KEY, timeout=0)
        if not item:
            continue
        _, task_id = item
        key = _task_key(task_id)
        data = r.hgetall(key)
        if not data:
            continue

        try:
            r.hset(key, mapping={"status": "processing", "error": ""})

            in_path = Path(data["input_path"])
            filename = data["filename"]
            out_path = in_path.parent / f"translated_{filename}"

            translate_file(
                in_path=in_path,
                out_path=out_path,
                src=data.get("src_lang", "auto"),
                tgt=data.get("tgt_lang", "en"),
                engine=data.get("engine", "xfyun"),
                domain=(data.get("domain") or None),
                max_workers=max(1, int(data.get("max_workers", "4"))),
            )

            r.hset(
                key,
                mapping={
                    "status": "finished",
                    "output_path": str(out_path),
                    "download_name": out_path.name,
                },
            )
        except Exception as e:
            r.hset(key, mapping={"status": "failed", "error": str(e)})


if __name__ == "__main__":
    run()
