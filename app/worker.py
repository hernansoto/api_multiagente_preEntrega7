"""Consumidor Redis Streams independiente de FastAPI; 5 jobs concurrentes."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.types import Command
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.config import settings
from app.graph import build_graph
from app.observability import run_traced_graph
from app.store import JobStore

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, redis: Redis, graph: Any, *, concurrency: int = 5):
        self.redis = redis
        self.graph = graph
        self.store = JobStore(redis)
        self.sem = asyncio.Semaphore(concurrency)
        self.concurrency = concurrency
        self.consumer = f"{socket.gethostname()}-{os.getpid()}"
        self.running: set[asyncio.Task] = set()

    async def prepare(self) -> None:
        try:
            await self.redis.xgroup_create(
                settings.redis_stream, settings.redis_group, id="0", mkstream=True
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def process(self, message_id: str, payload: dict[str, str]) -> None:
        job_id = payload["job_id"]
        kind = payload["kind"]
        async with self.sem:
            try:
                job = await self.store.raw(job_id)
                expected = "PENDING" if kind == "start" else "APPROVAL_QUEUED"
                if job["status"] != expected:
                    # Un RUNNING reclamado después de la caída no se reejecuta ciegamente
                    # para evitar duplicar efectos y cálculos: se reporta FAILED.
                    if job["status"] == "RUNNING":
                        await self.store.update(
                            job_id, status="FAILED",
                            error="Worker anterior interrumpido; requiere reenvío seguro de la tarea.",
                        )
                    if job["status"] not in ("DONE", "FAILED", "WAITING_APPROVAL"):
                        logger.warning("Evento %s inesperado en estado %s", job_id, job["status"])
                    await self.redis.xack(settings.redis_stream, settings.redis_group, message_id)
                    return

                await self.store.update(job_id, status="RUNNING", error="")
                config = {
                    "configurable": {"thread_id": job_id},
                    "run_name": "preentrega7_multiagent",
                    "tags": ["preentrega7", f"job:{job_id}", f"batch:{job['batch_id'] or 'manual'}"],
                    "metadata": {"job_id": job_id, "batch_id": job["batch_id"], "kind": kind},
                    "recursion_limit": 48,
                }
                if kind == "start":
                    graph_input: Any = {
                        "user_request": job["task"],
                        "messages": [HumanMessage(content=job["task"])],
                        "max_steps": int(job["max_steps"]),
                        "step_count": 0,
                        "task_completed": False,
                    }
                else:
                    graph_input = Command(resume={
                        "approved": payload.get("approved") == "true",
                        "reviewer": payload.get("reviewer", ""),
                        "comment": payload.get("comment", ""),
                    })

                result = await run_traced_graph(
                    graph=self.graph, payload=graph_input, config=config,
                    job_id=job_id, kind=kind,
                )
                interrupts = result.get("__interrupt__", ())
                if interrupts:
                    approval_payload = interrupts[0].value
                    await self.store.update(
                        job_id, status="WAITING_APPROVAL",
                        approval_request=json.dumps(approval_payload, ensure_ascii=False),
                    )
                else:
                    technical_errors = [
                        result.get("synthesis_error", ""),
                        result.get("stop_reason", "") if "No fue posible decidir" in result.get("stop_reason", "") else "",
                        result.get("research_error", "") if not result.get("research_sources") else "",
                        result.get("analysis_error", "") if not result.get("analysis_calculations") else "",
                    ]
                    if any(technical_errors):
                        raise RuntimeError("Errores técnicos de agentes: " + "; ".join(filter(None, technical_errors)))
                    answer = result.get("final_answer")
                    if not answer:
                        raise RuntimeError("El grafo terminó sin síntesis ni interrupción.")
                    await self.store.update(
                        job_id, status="DONE", result=str(answer),
                        approval_request="",
                    )
            except Exception as exc:
                logger.exception("Fallo del job %s (%s)", job_id, kind)
                try:
                    await self.store.update(
                        job_id, status="FAILED", error=f"{type(exc).__name__}: {exc}"[:900]
                    )
                except Exception:
                    logger.exception("No se pudo persistir FAILED para %s", job_id)
                    # No confirmar mensaje: Redis Streams conserva el pendiente para recuperar.
                    return
            await self.redis.xack(settings.redis_stream, settings.redis_group, message_id)

    async def submit(self, message_id: str, payload: dict[str, str]) -> None:
        while len(self.running) >= self.concurrency:
            await asyncio.wait(self.running, return_when=asyncio.FIRST_COMPLETED)
        task = asyncio.create_task(self.process(message_id, payload))
        self.running.add(task)
        task.add_done_callback(self.running.discard)

    async def recover_stale(self) -> None:
        """Recupera pendientes de workers caídos (15 min, evitar duplicar jobs lentos)."""
        cursor = "0-0"
        while True:
            response = await self.redis.xautoclaim(
                settings.redis_stream, settings.redis_group, self.consumer,
                min_idle_time=900_000, start_id=cursor, count=20,
            )
            cursor, pending = response[0], response[1]
            for message_id, payload in pending:
                await self.submit(message_id, payload)
            if cursor == "0-0" or not pending:
                break

    async def run_forever(self) -> None:
        await self.prepare()
        await self.recover_stale()
        cycles = 0
        while True:
            if cycles % 30 == 0 and cycles:
                await self.recover_stale()
            cycles += 1
            records = await self.redis.xreadgroup(
                groupname=settings.redis_group,
                consumername=self.consumer,
                streams={settings.redis_stream: ">"},
                count=10, block=2000,
            )
            for _, messages in records:
                for message_id, payload in messages:
                    await self.submit(message_id, payload)


async def main() -> None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY debe estar configurada en el worker")
    if settings.worker_concurrency < 1:
        raise ValueError("WORKER_CONCURRENCY debe ser >=1")
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        # from_conn_string mantiene vivo el checkpointer durante todas las ejecuciones.
        async with AsyncRedisSaver.from_conn_string(settings.redis_url) as checkpointer:
            model = ChatOpenAI(model=settings.openai_model, temperature=0)
            graph = build_graph(model, checkpointer)
            worker = Worker(redis, graph, concurrency=settings.worker_concurrency)
            try:
                await worker.run_forever()
            finally:
                if worker.running:
                    await asyncio.gather(*worker.running, return_exceptions=True)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
