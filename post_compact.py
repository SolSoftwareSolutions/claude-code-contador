#!/usr/bin/env python3
"""Hook SessionStart (matcher "compact"): reinyecta contexto mínimo tras compactar.

Añade al contexto de Claude (≤1.500 caracteres):
  - repo, rama y estado frente al remoto
  - ficheros con cambios sin commitear (máx. 15)
  - últimos 5 commits
  - índices del repo si existen (POST_COMPACT_INDEXES, por defecto docs/MAPA.md, MAPA.md, CLAUDE.md)
Solo lectura (git --no-optional-locks). Ante cualquier error, no imprime nada.
"""
import json
import os
import subprocess
import sys

MAX_CHARS = 1500
INDEXES = tuple(x for x in os.environ.get("POST_COMPACT_INDEXES", "docs/MAPA.md,MAPA.md,CLAUDE.md").split(",") if x)

try:
    data = json.load(sys.stdin)
except Exception:
    data = {}
cwd = data.get("cwd") or os.getcwd()


def git(*args):
    try:
        r = subprocess.run(["git", "--no-optional-locks", "-C", cwd, *args],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.rstrip() if r.returncode == 0 else ""
    except Exception:
        return ""


try:
    lines = []
    root = git("rev-parse", "--show-toplevel")
    base = root or cwd
    if root:
        status = git("status", "-sb").splitlines()
        head = status[0].lstrip("#").strip() if status else ""
        changed = [l[3:] for l in status[1:] if len(l) > 3]
        lines.append(f"Repo: {root} · {head}")
        if changed:
            extra = " …" if len(changed) > 15 else ""
            lines.append(f"Cambios sin commitear ({len(changed)}): {', '.join(changed[:15])}{extra}")
        log = git("log", "--oneline", "-5")
        if log:
            lines.append("Últimos commits:\n" + log)
    found = [rel for rel in INDEXES if os.path.exists(os.path.join(base, rel))]
    if found:
        lines.append("Índices del repo (léelos antes de explorar a ciegas): " + ", ".join(found))
    if lines:
        text = "[Contexto tras compactar]\n" + "\n".join(lines)
        print(text[:MAX_CHARS])
except Exception:
    pass
sys.exit(0)
