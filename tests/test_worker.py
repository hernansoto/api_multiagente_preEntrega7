import fakeredis.aioredis
import pytest

from app.store import JobStore
from app.worker import Worker


class BrokenGraph:
    async def ainvoke(self, *args, **kwargs):
        raise RuntimeError("Falló el proveedor de LLM")


@pytest.mark.asyncio
async def test_worker_marks_failed_and_acks(monkeypatch):
    # La función de tracing real anida la invocación de LangGraph. El mock emula
    # el error del proveedor para comprobar transición a FAILED.
    from app import worker as worker_module

    async def invoke(**kwargs):
        return await kwargs["graph"].ainvoke(kwargs["payload"], config=kwargs["config"])

    monkeypatch.setattr(worker_module, "run_traced_graph", invoke)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    repo = JobStore(redis)
    job = await repo.create("Probemos la recuperación de un error", 8)
    await redis.xgroup_create("multiagent:jobs", "multiagent-workers", "0")
    item = await redis.xreadgroup("multiagent-workers", "worker-test", {"multiagent:jobs": ">"})
    msg_id, message = item[0][1][0]
    await Worker(redis, BrokenGraph()).process(msg_id, message)
    assert (await repo.get(job["job_id"]))["status"] == "FAILED"
    assert (await redis.xpending("multiagent:jobs", "multiagent-workers"))["pending"] == 0
    await redis.aclose()
