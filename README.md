# claude-code-contador

Una línea de estado y dos hooks para Claude Code que te enseñan en todo momento el modelo, el contexto acumulado, la cuota semanal y la de 5 horas.

```
[Opus 5.5]  ·  ctx 135k/1000k  ·  Fable 42% ↻ jue 22 19:00  ·  semana 38%  ·  5h 8%
```

El instalador guarda una copia de tu configuración antes de tocar nada y no sustituye una línea de estado que ya tengas.

> [!WARNING]
> El porcentaje por modelo sale de una vía no documentada de Claude Code y puede dejar de funcionar con cualquier actualización. El resto usa los datos oficiales.

## Por qué

Cada mensaje de una conversación vuelve a leer todo el contexto anterior. Una conversación larga que salta de un tema a otro gasta cada vez más cuota, aunque escribas lo mismo, y Claude Code no te lo enseña mientras ocurre.

Con el gasto a la vista es fácil adoptar un hábito sencillo: al cambiar de tema, `/compact` indicando con qué tiene que quedarse, o `/clear` si no necesitas nada de lo anterior.

## Qué ves

| Elemento | Ejemplo | Significado |
|---|---|---|
| Modelo | `[Opus 5.5]` | Modelo activo en la sesión. |
| Contexto | `ctx 135k/1000k` | Tokens acumulados frente al tamaño de la ventana. Verde por debajo de 100k, amarillo hasta 150k y rojo por encima, con un aviso para compactar. |
| Límite por modelo | `Fable 42% ↻ jue 22 19:00` | Uso del límite semanal propio de ese modelo y cuándo se reinicia. Solo aparece si tu plan lo tiene. Una `~` indica que el dato tiene más de 15 minutos. |
| Semana | `semana 38%` | Cuota semanal consumida. |
| 5 horas | `5h 8%` | Cuota de la ventana de 5 horas consumida. |

Además, cada vez que envías un mensaje aparece la hora de envío (`↑ 10:23:05`) y, si el contexto pasa de 150k tokens, un aviso con lo que conviene hacer.

## Qué incluye

| Fichero | Qué hace |
|---|---|
| `ctx_statusline.py` | La línea de estado descrita arriba. |
| `ctx_warn.py` | Hook `UserPromptSubmit`: hora de envío de cada mensaje y aviso cuando el contexto pasa de 150k tokens. Si lo activas, bloquea el envío por encima de un umbral. |
| `post_compact.py` | Hook `SessionStart` tras compactar: vuelve a darle a Claude el repositorio, la rama, los cambios sin commitear y los últimos commits, para que no empiece a ciegas. |
| `install.sh` | Copia los scripts a `~/.claude/hooks/` y los registra en `~/.claude/settings.json`. |
| `settings-snippet.json` | La misma configuración, por si prefieres editar `settings.json` a mano. |

## Instalación

Requisitos: Claude Code con sesión iniciada en una cuenta de Claude (no con API key) y Python 3. No hay dependencias externas.

```bash
git clone https://github.com/SolSoftwareSolutions/claude-code-contador.git
cd claude-code-contador
bash install.sh
```

Reinicia las sesiones abiertas y comprueba que los hooks están registrados con `/hooks`.

El instalador:

- guarda una copia de `settings.json` como `settings.json.bak-<fecha>` antes de escribir;
- no sustituye una línea de estado que ya tengas, solo te avisa;
- no duplica los hooks si lo ejecutas más de una vez, así que también sirve para actualizar;
- fija `timeFormat` a `%H:%M:%S` solo si no lo tenías definido.

Opciones:

- `--autocompact N` fija `autoCompactWindow=N`.
- `--subagent-model MODELO` fija `CLAUDE_CODE_SUBAGENT_MODEL`. Úsalo solo si quieres que los subagentes usen un modelo distinto del principal; si eliges uno más caro que el que usas, el coste sube.

Sin estas opciones no se toca ni la compactación automática ni el modelo de los subagentes.

### Instalación manual

Copia `ctx_statusline.py`, `ctx_warn.py` y `post_compact.py` a `~/.claude/hooks/` y añade el contenido de `settings-snippet.json` a tu `~/.claude/settings.json`.

## Configuración

Todo se ajusta con variables de entorno, que puedes poner en el bloque `env` de `settings.json`.

| Variable | Por defecto | Uso |
|---|---|---|
| `CTX_SOFT_TOKENS` | `100000` | Umbral del amarillo en la línea de estado |
| `CTX_WARN_TOKENS` | `150000` | Umbral del rojo y del aviso |
| `CTX_URGENT_TOKENS` | `300000` | Aviso urgente |
| `CTX_BLOCK_TOKENS` | `0` | Si es mayor que 0, bloquea el envío por encima de ese tamaño |
| `SCOPED_MODEL_LABELS` | `Fable,Opus` | Límites por modelo que se muestran si existen |
| `FABLE_USAGE_TTL` | `300` | Segundos de caché del dato por modelo |
| `PROMPT_TIMESTAMP` | `1` | `0` desactiva la hora de envío |
| `PROMPT_TIME_FORMAT` | `%H:%M:%S` | Formato `strftime` de la hora de envío |
| `POST_COMPACT_INDEXES` | `docs/MAPA.md,MAPA.md,CLAUDE.md` | Ficheros índice que se citan tras compactar |

Ejemplo:

```json
{
  "env": {
    "CTX_WARN_TOKENS": "200000",
    "CTX_BLOCK_TOKENS": "400000"
  }
}
```

## De dónde sale cada dato

Modelo, contexto, cuota semanal y cuota de 5 horas vienen del JSON oficial que Claude Code pasa a la línea de estado.

Los límites semanales por modelo no vienen ahí. Se obtienen en segundo plano, como mucho cada 5 minutos, con una petición no documentada (`get_usage`) a `claude -p`. La petición no lanza inferencia, pero comprueba en tu cuenta que no consume cuota. Si deja de funcionar, la línea de estado simplemente omite ese dato y el resto sigue igual.

## Solución de problemas

- **No aparece el porcentaje por modelo.** Ejecuta `python3 ~/.claude/hooks/ctx_statusline.py --fetch-now` para ver la respuesta y el error, o `--dump` para ver las ventanas en bruto. Lo habitual es que tu plan no tenga límite propio para ese modelo (entonces cuenta dentro de «semana») o que la sesión esté iniciada con API key.
- **No cambia la línea de estado.** Si ya tenías una, el instalador no la sustituye. Mira el mensaje que imprime y cambia `statusLine` a mano.
- **No aparecen los avisos.** Comprueba con `/hooks` que `ctx_warn.py` está registrado y reinicia la sesión.

## Desinstalar

1. Borra `statusLine` y los dos hooks (`ctx_warn.py`, `post_compact.py`) de `~/.claude/settings.json`, o restaura la copia `settings.json.bak-*`.
2. Borra `~/.claude/hooks/ctx_statusline.py`, `ctx_warn.py`, `post_compact.py` y `~/.claude/cache/scoped-usage.*`.

## Licencia

[MIT](LICENSE). Carlos Delgado, [Sol Software Solutions](https://www.solsoftwaresolutions.com).
