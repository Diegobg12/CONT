# CLAUDE.md · Facturas DIAN → Siigo (beta)

## Objetivo
Beta local para una demo con una firma contable (40 empresas). Flujo de 5 pasos:
1. Elegir cliente y rango de fechas → se crea una **descarga**.
2. Pegar el enlace/token de la DIAN (llega al correo del RUT del representante legal, dura 60 min).
3. Robot asistido (Playwright, navegador visible) descarga el listado (Excel) y los XML/ZIP de documentos **recibidos**.
4. Lector XML (UBL 2.1 / AttachedDocument) + clasificación (tipo y cuenta PUC): reglas por proveedor → Claude Haiku → supervisor.
5. "Subir a Siigo": envía las facturas aprobadas a Siigo Nube por API.

## Stack
- Python 3.11+, FastAPI + Uvicorn, SQLModel sobre SQLite, lxml, openpyxl (Excel DIAN), Playwright (Python, headed), SDK oficial `anthropic`, httpx (Siigo), pydantic-settings (lee `.env`), pytest.
- Frontend: HTML/CSS/JS de `design/` servido como estáticos por FastAPI. Sin framework, sin build.

## Estructura
```
app/
  main.py            # FastAPI: monta /static y /api, arranque y semilla
  config.py          # Settings (pydantic-settings, lee .env)
  db.py              # engine SQLite (data/app.db), sesión
  models.py          # SQLModel: Cliente, CuentaPUC, Descarga, Factura, ReglaProveedor, Correccion
  seed.py            # 3 clientes de design/ + PUC básico
  api/               # routers: clientes, descargas, facturas, siigo
  services/
    dian_robot.py    # Playwright headed; pausa ante verificación humana
    dian_demo.py     # simulación DIAN (DEMO_MODE)
    xml_reader.py    # AttachedDocument → Invoice UBL 2.1 → dict
    excel_dian.py    # listado "documentos recibidos" → cruce por CUFE
    classifier.py    # reglas → Haiku (tool use) → supervisor
    siigo.py         # cliente API Siigo Nube (+ DRY_RUN / demo)
    jobs.py          # estado en memoria de tareas en curso (progreso, pausa, token)
  static/            # copia de design/ conectada a la API (mismo HTML/CSS)
fixtures/            # ~12 XML de ejemplo para DEMO_MODE (3 ambiguos)
samples/             # XML reales + dian_codegen.py — FUERA DE GIT
data/, downloads/    # BD y descargas temporales — FUERA DE GIT
tests/
```

## Comandos
```bash
# Python 3.12 vía uv (este Mac es Intel y brew no lo instala sin Command Line Tools)
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload          # http://127.0.0.1:8000
pytest -q
```

## Configuración (`.env`, nunca en git)
`DEMO_MODE`, `DRY_RUN`, `ANTHROPIC_API_KEY`, `CLASSIFIER_MODEL` (claude-haiku-5-5), `CONFIDENCE_THRESHOLD` (0.80), `SIIGO_USERNAME`, `SIIGO_ACCESS_KEY`, `SIIGO_PARTNER_ID`.
Se lee solo vía `app/config.py`. Si falta una llave y no estamos en DEMO_MODE/DRY_RUN, fallar con un mensaje claro (sin imprimir valores).

## Reglas de seguridad (no negociables)
- Robot **asistido**: navegador VISIBLE (headed), ritmo humano, una empresa a la vez, reintentos limitados.
- Ante captcha, verificación humana o "Solicitud bloqueada por controles de seguridad": **PAUSAR** y esperar a que el usuario lo resuelva en la ventana. Prohibido resolver captchas con servicios, rotar IPs, ocultar el robot (stealth) o cualquier evasión.
- El token/enlace DIAN vive **solo en memoria** (objeto del job). Nunca en BD, disco, logs, excepciones ni respuestas de la API. Al terminar el job se descarta.
- Secretos solo en `.env`. Nunca imprimir ni loguear llaves.
- `samples/` y datos reales nunca en git. Autorización escrita de cada empresa antes de usar su token.
- Memoria/reglas/ejemplos de la IA **nunca se mezclan entre clientes** (todo filtrado por `cliente_id`).
- Plan B siempre disponible: subir a mano el Excel del listado y los ZIP.
- No inventar datos: si falta el XML de una factura, se marca como faltante.

## Regla de diseño
- `design/` es la fuente aprobada. El frontend reutiliza su HTML, `styles.css` y `common.js` **tal cual** (colores, Inter, tarjetas, stepper de 5 pasos, menú lateral).
- Solo se reemplazan datos de ejemplo por datos de la API y las simulaciones JS (setInterval) por llamadas al backend (polling 1 s).
- **No cambiar el diseño sin preguntar.** `design/` no se edita; se trabaja en `app/static/`.

## Convenciones
- Código y nombres de dominio en español (cliente, factura, descarga); comentarios breves en español.
- Dinero en `Decimal` (COP), fechas `date`. NIT guardado sin puntos ni DV, DV aparte.
- Estados de factura: `leida` → `clasificada` | `supervisor` → `aprobada` → `subida` | `error_siigo`.
- Origen de clasificación: `regla` | `ia` | `supervisor` (se guarda qué regla o qué respuesta de IA se usó).
- Cada fase termina con pruebas que pasan y un commit (`fase N`).
- DEMO_MODE debe funcionar siempre sin red ni llaves.
