# MEGA projects · Facturas DIAN → Siigo (beta)

Beta para la demo con Luis: descargar facturas recibidas de la DIAN con el token del cliente, clasificarlas en su código contable (reglas + IA + supervisor) y subirlas a Siigo Nube.

## Cómo usar este paquete

1. Copia el contenido de esta carpeta en la raíz de tu repositorio.
2. Abre `design/1-cliente-fechas.html` en el navegador para ver las 5 pantallas (se navegan con los botones).
3. Copia `.env.example` a `.env` y llena las llaves.
4. En la raíz del repo, abre Claude Code: `claude`
5. Corre los prompts **en orden**, uno a la vez, desde `prompts/`:
   - `01-contexto-y-plan.md`: no programa; crea CLAUDE.md y el plan. Respóndele y da el OK.
   - `02-base-y-modo-demo.md`: flujo completo funcionando en modo demo.
   - `03-lector-xml.md`
   - `04-robot-dian.md`: antes graba la navegación con `playwright codegen` (ver el archivo).
   - `05-clasificacion.md`
   - `06-siigo.md`
   - `07-preparar-demo.md`
6. Al terminar cada fase: pruébala y haz un commit (`git add -A && git commit -m "fase N"`).

**Prioridad si no alcanza el tiempo:** modo demo completo, después el lector de XML y la clasificación, y al final el robot real y Siigo real.

## Carpetas

| Carpeta | Contenido |
|---|---|
| `design/` | Las 5 pantallas aprobadas (HTML + `styles.css` + `common.js`). Son la base del frontend. |
| `prompts/` | Los 7 prompts para Claude Code. |
| `fixtures/` | Facturas de ejemplo para el modo demo (las crea Claude Code en la fase 1). |
| `samples/` | Tus XML reales y la grabación `dian_codegen.py`. **No se suben a git.** |

## Reglas que no se negocian

- Robot asistido: navegador visible, pausa ante verificación humana, sin evadir controles de la DIAN.
- El token de la DIAN no se guarda ni se imprime.
- Autorización escrita de cada empresa cliente antes de usar su token.
- Llaves solo en `.env`.
