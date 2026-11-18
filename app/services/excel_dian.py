"""Listado de "documentos recibidos" exportado del portal de la DIAN (Excel) y cruce por CUFE.

Los encabezados se buscan por nombre aproximado (sin tildes ni mayúsculas) porque la DIAN
los ha cambiado con el tiempo. Columnas mínimas: CUFE/CUDE. Las demás son opcionales.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from openpyxl import load_workbook

from app.services.nit import limpiar


class ListadoInvalido(ValueError):
    pass


@dataclass
class FilaListado:
    cufe: str
    tipo: str = ""
    numero: str = ""
    fecha: date | None = None
    nit_emisor: str = ""
    nombre_emisor: str = ""
    total: Decimal | None = None

    @property
    def es_factura(self) -> bool:
        t = _norm(self.tipo)
        return not t or ("factura" in t and "nota" not in t)

    def json(self) -> dict:
        return {"cufe": self.cufe, "tipo": self.tipo, "numero": self.numero,
                "fecha": self.fecha.isoformat() if self.fecha else None, "nit_emisor": self.nit_emisor,
                "nombre_emisor": self.nombre_emisor, "total": str(self.total) if self.total is not None else None}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# campo -> lista de predicados sobre el encabezado normalizado (el primero que coincide gana)
_COLUMNAS = {
    "cufe": [lambda h: "cufe" in h or "cude" in h],
    "tipo": [lambda h: h.startswith("tipo de documento") or h == "tipo documento" or h == "tipo"],
    "folio": [lambda h: h == "folio" or h.startswith("numero")],
    "prefijo": [lambda h: h == "prefijo"],
    "fecha": [lambda h: "fecha emision" in h, lambda h: h.startswith("fecha")],
    "nit_emisor": [lambda h: "nit emisor" in h, lambda h: "nit" in h and "emisor" in h],
    "nombre_emisor": [lambda h: "nombre emisor" in h, lambda h: "razon social emisor" in h],
    "total": [lambda h: h == "total", lambda h: h.startswith("total")],
}


def _mapear(encabezados: list[str]) -> dict[str, int]:
    norm = [_norm(h) for h in encabezados]
    out: dict[str, int] = {}
    for campo, preds in _COLUMNAS.items():
        for pred in preds:
            idx = next((i for i, h in enumerate(norm) if h and pred(h) and i not in out.values()), None)
            if idx is not None:
                out[campo] = idx
                break
    return out


def _fecha(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "").strip()[:10]
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _decimal(v) -> Decimal | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    s = str(v).replace("$", "").replace(" ", "")
    if "," in s and "." in s:  # 1.234.567,89
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def leer_listado(contenido: bytes) -> list[FilaListado]:
    try:
        wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception as e:  # openpyxl lanza varios tipos
        raise ListadoInvalido(f"No se pudo abrir el Excel: {type(e).__name__}") from e
    ws = wb.worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    wb.close()
    # El encabezado es la primera fila (entre las 10 primeras) que tenga una columna CUFE/CUDE.
    for i, fila in enumerate(filas[:10]):
        cols = _mapear([str(c or "") for c in fila])
        if "cufe" in cols:
            break
    else:
        raise ListadoInvalido("El Excel no tiene una columna CUFE/CUDE")

    def celda(fila, campo):
        j = cols.get(campo)
        return fila[j] if j is not None and j < len(fila) else None

    out = []
    for fila in filas[i + 1:]:
        cufe = str(celda(fila, "cufe") or "").strip()
        if not cufe:
            continue
        prefijo, folio = str(celda(fila, "prefijo") or "").strip(), str(celda(fila, "folio") or "").strip()
        out.append(FilaListado(
            cufe=cufe, tipo=str(celda(fila, "tipo") or "").strip(),
            numero=folio if folio.startswith(prefijo) else f"{prefijo}{folio}",
            fecha=_fecha(celda(fila, "fecha")), nit_emisor=limpiar(str(celda(fila, "nit_emisor") or "")),
            nombre_emisor=str(celda(fila, "nombre_emisor") or "").strip(), total=_decimal(celda(fila, "total")),
        ))
    return out


def cruzar(listado: list[FilaListado], cufes_xml: set[str]) -> dict:
    """Cruza por CUFE: facturas del listado sin XML (faltantes) y XML que no están en el listado."""
    facturas = [f for f in listado if f.es_factura]
    cufes_listado = {f.cufe for f in facturas}
    return {
        "en_listado": len(facturas),
        "otros_documentos": len(listado) - len(facturas),  # notas, eventos…
        "faltantes": [f.json() for f in facturas if f.cufe not in cufes_xml],
        "sin_listado": sorted(cufes_xml - cufes_listado),
    }
