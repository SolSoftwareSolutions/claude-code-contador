#!/usr/bin/env python3
"""Status line de Claude Code.

  [Modelo]  ctx 182k/1000k ⚠  ·  Fable 82% ↻ jue 17 18:59  ·  Opus 40% ↻ …  ·  semana 49%  ·  5h 8%

- Contexto: verde < CTX_SOFT_TOKENS (100k), amarillo < CTX_WARN_TOKENS (150k), rojo por encima.
- Semana y 5h: vienen en el JSON oficial de la status line (rate_limits).
- Límites semanales por modelo (Fable, Opus… según SCOPED_MODEL_LABELS): Claude Code NO los
  pasa a la status line (issue anthropics/claude-code#92080). Solo se muestran los que tu plan
  tenga como ventana propia; si un modelo no la tiene, cuenta dentro de "semana".
  Se obtiene en segundo plano con la petición experimental `get_usage` de `claude -p`
  (la petición no lanza inferencia; comprueba en tu cuenta que no consume cuota) y se cachea CACHE_TTL segundos. Es una vía NO documentada:
  si deja de funcionar, la status line simplemente omite el dato.

Diagnóstico:  python3 ctx_statusline.py --fetch-now   (--dump muestra las ventanas en bruto)
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

SOFT = int(os.environ.get("CTX_SOFT_TOKENS", "100000"))
WARN = int(os.environ.get("CTX_WARN_TOKENS", "150000"))
CACHE_TTL = int(os.environ.get("FABLE_USAGE_TTL", "300"))  # el cliente no refresca más a menudo
LABELS = [x.strip() for x in os.environ.get("SCOPED_MODEL_LABELS", "Fable,Opus").split(",") if x.strip()]
CACHE_DIR = os.path.expanduser("~/.claude/cache")
CACHE = os.path.join(CACHE_DIR, "scoped-usage.json")
ATTEMPT = os.path.join(CACHE_DIR, "scoped-usage.attempt")

GREEN, YELLOW, RED, DIM, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


# ---------------------------------------------------------------- utilidades
def fmt_reset(value):
    """Epoch (int) o ISO-8601 -> 'jue 17 18:59' en hora local."""
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
        return f"{DIAS[dt.weekday()]} {dt.day} {dt:%H:%M}"
    except Exception:
        return "?"


def pct_color(p):
    return RED if p >= 85 else YELLOW if p >= 60 else GREEN


def to_pct(v):
    v = float(v)
    return v * 100 if isinstance(v, float) and 0 < v <= 1 and not float(v).is_integer() else v


# ------------------------------------------------------- obtención de Fable
def find_claude():
    for c in (shutil.which("claude"), os.path.expanduser("~/.local/bin/claude"),
              "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if c and os.path.exists(c):
            return c
    return None


def extract_scoped(rate_limits):
    """Todas las ventanas semanales por modelo, en las dos formas conocidas -> {label: {pct, resets_at}}."""
    found = {}
    for item in rate_limits.get("model_scoped") or []:
        name = str(item.get("display_name", "")).strip()
        if name and item.get("utilization") is not None:
            found[name] = {"pct": to_pct(item["utilization"]), "resets_at": item.get("resets_at")}
    for item in rate_limits.get("limits") or []:
        name = str((((item.get("scope") or {}).get("model") or {}).get("display_name", ""))).strip()
        if name and name not in found and item.get("percent") is not None:
            found[name] = {"pct": to_pct(item["percent"]), "resets_at": item.get("resets_at")}
    # Forma antigua del endpoint de uso: claves tipo seven_day_opus / seven_day_sonnet
    for key, item in rate_limits.items():
        if key.startswith("seven_day_") and isinstance(item, dict):
            name = key[len("seven_day_"):].capitalize()
            val = item.get("utilization", item.get("used_percentage"))
            if name not in found and val is not None:
                found[name] = {"pct": to_pct(val), "resets_at": item.get("resets_at")}
    return found


def fetch(timeout=25, dump=False):
    claude = find_claude()
    if not claude:
        return {"ts": time.time(), "error": "claude no encontrado en PATH"}
    req = json.dumps({"type": "control_request", "request_id": "u1",
                      "request": {"subtype": "get_usage", "skip_behaviors": True}}) + "\n"
    env = dict(os.environ)
    env.setdefault("USER", os.path.basename(os.path.expanduser("~")))
    cmd = [claude, "-p", "--input-format", "stream-json", "--output-format", "stream-json",
           "--verbose", "--model", "haiku", "--setting-sources", ""]
    try:
        proc = subprocess.run(cmd, input=req, capture_output=True, text=True,
                              timeout=timeout, env=env)
    except Exception as exc:
        return {"ts": time.time(), "error": f"fallo al ejecutar claude: {exc}"}
    types = []
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except Exception:
            continue
        types.append(f"{msg.get('type')}/{msg.get('subtype', '')}")
        if msg.get("type") != "control_response":
            continue
        resp = msg.get("response") or {}
        rl = resp.get("rate_limits") or (resp.get("response") or {}).get("rate_limits") or {}
        if resp.get("rate_limits_available") is False or \
                (resp.get("response") or {}).get("rate_limits_available") is False:
            return {"ts": time.time(), "error": "rate_limits_available=false (¿login con API key o USER vacío?)"}
        if dump:
            print(json.dumps(rl, indent=2, ensure_ascii=False))
        scoped = extract_scoped(rl)
        if not scoped:
            return {"ts": time.time(), "scoped": {}, "note": "sin ventanas por modelo en la respuesta",
                    "keys": sorted(rl.keys()), "response_keys": sorted(resp.keys())}
        return {"ts": time.time(), "scoped": scoped}
    return {"ts": time.time(), "error": "sin control_response",
            "claude": claude, "returncode": proc.returncode,
            "stdout_types": types[:10],
            "stderr": proc.stderr.strip()[-600:]}


def write_cache(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh)
    os.replace(tmp, CACHE)


def read_cache():
    try:
        with open(CACHE) as fh:
            return json.load(fh)
    except Exception:
        return None


def maybe_refresh(cache):
    """Lanza la obtención en segundo plano si la caché caducó (sin bloquear la status line)."""
    now = time.time()
    if cache and now - cache.get("ts", 0) < CACHE_TTL:
        return
    try:
        if now - os.path.getmtime(ATTEMPT) < CACHE_TTL:
            return
    except OSError:
        pass
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(ATTEMPT, "w") as fh:
            fh.write(str(now))
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--fetch"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        pass


# ------------------------------------------------------------------- render
def render(data):
    model = (data.get("model") or {}).get("display_name", "?")
    cw = data.get("context_window") or {}
    tokens = cw.get("total_input_tokens") or 0
    window = cw.get("context_window_size") or 0

    color = RED if tokens >= WARN else YELLOW if tokens >= SOFT else GREEN
    ctx = f"{color}ctx {tokens / 1000:.0f}k{RESET}"
    if window:
        ctx += f"{DIM}/{window // 1000}k{RESET}"
    if tokens >= 2 * WARN:
        ctx += f" {RED}🚨 compacta ya{RESET}"
    elif tokens >= WARN:
        ctx += f" {RED}⚠ /compact o /clear{RESET}"
    parts = [f"[{model}]", ctx]

    cache = read_cache()
    maybe_refresh(cache)
    scoped = (cache or {}).get("scoped") or {}
    stale = bool(cache) and time.time() - cache.get("ts", 0) > 3 * CACHE_TTL
    lower = {k.lower(): (k, v) for k, v in scoped.items()}
    for label in LABELS:
        if label.lower() not in lower:
            continue
        name, info = lower[label.lower()]
        p = float(info["pct"])
        mark = f"{DIM}~{RESET}" if stale else ""
        parts.append(f"{pct_color(p)}{name} {p:.0f}%{RESET}{mark} "
                     f"{DIM}↻ {fmt_reset(info.get('resets_at'))}{RESET}")

    rl = data.get("rate_limits") or {}
    week = (rl.get("seven_day") or {}).get("used_percentage")
    if week is not None:
        parts.append(f"{DIM}semana {float(week):.0f}%{RESET}")
    five = (rl.get("five_hour") or {}).get("used_percentage")
    if five is not None:
        parts.append(f"{DIM}5h {float(five):.0f}%{RESET}")
    return "  ·  ".join(parts)


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        write_cache(fetch())
        sys.exit(0)
    if "--fetch-now" in sys.argv or "--dump" in sys.argv:
        result = fetch(dump="--dump" in sys.argv)
        write_cache(result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        for name, info in (result.get("scoped") or {}).items():
            print(f"{name}: {info['pct']:.0f}% · reset local {fmt_reset(info.get('resets_at'))}")
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        print(render(payload))
    except Exception:
        print("")
