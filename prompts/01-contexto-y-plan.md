# Prompt 1 · Contexto, plan y CLAUDE.md

> Pega todo lo que está debajo de la línea en Claude Code. No programa nada todavía: solo lee, pregunta y propone el plan.

---

Vamos a construir una BETA para una demo con un cliente (firma contable con 40 empresas).
Primero NO escribas código: lee esto, revisa la carpeta `design/` y el archivo `design/README.md`, haz preguntas si algo es ambiguo y propón un plan por fases.

OBJETIVO DEL FLUJO
1. El usuario elige un cliente (empresa) y un rango de fechas (inicial y final).
2. Solicita/pega el token de la DIAN (enlace que llega al correo del RUT del representante legal, dura 60 min).
3. Un robot asistido abre la DIAN con ese token, busca los documentos RECIBIDOS en el rango y descarga el listado y las facturas (XML/ZIP).
4. El sistema lee cada XML (UBL 2.1 / AttachedDocument) y clasifica cada factura (tipo y cuenta PUC) con reglas por proveedor primero y Claude Haiku solo si no hay regla.
5. Si la confianza es baja, la factura queda "para el supervisor", que elige la cuenta en la UI (y eso crea una regla para ese proveedor).
6. Botón "Subir a Siigo": envía las facturas aprobadas a Siigo Nube por API y muestra "Subida exitosa".

DISEÑO (OBLIGATORIO)
- La carpeta `design/` tiene las 5 pantallas aprobadas en HTML estático (`1-cliente-fechas.html` … `5-subida.html`), con `styles.css` y `common.js`.
- El frontend de la beta debe REUTILIZAR ese HTML y CSS tal cual (mismos colores, tipografía Inter, tarjetas, stepper de 5 pasos, menú lateral flotante). Solo reemplaza los datos de ejemplo por datos reales de la API y la simulación de JS por llamadas al backend.
- No cambies el diseño sin preguntarme.

RESTRICCIONES
- Corre LOCAL en mi computador. El navegador del robot es VISIBLE (Playwright headed).
- La DIAN detecta automatizaciones y puede pedir verificación humana: el robot debe PAUSARSE y esperar a que yo la resuelva en la ventana. Prohibido: resolver captchas con servicios, rotar IPs, ocultar el robot o cualquier evasión de controles. Una empresa a la vez, a ritmo normal.
- El token nunca se guarda en disco ni en logs.
- Plan B obligatorio: si el robot falla, el usuario puede subir manualmente el Excel del listado y los ZIP descargados de la DIAN.
- MODO DEMO obligatorio: con un flag usa facturas de ejemplo (fixtures) y simula DIAN y Siigo, para que la demo nunca falle.
- Secretos en .env (ANTHROPIC_API_KEY, SIIGO_USERNAME, SIIGO_ACCESS_KEY, SIIGO_PARTNER_ID). `.env` ya está en .gitignore.

STACK (simple)
- Python 3.11+, FastAPI, Playwright (Python), SQLite con SQLModel, lxml para XML, SDK oficial de Anthropic.
- Frontend: el HTML/CSS/JS de `design/` servido por FastAPI como archivos estáticos (sin framework).

ENTREGABLES DE ESTE PASO
1. Crea CLAUDE.md con: objetivo, stack, estructura de carpetas, comandos (instalar, correr, tests), reglas de seguridad de arriba, la regla de diseño y convenciones.
2. Propón la estructura de carpetas y el modelo de datos (clientes, descargas, facturas, reglas_proveedor, correcciones, plan_cuentas).
3. Lista las fases y qué se puede probar al final de cada una. Espera mi OK antes de programar.
