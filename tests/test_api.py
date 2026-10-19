import fakeredis.aioredis
import httpx
import pytest

from app.main import app
from app.store import JobStore


@pytest.mark.asyncio
async def test_api_returns_202_and_does_not_invoke_graph():
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.store = JobStore(fake)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"task": "Compará Starter y Growth con cálculos reales"})
        assert response.status_code == 202
        jid = response.json()["job_id"]
        status = await client.get(f"/tasks/{jid}")
        assert status.status_code == 200
        assert status.json()["status"] == "PENDING"
    await fake.aclose()
