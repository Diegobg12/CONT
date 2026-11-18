"""Genera las facturas de ejemplo del MODO DEMO en fixtures/.

Uso: python -m scripts.generar_fixtures
Crea 12 AttachedDocument (UBL 2.1) con proveedores ficticios y fixtures/demo_ia.json
con las respuestas simuladas de la IA. Todos los datos son inventados.
"""
import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from app.demo_data import COMPRADOR_DEMO, PROVEEDORES
from app.services.nit import calcular_dv

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "fixtures"
D2 = Decimal("0.01")


def m(v: Decimal) -> str:
    return str(v.quantize(D2, ROUND_HALF_UP))


def party(rol: str, nit: str, nombre: str) -> str:
    dv = calcular_dv(nit)
    return f"""  <cac:{rol}>
    <cac:Party>
      <cac:PartyName><cbc:Name>{escape(nombre)}</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:RegistrationName>{escape(nombre)}</cbc:RegistrationName>
        <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" schemeID="{dv}" schemeName="31">{nit}</cbc:CompanyID>
        <cbc:TaxLevelCode listName="48">R-99-PN</cbc:TaxLevelCode>
        <cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:{rol}>"""


def invoice(i: int, p: dict) -> tuple[str, str, str]:
    numero = f"FE{1000 + i * 37}"
    fecha = p["fecha"]
    lineas = [(d, Decimal(q), Decimal(q) * Decimal(pu)) for d, q, pu in p["lineas"]]
    subtotal = sum((v for _, _, v in lineas), Decimal(0))
    iva = (subtotal * Decimal("0.19")).quantize(D2, ROUND_HALF_UP) if p["iva"] else Decimal(0)
    total = subtotal + iva
    ret = (subtotal * Decimal(str(p["retefuente"]))).quantize(D2, ROUND_HALF_UP) if p.get("retefuente") else None

    base = f"{numero}{fecha}10:00:00-05:00{m(subtotal)}01{m(iva)}04{m(Decimal(0))}03{m(Decimal(0))}{m(total)}{p['nit']}{COMPRADOR_DEMO['nit']}demo2"
    cufe = hashlib.sha384(base.encode()).hexdigest()

    xml_lineas = "\n".join(
        f"""  <cac:InvoiceLine>
    <cbc:ID>{n}</cbc:ID>
    <cbc:InvoicedQuantity unitCode="94">{q}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="COP">{m(v)}</cbc:LineExtensionAmount>
    <cac:Item><cbc:Description>{escape(d)}</cbc:Description></cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="COP">{m(v / q)}</cbc:PriceAmount><cbc:BaseQuantity unitCode="94">1</cbc:BaseQuantity></cac:Price>
  </cac:InvoiceLine>"""
        for n, (d, q, v) in enumerate(lineas, 1)
    )
    tax = f"""  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="COP">{m(iva)}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="COP">{m(subtotal if p["iva"] else Decimal(0))}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="COP">{m(iva)}</cbc:TaxAmount>
      <cac:TaxCategory><cbc:Percent>{"19.00" if p["iva"] else "0.00"}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme></cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>"""
    if ret is not None:
        tax += f"""
  <cac:WithholdingTaxTotal>
    <cbc:TaxAmount currencyID="COP">{m(ret)}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="COP">{m(subtotal)}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="COP">{m(ret)}</cbc:TaxAmount>
      <cac:TaxCategory><cbc:Percent>{Decimal(str(p["retefuente"])) * 100:.2f}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>06</cbc:ID><cbc:Name>ReteRenta</cbc:Name></cac:TaxScheme></cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:WithholdingTaxTotal>"""

    inv = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>10</cbc:CustomizationID>
  <cbc:ProfileID>DIAN 2.1: Factura Electrónica de Venta</cbc:ProfileID>
  <cbc:ProfileExecutionID>1</cbc:ProfileExecutionID>
  <cbc:ID>{numero}</cbc:ID>
  <cbc:UUID schemeID="1" schemeName="CUFE-SHA384">{cufe}</cbc:UUID>
  <cbc:IssueDate>{fecha}</cbc:IssueDate>
  <cbc:IssueTime>10:00:00-05:00</cbc:IssueTime>
  <cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
  <cbc:Note>Factura de ejemplo · datos ficticios para el modo demo</cbc:Note>
  <cbc:DocumentCurrencyCode>COP</cbc:DocumentCurrencyCode>
  <cbc:LineCountNumeric>{len(lineas)}</cbc:LineCountNumeric>
{party("AccountingSupplierParty", p["nit"], p["nombre"])}
{party("AccountingCustomerParty", COMPRADOR_DEMO["nit"], COMPRADOR_DEMO["razon_social"])}
{tax}
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="COP">{m(subtotal)}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="COP">{m(subtotal if p["iva"] else Decimal(0))}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="COP">{m(total)}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="COP">{m(total)}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
{xml_lineas}
</Invoice>"""
    return numero, cufe, inv


def attached(numero: str, cufe: str, p: dict, inv: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>Documentos adjuntos</cbc:CustomizationID>
  <cbc:ProfileID>Factura Electrónica de Venta</cbc:ProfileID>
  <cbc:ProfileExecutionID>1</cbc:ProfileExecutionID>
  <cbc:ID>{numero}-AD</cbc:ID>
  <cbc:IssueDate>{p["fecha"]}</cbc:IssueDate>
  <cbc:IssueTime>10:05:00-05:00</cbc:IssueTime>
  <cbc:DocumentType>Contenedor de Factura Electrónica</cbc:DocumentType>
  <cbc:ParentDocumentID>{numero}</cbc:ParentDocumentID>
  <cac:SenderParty><cac:PartyTaxScheme><cbc:RegistrationName>{escape(p["nombre"])}</cbc:RegistrationName><cbc:CompanyID schemeID="{calcular_dv(p["nit"])}" schemeName="31">{p["nit"]}</cbc:CompanyID></cac:PartyTaxScheme></cac:SenderParty>
  <cac:ReceiverParty><cac:PartyTaxScheme><cbc:RegistrationName>{escape(COMPRADOR_DEMO["razon_social"])}</cbc:RegistrationName><cbc:CompanyID schemeID="{calcular_dv(COMPRADOR_DEMO["nit"])}" schemeName="31">{COMPRADOR_DEMO["nit"]}</cbc:CompanyID></cac:PartyTaxScheme></cac:ReceiverParty>
  <cac:Attachment>
    <cac:ExternalReference>
      <cbc:MimeCode>text/xml</cbc:MimeCode>
      <cbc:EncodingCode>UTF-8</cbc:EncodingCode>
      <cbc:Description><![CDATA[{inv}]]></cbc:Description>
    </cac:ExternalReference>
  </cac:Attachment>
  <cac:ParentDocumentLineReference>
    <cbc:LineID>1</cbc:LineID>
    <cac:DocumentReference>
      <cbc:ID>{numero}</cbc:ID>
      <cbc:UUID schemeName="CUFE-SHA384">{cufe}</cbc:UUID>
      <cbc:IssueDate>{p["fecha"]}</cbc:IssueDate>
      <cbc:DocumentType>ApplicationResponse</cbc:DocumentType>
    </cac:DocumentReference>
  </cac:ParentDocumentLineReference>
</AttachedDocument>
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*.xml"):
        f.unlink()
    ia = {}
    for i, p in enumerate(PROVEEDORES, 1):
        numero, cufe, inv = invoice(i, p)
        (OUT / f"{i:02d}_{numero}.xml").write_text(attached(numero, cufe, p, inv), encoding="utf-8")
        c = p["clasif"]
        if c[0] == "ia":
            ia[p["nit"]] = {"cuenta": c[1], "confianza": c[2], "segunda": c[3], "confianza2": c[4], "explicacion": c[5]}
    (OUT / "demo_ia.json").write_text(json.dumps(ia, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(PROVEEDORES)} facturas de ejemplo en {OUT}")


if __name__ == "__main__":
    main()
