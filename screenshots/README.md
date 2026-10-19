# Evidencia requerida de LangSmith

Este directorio **no contiene capturas reales todavía**. No se simularon
valores de costos, tokens ni latencias.

Después de levantar Docker Compose con OPENAI_API_KEY y LANGSMITH_API_KEY
reales, correr `python scripts/load_test.py`. Guardar aquí:

1. `01-traces-five-jobs.png`: cinco trazas filtradas por el tag batch:load5-...
2. `02-cost-per-execution.png`: costo mostrado por LangSmith para cada run.
3. `03-latency-p95.png`: panel de latencia p95 del intervalo seleccionado.
4. `04-token-hotspot.png`: árbol de spans de un job, con nodo/LLM de más tokens.
5. `05-hitl-interrupt.png`: GET job WAITING_APPROVAL + traza de interrupción.
6. `06-hitl-resume.png`: traza tras usar el endpoint de aprobación o rechazo.

`load5-report.json` (generado por script) contiene IDs reales para encontrar
las trazas, pero **no reemplaza** los PNG solicitados por la rúbrica.

Si el dashboard no muestra costos, comprobar que LangSmith reconoce el modelo,
que el proveedor devuelve usage_metadata y que los cinco runs están completos.
