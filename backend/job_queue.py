"""In-process async job queue for inference pipeline.
Production would swap this for BullMQ/Redis, but the API contract is the same.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

log = logging.getLogger("cropvision.queue")


class JobQueue:
    def __init__(self, worker: Callable[[str], Awaitable[None]], concurrency: int = 2):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker = worker
        self.concurrency = concurrency
        self._tasks: list[asyncio.Task] = []
        self.processed = 0
        self.failed = 0

    async def enqueue(self, job_id: str) -> None:
        await self.queue.put(job_id)

    async def _run(self, idx: int) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                await self.worker(job_id)
                self.processed += 1
            except Exception:
                self.failed += 1
                log.exception("Worker %d failed job %s", idx, job_id)
            finally:
                self.queue.task_done()

    def start(self) -> None:
        for i in range(self.concurrency):
            self._tasks.append(asyncio.create_task(self._run(i)))
        log.info("JobQueue started with %d workers", self.concurrency)

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass

    def stats(self) -> dict:
        return {
            "pending": self.queue.qsize(),
            "processed": self.processed,
            "failed": self.failed,
            "workers": self.concurrency,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
