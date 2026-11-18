"""Lector de facturas electrónicas DIAN (UBL 2.1).

Acepta un Invoice directo o un AttachedDocument con la factura dentro del CDATA
(cac:Attachment/cac:ExternalReference/cbc:Description). La fase 2 agrega validaciones.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from lxml import etree

from app.services.nit import limpiar

NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "att": "urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


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
    proveedor_nombre: str
    comprador_nit: str
    comprador_nombre: str
    subtotal: Decimal
    iva: Decimal
    retenciones: Decimal
    total: Decimal
    lineas: list[Linea] = field(default_factory=list)

    @property
    def descripcion(self) -> str:
        if not self.lineas:
            return ""
        extra = f" (+{len(self.lineas) - 1} ítems)" if len(self.lineas) > 1 else ""
        return self.lineas[0].descripcion + extra

    def lineas_json(self) -> list[dict]:
        return [{k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(l).items()} for l in self.lineas]


def _txt(node, path: str, default: str = "") -> str:
    r = node.find(path, NS)
    return (r.text or "").strip() if r is not None and r.text else default


def _dec(node, path: str) -> Decimal:
    t = _txt(node, path, "0")
    return Decimal(t or "0")


def _extraer_invoice(raiz):
    tag = etree.QName(raiz).localname
    if tag == "Invoice":
        return raiz
    if tag == "AttachedDocument":
        desc = raiz.find("cac:Attachment/cac:ExternalReference/cbc:Description", NS)
        if desc is None or not (desc.text or "").strip():
            raise FacturaInvalida("AttachedDocument sin factura embebida")
        interna = etree.fromstring(desc.text.strip().encode("utf-8"), _PARSER)
        if etree.QName(interna).localname != "Invoice":
            raise FacturaInvalida(f"El documento embebido no es una factura ({etree.QName(interna).localname})")
        return interna
    raise FacturaInvalida(f"Tipo de documento no soportado: {tag}")


def leer_xml(contenido: bytes) -> FacturaLeida:
    try:
        raiz = etree.fromstring(contenido, _PARSER)
    except etree.XMLSyntaxError as e:
        raise FacturaInvalida(f"XML mal formado: {e}") from e
    inv = _extraer_invoice(raiz)

    prov = "cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme"
    comp = "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme"
    prov_id = inv.find(f"{prov}/cbc:CompanyID", NS)

    iva = Decimal(0)
    for tt in inv.findall("cac:TaxTotal", NS):
        if _txt(tt, "cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID") == "01":
            iva += _dec(tt, "cbc:TaxAmount")
    ret = sum((_dec(w, "cbc:TaxAmount") for w in inv.findall("cac:WithholdingTaxTotal", NS)), Decimal(0))

    lineas = [
        Linea(
            descripcion=_txt(l, "cac:Item/cbc:Description"),
            cantidad=_dec(l, "cbc:InvoicedQuantity"),
            valor=_dec(l, "cbc:LineExtensionAmount"),
        )
        for l in inv.findall("cac:InvoiceLine", NS)
    ]
    cufe = _txt(inv, "cbc:UUID")
    if not cufe:
        raise FacturaInvalida("Factura sin CUFE (cbc:UUID)")

    return FacturaLeida(
        cufe=cufe,
        numero=_txt(inv, "cbc:ID"),
        fecha=date.fromisoformat(_txt(inv, "cbc:IssueDate")),
        proveedor_nit=limpiar(prov_id.text if prov_id is not None else ""),
        proveedor_dv=prov_id.get("schemeID", "") if prov_id is not None else "",
        proveedor_nombre=_txt(inv, f"{prov}/cbc:RegistrationName"),
        comprador_nit=limpiar(_txt(inv, f"{comp}/cbc:CompanyID")),
        comprador_nombre=_txt(inv, f"{comp}/cbc:RegistrationName"),
        subtotal=_dec(inv, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount"),
        iva=iva,
        retenciones=ret,
        total=_dec(inv, "cac:LegalMonetaryTotal/cbc:PayableAmount"),
        lineas=lineas,
    )


def leer_archivo(nombre: str, contenido: bytes) -> list[FacturaLeida]:
    """Lee un XML o un ZIP (con uno o varios XML dentro)."""
    if nombre.lower().endswith(".zip"):
        facturas = []
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            for n in z.namelist():
                if n.lower().endswith(".xml"):
                    facturas.append(leer_xml(z.read(n)))
        return facturas
    return [leer_xml(contenido)]


def leer_ruta(ruta: Path) -> list[FacturaLeida]:
    return leer_archivo(ruta.name, ruta.read_bytes())
