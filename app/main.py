"""API REST asíncrona: nunca ejecuta LLMs dentro de los handlers."""
from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.config import settings
from app.store import Conflict, JobStore, NotFound


class TaskRequest(BaseModel):
    task: str = Field(min_length=10, max_length=6000)
    max_steps: int = Field(default=8, ge=3, le=12)
    batch_id: str = Field(default="", max_length=60)


class ApprovalRequest(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=2, max_length=80)
    comment: str = Field(default="", max_length=300)


def valid_id(job_id: str) -> str:
    try:
        return str(UUID(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="ID de tarea inválido") from exc


def check_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.api_key and not secrets.compare_digest(x_api_key or "", settings.api_key):
        raise HTTPException(status_code=401, detail="X-API-Key no válido")


def check_reviewer_key(x_approval_key: str | None = Header(default=None)) -> None:
    if not settings.approval_api_key:
        raise HTTPException(status_code=503, detail="APPROVAL_API_KEY no configurada")
    if not secrets.compare_digest(x_approval_key or "", settings.approval_api_key):
        raise HTTPException(status_code=403, detail="X-Approval-Key inválida")


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await redis.ping()
    app.state.store = JobStore(redis)
    try:
        yield
    finally:
        await redis.aclose()


app = FastAPI(
    title="Pre-entrega 7 · API de Orquestador Multi-Agente",
    description="Encolado asíncrono, checkpoints Redis, LangSmith y aprobación humana",
    version="1.0.0", lifespan=lifespan,
)


def store(request: Request) -> JobStore:
    return request.app.state.store


@app.get("/health")
async def health(request: Request):
    try:
        await request.app.state.store.redis.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis no disponible") from exc
    return {"status": "ok", "service": "api"}


@app.post("/tasks", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(check_api_key)])
async def create_task(body: TaskRequest, repository: JobStore = Depends(store)):
    item = await repository.create(body.task, body.max_steps, body.batch_id)
    return {
        "job_id": item["job_id"], "status": "PENDING",
        "status_url": f"/tasks/{item['job_id']}",
    }


@app.get("/tasks/{job_id}", dependencies=[Depends(check_api_key)])
async def get_task(job_id: str, repository: JobStore = Depends(store)):
    try:
        return await repository.get(valid_id(job_id))
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Job no encontrado") from exc


@app.post(
    "/tasks/{job_id}/approve", status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(check_api_key), Depends(check_reviewer_key)],
)
async def approve_task(
    job_id: str, body: ApprovalRequest, repository: JobStore = Depends(store),
):
    try:
        await repository.queue_approval(
            valid_id(job_id), body.approved, body.reviewer, body.comment,
        )
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Job no encontrado") from exc
    except Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job_id": job_id, "status": "APPROVAL_QUEUED", "approved": body.approved}
