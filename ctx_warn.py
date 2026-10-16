#!/usr/bin/env python3
"""Hook UserPromptSubmit: hora de envío de cada mensaje + aviso de contexto.

Muestra (sin bloquear):   ↑ 10:23:05
y si el contexto supera CTX_WARN_TOKENS (150k):
                          ↑ 10:23:05 · ⚠ Contexto en 172k tokens (umbral 150k) …

El tamaño de contexto se obtiene del último mensaje del asistente en el transcript
(input + cache_read + cache_creation); si después hubo una compactación, no avisa.
Nunca falla: ante cualquier error se limita a la hora (o sale en silencio).

Variables:
  PROMPT_TIMESTAMP=0         desactiva la hora de envío
  PROMPT_TIME_FORMAT=...     formato strftime (por defecto %H:%M:%S)
  CTX_WARN_TOKENS=150000     umbral de aviso
  CTX_URGENT_TOKENS=300000   umbral de aviso urgente
  CTX_BLOCK_TOKENS=0         >0 bloquea el prompt por encima de ese tamaño
"""
import json
import os
import sys
from datetime import datetime

WARN = int(os.environ.get("CTX_WARN_TOKENS", "150000"))
URGENT = int(os.environ.get("CTX_URGENT_TOKENS", "300000"))
BLOCK = int(os.environ.get("CTX_BLOCK_TOKENS", "0"))
SHOW_TIME = os.environ.get("PROMPT_TIMESTAMP", "1") != "0"
TIME_FMT = os.environ.get("PROMPT_TIME_FORMAT", "%H:%M:%S")


def last_context_tokens(path):
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        fh.seek(max(0, size - 4_000_000))  # basta con la cola del fichero
        lines = fh.read().splitlines()
    for raw in reversed(lines):
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        if entry.get("isSidechain"):
            continue
        if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            return None  # compactado después del último uso conocido
        msg = entry.get("message")
        usage = msg.get("usage") if isinstance(msg, dict) else None
        if entry.get("type") == "assistant" and usage:
            return (usage.get("input_tokens") or 0) \
                + (usage.get("cache_read_input_tokens") or 0) \
                + (usage.get("cache_creation_input_tokens") or 0)
    return None


stamp = f"↑ {datetime.now().strftime(TIME_FMT)}" if SHOW_TIME else ""

tokens = None
try:
    data = json.load(sys.stdin)
    path = data.get("transcript_path")
    if path and os.path.exists(path):
        tokens = last_context_tokens(path)
except Exception:
    tokens = None

k = (tokens or 0) // 1000
if tokens and BLOCK and tokens >= BLOCK:
    print(json.dumps({
        "decision": "block",
        "reason": f"⛔ Contexto en {k}k (límite {BLOCK // 1000}k). Ejecuta /compact <foco> o /clear y vuelve a enviar.",
    }))
    sys.exit(0)

parts = [stamp] if stamp else []
if tokens and tokens >= URGENT:
    parts.append(f"🚨 Contexto en {k}k tokens (más de {URGENT // 1000}k): cada mensaje relee al menos el doble que a {URGENT // 2000}k. "
                 f"Compacta ya con /compact <foco> o cierra con /clear.")
elif tokens and tokens >= WARN:
    parts.append(f"⚠ Contexto en {k}k tokens (umbral {WARN // 1000}k): cada mensaje relee todo. "
                 f"/compact <foco> si sigues con la tarea, /clear si cambias.")
if parts:
    print(json.dumps({"systemMessage": " · ".join(parts)}, ensure_ascii=False))
sys.exit(0)
