# Prompt 4 · Robot asistido de la DIAN

> **Antes de pegar este prompt, graba tú mismo la navegación real.** Con el token de un cliente (y su autorización), en tu terminal:
>
> ```bash
> python -m playwright codegen "PEGA_AQUI_EL_ENLACE_DEL_TOKEN"
> ```
>
> Haz a mano el recorrido: entrar → documentos recibidos → rango de fechas → exportar listado → descargar documentos. Copia el código generado a `samples/dian_codegen.py` y **borra el enlace del token** antes de guardarlo.

---

Fase 3. Robot asistido DIAN con Playwright (navegador VISIBLE).
Usa `./samples/dian_codegen.py` como referencia de la navegación real que grabé (selectores y pasos).
- Entrada: enlace del token (pegado en la pantalla 2), cliente y rango de fechas.
- Pasos: abrir el enlace, ir a documentos recibidos, filtrar por el rango, descargar el listado (Excel) y los documentos de cada factura a una carpeta temporal por descarga.
- Si aparece cualquier verificación humana o mensaje de bloqueo ("Solicitud bloqueada por controles de seguridad"), PAUSA: muestra en la pantalla 3 el aviso naranja que ya existe en el diseño (`#pausa`) y espera a que yo la complete en la ventana; luego continúa. No intentes evadirla.
- Ritmo humano normal, una empresa a la vez, reintentos limitados, timeouts claros.
- Reporta progreso a la pantalla 3 (paso actual y "factura N de M").
- Si el portal solo entrega PDF y no XML, registra cuáles faltan para completarlas después; no inventes datos.
- El token solo vive en memoria durante la sesión; no lo guardes ni lo imprimas.
- Si algo falla, el enlace "plan B" de la pantalla 3 debe llevar a subir el Excel y los ZIP a mano, y seguir el flujo igual.
Al terminar: guíame para probarlo con un token real y dime qué revisar si se rompe un selector.
