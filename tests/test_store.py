import asyncio

import fakeredis.aioredis
import pytest

from app.store import Conflict, JobStore


@pytest.mark.asyncio
async def test_enqueue_status_and_single_human_approval():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    repo = JobStore(redis)
    job = await repo.create("Compará los dos planes comerciales", 8, "batch-1")
    job_id = job["job_id"]
    assert (await repo.get(job_id))["status"] == "PENDING"
    assert (await redis.xlen("multiagent:jobs")) == 1
    await repo.update(job_id, status="WAITING_APPROVAL")
    await repo.queue_approval(job_id, True, "docente", "Aprobado")
    assert (await repo.get(job_id))["status"] == "APPROVAL_QUEUED"
    assert (await redis.xlen("multiagent:jobs")) == 2
    with pytest.raises(Conflict):
        await repo.queue_approval(job_id, True, "otro", "Duplicada")
    await redis.aclose()
