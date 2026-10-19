"""Adaptadores para guardar evidencia de tool calls sin compartir prompts completos."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import BaseMessage, ToolMessage


def as_text(content: Any) -> str:
    """Normaliza las respuestas de modelos, incluidas listas de bloques de texto."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(block.get("text", "")) if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def collect_tool_json(messages: list[BaseMessage], allowed_names: set[str]) -> list[dict[str, Any]]:
    """Solo acepta ToolMessage con nombre permitido y payload JSON parseable."""
    payloads: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name not in allowed_names:
            continue
        try:
            payload = json.loads(as_text(message.content))
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and not payload.get("error"):
            payloads.append(payload)
    return payloads
