# Prompt 5 · Clasificación y verificación humana

---

Fase 4. Clasificador de facturas:
1. Reglas primero: si (cliente, NIT proveedor) tiene regla confirmada, aplica tipo, cuenta PUC y centro de costo sin IA. En la pantalla 4 se muestra como "Regla del proveedor".
2. Si no, llama a Claude Haiku (modelo "claude-haiku-5-5") con salida estructurada (tool use con JSON schema): tipo (gasto, costo, inventario, activo, servicio), cuenta PUC del plan de ESE cliente, centro de costo, confianza 0-1, explicación corta y una segunda opción con su confianza. En la pantalla 4 se muestra como "IA · 92%".
   Contexto del prompt: ficha del cliente (actividad), su plan de cuentas, notas del contador, y hasta 5 facturas anteriores aprobadas del mismo cliente parecidas a esta.
3. Si confianza < 0.80 o las dos opciones están a menos de 15 puntos: estado "para el supervisor" (fila naranja con selector), mostrando las dos sugerencias como en el diseño.
4. Cuando el supervisor asigna una cuenta: guarda la corrección y crea/actualiza la regla del proveedor (se confirma tras 2 coincidencias). Se muestra "Asignada por el supervisor · regla guardada".
5. Nunca mezclar memoria entre clientes. Registra qué regla o qué respuesta de IA se usó en cada factura.
Tests: reglas, umbral de confianza y que el modo demo deje exactamente 3 facturas para el supervisor.
