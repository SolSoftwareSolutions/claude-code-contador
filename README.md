# claude-code-contador

Una línea de estado y dos hooks para Claude Code que te enseñan en todo momento qué modelo usas, cuánto contexto llevas acumulado y cuánta cuota has gastado.

```
[Opus 5.5]  ·  ctx 135k/1000k  ·  Fable 42% ↻ jue 22 19:00  ·  semana 38%  ·  5h 8%
```

## Por qué

Cada mensaje de una conversación vuelve a leer todo el contexto anterior. Una conversación larga que salta de un tema a otro gasta cada vez más cuota, aunque escribas lo mismo, y Claude Code no te lo enseña mientras ocurre. Con el gasto a la vista es fácil adoptar un hábito sencillo: al cambiar de tema, `/compact` indicando con qué tiene que quedarse, o `/clear` si no necesitas nada de lo anterior.

## Qué incluye

| Fichero | Qué hace |
|---|---|
| `ctx_statusline.py` | Línea de estado: modelo, contexto (verde < 100k, amarillo < 150k, rojo por encima), cuota semanal, cuota de 5 horas y, si tu plan los tiene, límites semanales por modelo. |
| `ctx_warn.py` | Hook `UserPromptSubmit`: muestra la hora de envío de cada mensaje y avisa cuando el contexto pasa de 150k tokens. Puede bloquear el envío por encima de un umbral si lo activas. |
| `post_compact.py` | Hook `SessionStart` tras compactar: vuelve a darle a Claude el repositorio, la rama, los cambios sin commitear y los últimos commits. |
| `install.sh` | Copia los scripts a `~/.claude/hooks/` y los registra en `~/.claude/settings.json` sin pisar tu configuración. |
| `settings-snippet.json` | Lo mismo que hace el instalador, por si prefieres editar `settings.json` a mano. |

## Instalación

Requiere Python 3 y Claude Code.

```bash
git clone https://github.com/SolSoftwareSolutions/claude-code-contador.git
cd claude-code-contador
bash install.sh
```

Opciones:

- `--autocompact N` fija `autoCompactWindow=N`.
- `--subagent-model MODELO` fija `CLAUDE_CODE_SUBAGENT_MODEL`. Úsalo solo si quieres que los subagentes usen un modelo distinto del principal. Ten en cuenta que puede subir el coste si eliges un modelo más caro que el que usas.

El instalador guarda una copia de `settings.json` antes de tocarlo y no reemplaza una línea de estado que ya tengas. Reinicia las sesiones abiertas y comprueba los hooks con `/hooks`.

## Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `CTX_SOFT_TOKENS` | 100000 | Umbral del amarillo en la línea de estado |
| `CTX_WARN_TOKENS` | 150000 | Umbral del rojo y del aviso |
| `CTX_URGENT_TOKENS` | 300000 | Aviso urgente |
| `CTX_BLOCK_TOKENS` | 0 | Si es mayor que 0, bloquea el envío por encima de ese tamaño |
| `SCOPED_MODEL_LABELS` | Fable,Opus | Límites por modelo que se muestran si existen |
| `FABLE_USAGE_TTL` | 300 | Segundos de caché del dato por modelo |
| `PROMPT_TIMESTAMP` | 1 | 0 desactiva la hora de envío |
| `POST_COMPACT_INDEXES` | docs/MAPA.md,MAPA.md,CLAUDE.md | Ficheros índice que se citan tras compactar |

## Aviso sobre los límites por modelo

Modelo, contexto, cuota semanal y cuota de 5 horas vienen del JSON oficial que Claude Code pasa a la línea de estado. Los límites semanales por modelo no vienen ahí: se obtienen en segundo plano cada 5 minutos con una petición no documentada (`get_usage`) a `claude -p`. La petición no lanza inferencia, pero comprueba en tu cuenta que no consume cuota. Puede dejar de funcionar con cualquier actualización; si pasa, la línea de estado simplemente omite ese dato. Diagnóstico: `python3 ctx_statusline.py --fetch-now`.

## Desinstalar

1. Borra `statusLine` y los dos hooks (`ctx_warn.py`, `post_compact.py`) de `~/.claude/settings.json`, o restaura la copia `settings.json.bak-*`.
2. Borra `~/.claude/hooks/ctx_statusline.py`, `ctx_warn.py`, `post_compact.py` y `~/.claude/cache/scoped-usage.*`.

## Licencia

MIT. Carlos Delgado, Sol Software Solutions.
