#!/usr/bin/env bash
# Instala/actualiza las utilidades de contexto en ~/.claude sin pisar tu configuración.
#   bash install.sh                          -> status line, hooks y timeFormat
#   bash install.sh --autocompact N          -> además fija autoCompactWindow=N
#   bash install.sh --subagent-model MODELO  -> además fija CLAUDE_CODE_SUBAGENT_MODEL=MODELO
# Las dos opciones se pueden combinar. Sin ellas no se toca ni la compactación ni el modelo
# de los subagentes. Antes de escribir, guarda una copia de settings.json.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
ACW="keep"
SUBAGENT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --autocompact) ACW="${2:?falta el valor}"; shift 2 ;;
    --subagent-model) SUBAGENT="${2:?falta el modelo}"; shift 2 ;;
    *) echo "Opción desconocida: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$DEST"
cp "$HERE/ctx_statusline.py" "$HERE/ctx_warn.py" "$HERE/post_compact.py" "$DEST/"
chmod +x "$DEST"/ctx_statusline.py "$DEST"/ctx_warn.py "$DEST"/post_compact.py
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak-$(date +%Y%m%d-%H%M%S)"

python3 - "$SETTINGS" "$ACW" "$SUBAGENT" <<'PY'
import json, sys
path, acw, subagent = sys.argv[1], sys.argv[2], sys.argv[3]
s = json.load(open(path))
notes = []

def ensure_hook(event, command, matcher=None, timeout=5):
    groups = s.setdefault("hooks", {}).setdefault(event, [])
    if any(h.get("command") == command for g in groups for h in g.get("hooks", [])):
        return f"Hook {event}{'/' + matcher if matcher else ''} ya presente."
    group = {"hooks": [{"type": "command", "command": command, "timeout": timeout}]}
    if matcher:
        group = {"matcher": matcher, **group}
    groups.append(group)
    return f"Hook {event}{'/' + matcher if matcher else ''} añadido."

# 1) status line (no se sobrescribe una ajena)
sl_cmd = "python3 ~/.claude/hooks/ctx_statusline.py"
if "statusLine" in s and s["statusLine"].get("command") != sl_cmd:
    notes.append(f"statusLine ajena ({s['statusLine'].get('command')}); NO se cambia.")
else:
    s["statusLine"] = {"type": "command", "command": sl_cmd, "refreshInterval": 60}
    notes.append("statusLine configurada (refresco cada 60 s).")

# 2) hooks
notes.append(ensure_hook("UserPromptSubmit", "python3 ~/.claude/hooks/ctx_warn.py"))
notes.append(ensure_hook("SessionStart", "python3 ~/.claude/hooks/post_compact.py", matcher="compact"))

# 3) modelo de los subagentes: solo bajo petición
if subagent:
    env = s.setdefault("env", {})
    env["CLAUDE_CODE_SUBAGENT_MODEL"] = subagent
    notes.append(f"CLAUDE_CODE_SUBAGENT_MODEL = {subagent} (a petición).")

# 4) horas en la interfaz
if "timeFormat" not in s:
    s["timeFormat"] = "%H:%M:%S"
    notes.append("timeFormat = %H:%M:%S.")

# 5) autoCompactWindow: solo bajo petición
if acw != "keep":
    s["autoCompactWindow"] = int(acw)
    notes.append(f"autoCompactWindow = {acw} (a petición).")

json.dump(s, open(path, "w"), indent=2, ensure_ascii=False)
print("\n".join(notes))
PY
echo "Hecho. Copia de seguridad: $SETTINGS.bak-*. Reinicia las sesiones abiertas y comprueba con /hooks."
