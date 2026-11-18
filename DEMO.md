# Guion de la demo · revisión con la contadora

> Modo demo: facturas de ejemplo (proveedores ficticios), IA **simulada**, DIAN y Siigo **simulados**.
> No necesita internet, token DIAN, llave de Anthropic ni credenciales de Siigo.

## Antes de empezar (2 min)

```bash
cd "mega-facturas-dian"
source .venv/bin/activate
uvicorn app.main:app            # deja esta terminal abierta
```

1. Abre **http://127.0.0.1:8000** en Chrome.
2. Si ya hiciste pruebas: abajo a la derecha de la pantalla 1, clic en **Reiniciar demo** (dos clics: pide confirmación).
3. Verifica en `.env`: `DEMO_MODE=true` y `DRY_RUN=true`.

## Recorrido (5 min)

| Paso | Qué hacer | Qué mostrar / decir |
|---|---|---|
| 1 · Cliente y fechas | Deja **Distribuidora Andina SAS** y "Mes anterior" (octubre 2026). Continuar. | Se elige la empresa y el rango; la DIAN manda el token al correo del RUT del representante legal. |
| 2 · Token | Clic en "Solicitar token". Pega cualquier texto. "Ingresar a la DIAN". | El token dura 60 min, se usa una vez y **no se guarda**. |
| 3 · Descarga | Espera ~15 s. | Progreso real: sesión → listado → "factura N de 12" → clasificación. Si la DIAN pide verificar que hay una persona, el robot se pausa (aviso naranja). Enlace **plan B** para subir el Excel y los ZIP a mano. |
| 4 · Revisión | Mira la tabla. Filtra "Para el supervisor (3)". Asigna las 3 cuentas. | **Regla del proveedor** (azul): ya se conocía el proveedor. **IA · 96%** (violeta): sugerencia segura. **Naranja**: la IA dudó; muestra sus dos opciones. Al asignar queda "regla guardada" para ese proveedor. "Subir a Siigo" solo se activa sin pendientes. |
| 5 · Subida | Subir a Siigo. | Progreso y "Subida exitosa" con el resumen (simulada: aún no hay credenciales de Siigo). |

**Las 3 facturas dudosas (a propósito):**
- Mantenimiento + repuestos de montacargas: ¿5145 gasto o 1520 activo?
- Kit promocional exhibidor: ¿5240 publicidad o 1435 mercancía? (¿se vende o se regala?)
- Computador portátil: ¿1528 activo o 5195 gasto? (política de activos)

## Preguntas para la contadora (anota las respuestas)

1. **Plan de cuentas**: ¿el PUC de ejemplo (1435, 1520, 1524, 1528, 5110, 5120, 5130, 5135, 5145, 5195, 5235, 5240) se parece al que usan? ¿Usan subcuentas de 6–8 dígitos en Siigo?
2. **Las 3 dudosas**: ¿qué cuenta elegiría ella y por qué? (sirve para afinar las instrucciones de la IA).
3. **Umbral**: hoy va al supervisor si la IA tiene menos de 80% o si sus dos opciones están a menos de 15 puntos. ¿Le parece estricto o flojo?
4. **Reglas**: una regla de proveedor se confirma a las **2** asignaciones iguales. ¿Está bien, o un mismo proveedor puede ir a cuentas distintas (ej. una ferretería)?
5. **Centro de costo**: ¿lo usan en Siigo? Hoy está oculto.
6. **Validaciones**: se rechaza la factura si el comprador no es el cliente o si el CUFE ya se descargó; se alerta si los totales no cuadran, el DV del NIT es inválido o la fecha está fuera del rango. ¿Falta alguna (retenciones, IVA descontable, notas crédito)?
7. **Siigo**: ¿suben las compras como **factura de proveedor** o como **comprobante contable**? ¿Con qué tipo de documento y consecutivo?
8. **Pantalla 4**: ¿quiere ver las alertas de validación en la tabla (línea naranja bajo el proveedor)?

## Si algo falla en vivo

- **La pantalla se queda en 0%**: recarga la página (F5); el progreso vive en el servidor.
- **No hay facturas para el supervisor**: ya asignaste esas cuentas dos veces y las reglas quedaron confirmadas → **Reiniciar demo**.
- **Otro cliente que no es Andina**: funciona, pero quedan 7 para el supervisor (esos clientes no tienen reglas guardadas).
- **El servidor se cerró**: vuelve a correr `uvicorn app.main:app`.
- **Probar con XML reales**: en la pantalla 3 usa el **plan B** y sube los ZIP. En modo demo, los proveedores que no son de ejemplo no tienen IA simulada y van al supervisor (es lo esperado sin llave de Anthropic).
