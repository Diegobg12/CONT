# Prompt 2 · Base del proyecto y modo demo

---

Fase 1. Implementa:
- Proyecto FastAPI con la estructura acordada, requirements.txt, completa `.env.example` si falta algo y actualiza el README con cómo correrlo.
- Modelos SQLite y una semilla con 3 clientes de ejemplo (los mismos de `design/1-cliente-fechas.html`, todos en Siigo Nube) y un plan de cuentas PUC básico (1435, 1520, 1528, 5110, 5120, 5135, 5145, 5195, 5235...).
- Sirve las 5 pantallas de `design/` desde FastAPI (copia a `app/static/` o similar) y conéctalas a endpoints reales: el estado de la "descarga" vive en el backend (cliente, rango, paso, progreso, facturas).
  - Pantalla 3 y 5: el progreso se lee del backend (polling cada segundo o SSE), no del setInterval de la maqueta.
  - Pantalla 4: la tabla se llena desde la API y la asignación del supervisor se guarda con un POST.
- MODO DEMO (variable DEMO_MODE=true): carpeta `fixtures/` con ~12 facturas XML de ejemplo realistas (UBL 2.1 dentro de AttachedDocument, proveedores ficticios, 3 de ellas ambiguas), y simulación de DIAN y Siigo con tiempos realistas.
Al terminar: corre el servidor, recorre el flujo completo en modo demo y dime cómo verlo en el navegador.
