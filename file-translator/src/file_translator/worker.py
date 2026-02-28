from __future__ import annotations

import os

from redis import Redis
from rq import Connection, Worker


def run() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_conn = Redis.from_url(redis_url)
    with Connection(redis_conn):
        worker = Worker(["file-translator"])
        worker.work()


if __name__ == "__main__":
    run()
