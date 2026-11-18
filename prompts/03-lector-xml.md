# Prompt 3 · Lector de facturas DIAN

> Antes: si tienes 2 o 3 XML/ZIP reales de la DIAN, ponlos en `samples/` (no se suben a git).

---

Fase 2. Lector de XML DIAN:
- Recibe ZIP o XML. Si es AttachedDocument, extrae la factura (Invoice UBL 2.1) que viene dentro del CDATA.
- Extrae: CUFE (cbc:UUID), número, fecha, NIT y nombre del proveedor, NIT del comprador, líneas (descripción, cantidad, valor), subtotal, IVA, retenciones si vienen, total.
- Validaciones: subtotal + impuestos = total (con tolerancia), dígito de verificación del NIT, CUFE no repetido, fecha dentro del rango pedido, NIT del comprador = cliente seleccionado.
- Tests con pytest usando los fixtures y los XML reales de `./samples/` (si hay).
- También: importar el Excel de "documentos recibidos" de la DIAN para cruzar por CUFE y reportar faltantes.
