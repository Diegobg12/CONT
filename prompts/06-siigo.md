# Prompt 6 · Subida a Siigo

> Antes: pon en `.env` las credenciales API de Siigo Nube de una empresa de prueba. Si no las tienes, deja `DRY_RUN=true`.

---

Fase 5. Integración con Siigo Nube (API oficial).
- Revisa la documentación oficial en developers.siigo.com antes de programar: autenticación (usuario API + access key, encabezado Partner-Id), y el endpoint correcto para registrar compras/facturas de proveedor o, si no aplica, comprobantes contables (journals). Dime cuál vas a usar y por qué antes de implementarlo.
- Flujo: autenticar → verificar/crear el proveedor como tercero → crear el documento con cuenta PUC, impuestos y total → guardar el ID que devuelve Siigo en la factura.
- Modo DRY_RUN (y en DEMO_MODE): no llama a Siigo; muestra el JSON que enviaría y simula éxito.
- Manejo de errores por factura (una que falla no detiene las demás) y resumen final: subidas, fallidas, motivo.
- Pantalla 5: progreso "factura N de M" y aviso final "Subida exitosa" con el resumen real (comprobantes, fallidas, reglas nuevas, tiempo).
