"""Fase 2: lector XML/ZIP, validaciones y listado Excel de la DIAN."""
import io
import re
import zipfile
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.excel_dian import ListadoInvalido, cruzar, leer_listado
from app.services.validacion import validar
from app.services.xml_reader import leer_archivo, leer_xml

ROOT = Path(__file__).resolve().parent.parent
FIX = sorted((ROOT / "fixtures").glob("*.xml"))
SAMPLES = sorted(p for p in (ROOT / "samples").glob("*") if p.suffix.lower() in (".xml", ".zip"))
ANDINA = "900456789"
OCT = dict(fecha_ini=date(2026, 10, 1), fecha_fin=date(2026, 10, 31))


def _bytes(i=0) -> bytes:
    return FIX[i].read_bytes()


def _invoice_interno(i=0) -> bytes:
    m = re.search(rb"<!\[CDATA\[(.*?)\]\]>", _bytes(i), re.S)
    return m.group(1).strip()


def _zip(miembros: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, c in miembros.items():
            z.writestr(n, c)
    return buf.getvalue()


# ---------- Lector ----------

def test_attached_e_invoice_directo_dan_lo_mismo():
    a = leer_xml(_bytes(5))
    b = leer_xml(_invoice_interno(5))
    assert a == b
    assert a.retenciones > 0 and a.iva > 0  # honorarios: IVA + retefuente
    assert a.proveedor_tipo_doc == "31"


def test_bom_y_espacios():
    assert leer_xml(b"\xef\xbb\xbf\n  " + _bytes(0)).cufe == leer_xml(_bytes(0)).cufe


def test_zip_con_xml_y_pdf():
    rs = leer_archivo("dian.zip", _zip({"a.xml": _bytes(0), "b.xml": _bytes(1), "a.pdf": b"%PDF-1.4"}))
    assert len(rs) == 2 and all(r.factura for r in rs)
    assert rs[0].archivo == "dian.zip/a.xml"


@pytest.mark.parametrize("nombre,contenido,mensaje", [
    ("solo_pdf.zip", _zip({"a.pdf": b"%PDF"}), "solo PDF"),
    ("roto.zip", b"no soy zip", "ZIP"),
    ("malo.xml", b"<Invoice><sin cerrar>", "mal formado"),
    ("factura.pdf", b"%PDF", "Formato no soportado"),
])
def test_errores_se_reportan_sin_lanzar(nombre, contenido, mensaje):
    (r,) = leer_archivo(nombre, contenido)
    assert r.factura is None and mensaje in r.error


def test_attached_con_application_response_no_es_factura():
    xml = _bytes(0).replace(b"<Invoice ", b"<ApplicationResponse ").replace(b"</Invoice>", b"</ApplicationResponse>")
    (r,) = leer_archivo("x.xml", xml)
    assert "no es una factura" in r.error


def test_no_resuelve_entidades_externas():
    xxe = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Invoice>&e;</Invoice>'
    (r,) = leer_archivo("xxe.xml", xxe)
    assert r.factura is None  # sin CUFE; y nunca lee el archivo


# ---------- Validaciones ----------

def _f(i=0):
    return leer_xml(_bytes(i))


def test_factura_valida_sin_alertas():
    for p in FIX:
        v = validar(leer_xml(p.read_bytes()), cliente_nit=ANDINA, cufes_existentes=set(), **OCT)
        assert v.rechazo is None and v.alertas == [], (p.name, v)


def test_comprador_distinto_rechaza_o_alerta_en_demo():
    f = _f()
    assert "no es el cliente" in validar(f, cliente_nit="901223004", cufes_existentes=set(), **OCT).rechazo
    v = validar(f, cliente_nit="901223004", cufes_existentes=set(), demo=True, **OCT)
    assert v.rechazo is None and any("no es el cliente" in a for a in v.alertas)


def test_cufe_repetido_rechaza():
    f = _f()
    assert "repetido" in validar(f, cliente_nit=ANDINA, cufes_existentes={f.cufe}, **OCT).rechazo


def test_totales_no_cuadran():
    f = replace(_f(), total_con_impuestos=_f().total_con_impuestos + Decimal(5000))
    assert any("no cuadran" in a for a in validar(f, cliente_nit=ANDINA, cufes_existentes=set(), **OCT).alertas)


def test_tolerancia_redondeo():
    f = _f()
    f = replace(f, total=f.total + Decimal("1.50"))
    assert validar(f, cliente_nit=ANDINA, cufes_existentes=set(), **OCT).alertas == []


def test_dv_invalido():
    f = replace(_f(), proveedor_dv="0")
    assert any("Dígito de verificación" in a for a in validar(f, cliente_nit=ANDINA, cufes_existentes=set(), **OCT).alertas)


def test_dv_no_aplica_a_cedula():
    f = replace(_f(), proveedor_dv="", proveedor_tipo_doc="13")
    assert validar(f, cliente_nit=ANDINA, cufes_existentes=set(), **OCT).alertas == []


def test_fecha_fuera_de_rango():
    v = validar(_f(), cliente_nit=ANDINA, cufes_existentes=set(), fecha_ini=date(2026, 11, 1), fecha_fin=date(2026, 11, 30))
    assert any("fuera del rango" in a for a in v.alertas)


# ---------- Listado Excel ----------

def _excel(filas: list[list], titulo: bool = False) -> bytes:
    wb = Workbook()
    ws = wb.active
    if titulo:  # algunos exports traen filas de título antes del encabezado
        ws.append(["Documentos recibidos"]); ws.append([])
    for f in filas:
        ws.append(f)
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def test_listado_demo_cruza_completo():
    filas = leer_listado((ROOT / "fixtures" / "listado_demo.xlsx").read_bytes())
    assert len(filas) == 12
    assert filas[0].nit_emisor and filas[0].fecha == date(2026, 10, 1) and filas[0].numero.startswith("FE")
    cufes = {leer_xml(p.read_bytes()).cufe for p in FIX}
    c = cruzar(filas, cufes)
    assert c["en_listado"] == 12 and c["faltantes"] == [] and c["sin_listado"] == []


def test_listado_faltantes_y_otros_documentos():
    contenido = _excel([
        ["Tipo de Documento", "CUFE/CUDE", "Folio", "Prefijo", "Fecha Emisión", "NIT Emisor", "Nombre Emisor", "Total"],
        ["Factura electrónica", "AAA", "1", "FE", "05-10-2026", "900.112.233", "Prov A", "1.190.000,00"],
        ["Factura electrónica", "BBB", "2", "FE", "06/10/2026", "800334455", "Prov B", 500000],
        ["Nota crédito electrónica", "CCC", "3", "NC", "07-10-2026", "800334455", "Prov B", 1000],
    ], titulo=True)
    filas = leer_listado(contenido)
    assert [f.cufe for f in filas] == ["AAA", "BBB", "CCC"]
    assert filas[0].total == Decimal("1190000.00") and filas[0].nit_emisor == "900112233"
    c = cruzar(filas, {"AAA", "ZZZ"})
    assert [f["cufe"] for f in c["faltantes"]] == ["BBB"]
    assert c["otros_documentos"] == 1 and c["sin_listado"] == ["ZZZ"]


def test_listado_sin_columna_cufe():
    with pytest.raises(ListadoInvalido):
        leer_listado(_excel([["Folio", "Total"], ["1", 2]]))
    with pytest.raises(ListadoInvalido):
        leer_listado(b"no es excel")


# ---------- XML reales del usuario (samples/, fuera de git) ----------

@pytest.mark.skipif(not SAMPLES, reason="No hay XML/ZIP reales en samples/")
@pytest.mark.parametrize("ruta", SAMPLES, ids=lambda p: p.name)
def test_samples_reales(ruta):
    rs = leer_archivo(ruta.name, ruta.read_bytes())
    leidas = [r for r in rs if r.factura]
    assert leidas, [r.error for r in rs]
    for r in leidas:
        f = r.factura
        assert f.cufe and f.proveedor_nit and f.total > 0
        v = validar(f, cliente_nit=f.comprador_nit, cufes_existentes=set(), fecha_ini=f.fecha, fecha_fin=f.fecha)
        assert not v.alertas, v.alertas
