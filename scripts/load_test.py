"""Carga: envía 5 tareas realmente concurrentes y espera sus estados finales.

El script mide latencia observada por cliente. El p95/costo A EVALUAR se toma
exclusivamente de LangSmith, no se sustituye por esta medición local.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv

load_dotenv()

TASK = (
    "Compará los planes ficticios Starter y Growth: investigá sus fuentes, "
    "calculá margen bruto y contribución mensual; recomendá cuál conviene "
    "según ambas métricas y citá los source_id."
)


async def run(url: str, timeout: int, *, poll_interval: float) -> dict:
    batch = "load5-" + uuid4().hex[:10]
    headers = {}
    if os.getenv("API_KEY"):
        headers["X-API-Key"] = os.environ["API_KEY"]
    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=30.0) as client:
        start = time.perf_counter()

        async def submit(index: int) -> dict:
            t0 = time.perf_counter()
            r = await client.post("/tasks", json={"task": TASK, "batch_id": batch})
            r.raise_for_status()
            return {"index": index, "job_id": r.json()["job_id"],
                    "enqueue_ms": round((time.perf_counter() - t0) * 1000, 2)}

        # Las cinco solicitudes se emiten en paralelo.
        jobs = await asyncio.gather(*(submit(n + 1) for n in range(5)))
        async def monitor(job: dict) -> dict:
            until = time.monotonic() + timeout
            while time.monotonic() < until:
                r = await client.get(f"/tasks/{job['job_id']}")
                r.raise_for_status()
                state = r.json()
                if state["status"] in {"DONE", "FAILED", "WAITING_APPROVAL"}:
                    return {**job, "final_status": state["status"],
                            "result_preview": (state.get("result") or "")[:150],
                            "error": state.get("error")}
                await asyncio.sleep(poll_interval)
            return {**job, "final_status": "TIMEOUT", "error": "Polling agotado"}

        results = await asyncio.gather(*(monitor(job) for job in jobs))
        report = {
            "batch_id": batch,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "requests": len(results),
            "duration_wall_seconds": round(time.perf_counter() - start, 2),
            "jobs": results,
            "notice": "El costo/token y p95 oficiales deben verificarse y capturarse en LangSmith.",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--poll-interval", type=float, default=2.0)
    p.add_argument("--output", default="screenshots/load5-report.json")
    args = p.parse_args()
    result = asyncio.run(run(args.url, args.timeout, poll_interval=args.poll_interval))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(item["final_status"] != "DONE" for item in result["jobs"]):
        raise SystemExit("Una o más tareas no finalizaron correctamente; revisar worker/logs")


if __name__ == "__main__":
    main()
