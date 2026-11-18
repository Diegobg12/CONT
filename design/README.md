# Diseño del flujo (aprobado)

Abre `1-cliente-fechas.html` en el navegador y sigue los botones hasta la pantalla 5.

| Archivo | Pantalla | Qué debe hacer en la beta real |
|---|---|---|
| `1-cliente-fechas.html` | Cliente y fechas | Lista de clientes desde la BD; crear una "descarga" con el rango. |
| `2-token.html` | Token DIAN | Recibir el enlace/código del token (solo en memoria) y lanzar el robot. |
| `3-descarga.html` | Descarga | Progreso real del robot; aviso naranja `#pausa` si la DIAN pide verificación; enlace al plan B. |
| `4-revision.html` | Revisión | Tabla Fecha · CUFE · Descripción · Valor · Código contable. Pendientes en naranja con selector; "Subir a Siigo" solo sin pendientes. |
| `5-subida.html` | Subida a Siigo | Progreso real y aviso "Subida exitosa" con el resumen. |

## Tokens de diseño (`styles.css`)

- Fondo exterior `#E9EBF2`, fondo app `#F6F7FB`, tarjetas blancas con radio 22 px.
- Texto `#15171C`, secundario `#5F6573`.
- Azul principal `#2F6BFF` (hover `#1E4FD6`), azul suave `#E6EEFF`.
- Pendiente / supervisor: naranja `#A84B00`, fondo `#FFF1E2`, fila `#FFF8EE`.
- Éxito: verde `#1D6B2A` / `#2FB36B`.
- Origen de la clasificación: Regla `#1E4FD6`, IA `#5B4BC4`, Supervisor `#1D6B2A`.
- Tipografía Inter (400/500/600/700). Botones tipo píldora de 50 px.

`common.js` dibuja el menú lateral y el stepper; cada página indica su paso con `data-current`.
Los datos y animaciones de las páginas son de ejemplo: en la beta se reemplazan por llamadas al backend.
