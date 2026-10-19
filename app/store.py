"""Persistencia de estados de job y cola Redis Streams; operaciones atómicas."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import WatchError

from app.config import settings


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class JobStore:
    def __init__(self, redis: Redis):
        self.redis = redis

    @staticmethod
    def key(job_id: str) -> str:
        return f"multiagent:job:{job_id}"

    async def create(self, task: str, max_steps: int, batch_id: str = "") -> dict[str, str]:
        job_id = str(uuid4())
        item = {
            "job_id": job_id,
            "task": task,
            "status": "PENDING",
            "max_steps": str(max_steps),
            "batch_id": batch_id,
            "created_at": now(),
            "updated_at": now(),
            "result": "",
            "error": "",
            "approval_request": "",
        }
        async with self.redis.pipeline(transaction=True) as tx:
            tx.hset(self.key(job_id), mapping=item)
            tx.xadd(settings.redis_stream, {"job_id": job_id, "kind": "start"})
            await tx.execute()
        return item

    async def get(self, job_id: str) -> dict[str, Any]:
        item = await self.redis.hgetall(self.key(job_id))
        if not item:
            raise NotFound(job_id)
        return {
            **{key: value for key, value in item.items() if key != "task"},
            "approval_request": json.loads(item.get("approval_request") or "null"),
            "result": item.get("result") or None,
            "error": item.get("error") or None,
            "max_steps": int(item.get("max_steps", 8)),
        }

    async def raw(self, job_id: str) -> dict[str, str]:
        item = await self.redis.hgetall(self.key(job_id))
        if not item:
            raise NotFound(job_id)
        return item

    async def update(self, job_id: str, *, status: str, **fields: str) -> None:
        await self.redis.hset(self.key(job_id), mapping={
            "status": status, "updated_at": now(), **fields,
        })

    async def queue_approval(
        self, job_id: str, approved: bool, reviewer: str, comment: str,
    ) -> None:
        """WATCH evita que dos revisores reanuden el mismo checkpoint dos veces."""
        key = self.key(job_id)
        async with self.redis.pipeline(transaction=True) as tx:
            try:
                await tx.watch(key)
                status = await tx.hget(key, "status")
                if status is None:
                    raise NotFound(job_id)
                if status != "WAITING_APPROVAL":
                    raise Conflict(f"Estado actual: {status}. Se esperaba WAITING_APPROVAL.")
                tx.multi()
                tx.hset(key, mapping={"status": "APPROVAL_QUEUED", "updated_at": now()})
                tx.xadd(settings.redis_stream, {
                    "job_id": job_id,
                    "kind": "resume",
                    "approved": "true" if approved else "false",
                    "reviewer": reviewer[:80],
                    "comment": comment[:300],
                })
                await tx.execute()
            except WatchError as exc:
                raise Conflict("Otro revisor ya respondió; volvé a consultar el job.") from exc
