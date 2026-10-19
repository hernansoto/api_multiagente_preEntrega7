"""Ejemplo de HITL: verificar pausa, aprobar o rechazar por API."""
from __future__ import annotations

import argparse
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

CRITICAL_TASK = (
    "Realizá una investigación pagada de costo muy alto, consultando fuentes "
    "externas masivamente, antes de analizar y comparar los planes ficticios Starter y Growth. "
    "Requiero aprobación antes de generar gastos."
)


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--reject", action="store_true", help="Rechazar en lugar de aprobar")
    args = p.parse_args()
    headers = {}
    if os.getenv("API_KEY"):
        headers["X-API-Key"] = os.environ["API_KEY"]
    async with httpx.AsyncClient(base_url=args.url, headers=headers, timeout=25) as http:
        create = await http.post("/tasks", json={"task": CRITICAL_TASK})
        create.raise_for_status()
        job_id = create.json()["job_id"]
        print("Job:", job_id)
        for _ in range(90):
            response = await http.get(f"/tasks/{job_id}")
            response.raise_for_status()
            body = response.json()
            if body["status"] == "WAITING_APPROVAL":
                print("Pausa persistida en Redis:", body["approval_request"])
                break
            if body["status"] in {"DONE", "FAILED"}:
                raise RuntimeError(f"El job no quedó en WAITING_APPROVAL: {body}")
            await asyncio.sleep(2)
        else:
            raise RuntimeError("No se alcanzó WAITING_APPROVAL")
        approval_key = os.getenv("APPROVAL_API_KEY", "")
        if not approval_key:
            print("Falta APPROVAL_API_KEY. Aprobá por Swagger y X-Approval-Key.")
            return
        approval = await http.post(
            f"/tasks/{job_id}/approve",
            json={"approved": not args.reject, "reviewer": "demo", "comment": "Aprobación demo"},
            headers={"X-Approval-Key": approval_key},
        )
        approval.raise_for_status()
        print("Respuesta HITL:", approval.json())


if __name__ == "__main__":
    asyncio.run(main())
