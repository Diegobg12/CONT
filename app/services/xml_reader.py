"""Lector de facturas electrónicas DIAN (UBL 2.1).

Acepta un Invoice directo o un AttachedDocument con la factura dentro del CDATA
(cac:Attachment/cac:ExternalReference/cbc:Description), sueltos o dentro de ZIP.
Las validaciones de negocio están en `validacion.py`.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

from app.services.nit import limpiar

NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
# Sin entidades externas ni red: los XML vienen de terceros.
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_blank_text=True)
MAX_ZIP_MIEMBRO = 20 * 1024 * 1024  # 20 MB por XML descomprimido


class FacturaInvalida(ValueError):
    pass


@dataclass
class Linea:
    descripcion: str
    cantidad: Decimal
    valor: Decimal


@dataclass
class FacturaLeida:
    cufe: str
    numero: str
    fecha: date
    proveedor_nit: str
    proveedor_dv: str
    proveedor_tipo_doc: str  # schemeName: 31 = NIT, 13 = cédula…
    proveedor_nombre: str
    comprador_nit: str
    comprador_nombre: str
    subtotal: Decimal  # LineExtensionAmount
    iva: Decimal
    impuestos: Decimal  # todos los TaxTotal (IVA, INC, ICA…)
    retenciones: Decimal
    total_con_impuestos: Decimal  # TaxInclusiveAmount
    total: Decimal  # PayableAmount
    descuentos: Decimal = Decimal(0)
    cargos: Decimal = Decimal(0)
    anticipos: Decimal = Decimal(0)
    lineas: list[Linea] = field(default_factory=list)

    @property
    def descripcion(self) -> str:
        if not self.lineas:
            return ""
        extra = f" (+{len(self.lineas) - 1} ítems)" if len(self.lineas) > 1 else ""
        return self.lineas[0].descripcion + extra

    def lineas_json(self) -> list[dict]:
        return [{k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(l).items()} for l in self.lineas]


@dataclass
class Resultado:
    """Resultado de leer un archivo: una factura o el motivo por el que no se pudo leer."""
    archivo: str
    factura: FacturaLeida | None = None
    error: str | None = None


def _txt(node, path: str, default: str = "") -> str:
    r = node.find(path, NS)
    return (r.text or "").strip() if r is not None and r.text else default


def _dec(node, path: str) -> Decimal:
    t = _txt(node, path, "0") or "0"
    try:
        return Decimal(t)
    except InvalidOperation as e:
        raise FacturaInvalida(f"Valor numérico inválido en {path}: {t!r}") from e


def _parse(contenido: bytes):
    if contenido.startswith(b"\xef\xbb\xbf"):
        contenido = contenido[3:]
    try:
        return etree.fromstring(contenido.strip(), _PARSER)
    except etree.XMLSyntaxError as e:
        raise FacturaInvalida(f"XML mal formado: {e}") from e


def _extraer_invoice(raiz):
    tag = etree.QName(raiz).localname
    if tag == "Invoice":
        return raiz
    if tag == "AttachedDocument":
        for desc in raiz.findall("cac:Attachment/cac:ExternalReference/cbc:Description", NS):
            texto = (desc.text or "").lstrip("﻿").strip()
            if not texto.startswith("<"):
                continue
            interna = _parse(texto.encode("utf-8"))
            nombre = etree.QName(interna).localname
            if nombre == "Invoice":
                return interna
            raise FacturaInvalida(f"El documento adjunto no es una factura de venta ({nombre})")
        raise FacturaInvalida("AttachedDocument sin factura embebida")
    raise FacturaInvalida(f"Tipo de documento no soportado: {tag}")


def leer_xml(contenido: bytes) -> FacturaLeida:
    inv = _extraer_invoice(_parse(contenido))

    prov = "cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme"
    comp = "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme"
    prov_id = inv.find(f"{prov}/cbc:CompanyID", NS)
    if prov_id is None:  # algunos emisores lo ponen solo en PartyLegalEntity
        prov_id = inv.find("cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:CompanyID", NS)
    comp_id = _txt(inv, f"{comp}/cbc:CompanyID") or _txt(
        inv, "cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:CompanyID")

    iva = impuestos = Decimal(0)
    for tt in inv.findall("cac:TaxTotal", NS):
        monto = _dec(tt, "cbc:TaxAmount")
        impuestos += monto
        if _txt(tt, "cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID") == "01":
            iva += monto
    ret = sum((_dec(w, "cbc:TaxAmount") for w in inv.findall("cac:WithholdingTaxTotal", NS)), Decimal(0))

    lineas = [
        Linea(descripcion=_txt(l, "cac:Item/cbc:Description"), cantidad=_dec(l, "cbc:InvoicedQuantity"),
              valor=_dec(l, "cbc:LineExtensionAmount"))
        for l in inv.findall("cac:InvoiceLine", NS)
    ]
    cufe = _txt(inv, "cbc:UUID")
    if not cufe:
        raise FacturaInvalida("Factura sin CUFE (cbc:UUID)")
    fecha_txt = _txt(inv, "cbc:IssueDate")
    try:
        fecha = date.fromisoformat(fecha_txt)
    except ValueError as e:
        raise FacturaInvalida(f"Fecha de emisión inválida: {fecha_txt!r}") from e

    lmt = "cac:LegalMonetaryTotal"
    return FacturaLeida(
        cufe=cufe,
        numero=_txt(inv, "cbc:ID"),
        fecha=fecha,
        proveedor_nit=limpiar(prov_id.text if prov_id is not None else ""),
        proveedor_dv=prov_id.get("schemeID", "") if prov_id is not None else "",
        proveedor_tipo_doc=prov_id.get("schemeName", "") if prov_id is not None else "",
        proveedor_nombre=_txt(inv, f"{prov}/cbc:RegistrationName")
        or _txt(inv, "cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name"),
        comprador_nit=limpiar(comp_id),
        comprador_nombre=_txt(inv, f"{comp}/cbc:RegistrationName"),
        subtotal=_dec(inv, f"{lmt}/cbc:LineExtensionAmount"),
        iva=iva,
        impuestos=impuestos,
        retenciones=ret,
        total_con_impuestos=_dec(inv, f"{lmt}/cbc:TaxInclusiveAmount"),
        total=_dec(inv, f"{lmt}/cbc:PayableAmount"),
        descuentos=_dec(inv, f"{lmt}/cbc:AllowanceTotalAmount"),
        cargos=_dec(inv, f"{lmt}/cbc:ChargeTotalAmount"),
        anticipos=_dec(inv, f"{lmt}/cbc:PrepaidAmount"),
        lineas=lineas,
    )


def leer_archivo(nombre: str, contenido: bytes) -> list[Resultado]:
    """Lee un XML o un ZIP (uno o varios XML dentro; los PDF se ignoran). Nunca lanza: reporta errores."""
    if nombre.lower().endswith(".zip"):
        try:
            z = zipfile.ZipFile(io.BytesIO(contenido))
        except zipfile.BadZipFile:
            return [Resultado(nombre, error="ZIP dañado o no es un ZIP")]
        out = []
        with z:
            xmls = [i for i in z.infolist() if i.filename.lower().endswith(".xml") and not i.is_dir()]
            if not xmls:
                return [Resultado(nombre, error="El ZIP no trae XML (¿solo PDF?)")]
            for info in xmls:
                etiqueta = f"{nombre}/{info.filename}"
                if info.file_size > MAX_ZIP_MIEMBRO:
                    out.append(Resultado(etiqueta, error="XML demasiado grande"))
                    continue
                out.append(_leer_uno(etiqueta, z.read(info)))
        return out
    if nombre.lower().endswith(".xml"):
        return [_leer_uno(nombre, contenido)]
    return [Resultado(nombre, error="Formato no soportado (se esperaba XML o ZIP)")]


def _leer_uno(nombre: str, contenido: bytes) -> Resultado:
    try:
        return Resultado(nombre, factura=leer_xml(contenido))
    except FacturaInvalida as e:
        return Resultado(nombre, error=str(e))


def leer_ruta(ruta: Path) -> list[Resultado]:
    return leer_archivo(ruta.name, ruta.read_bytes())
