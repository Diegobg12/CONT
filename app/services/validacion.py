"""Validaciones de una factura leída contra la descarga en curso.

- Rechazos (la factura NO se importa): comprador distinto al cliente, CUFE repetido.
- Alertas (se importa y se avisa): totales que no cuadran, DV del NIT, fecha fuera del rango.
En DEMO_MODE el comprador distinto se vuelve alerta, para que la demo funcione con cualquier cliente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.services.nit import calcular_dv
from app.services.xml_reader import FacturaLeida

NIT_SCHEME = "31"


def tolerancia(f: FacturaLeida) -> Decimal:
    """Solo redondeos: $2, o $0,50 por línea si la factura tiene muchas líneas."""
    return max(Decimal(2), Decimal("0.5") * len(f.lineas))


@dataclass
class Validacion:
    rechazo: str | None = None
    alertas: list[str] = field(default_factory=list)


def validar(f: FacturaLeida, *, cliente_nit: str, fecha_ini: date, fecha_fin: date,
            cufes_existentes: set[str], demo: bool = False) -> Validacion:
    v = Validacion()

    if f.cufe in cufes_existentes:
        v.rechazo = "CUFE repetido: la factura ya se había descargado"
        return v

    if f.comprador_nit != cliente_nit:
        msg = f"El comprador (NIT {f.comprador_nit or '—'}) no es el cliente seleccionado"
        if not demo:
            v.rechazo = msg
            return v
        v.alertas.append(msg)

    # Totales: subtotal + impuestos = total con impuestos; y el valor a pagar cuadra con descuentos/cargos/anticipos.
    tol = tolerancia(f)
    if f.total_con_impuestos and abs(f.subtotal + f.impuestos - f.total_con_impuestos) > tol:
        v.alertas.append(f"Totales no cuadran: subtotal {f.subtotal} + impuestos {f.impuestos} ≠ {f.total_con_impuestos}")
    base = f.total_con_impuestos or (f.subtotal + f.impuestos)
    esperado = base - f.descuentos + f.cargos - f.anticipos
    if abs(esperado - f.total) > tol:
        v.alertas.append(f"Valor a pagar {f.total} no cuadra con {esperado}")
    if f.lineas and abs(sum(l.valor for l in f.lineas) - f.subtotal) > tol:
        v.alertas.append("La suma de las líneas no coincide con el subtotal")

    if f.proveedor_tipo_doc in ("", NIT_SCHEME) and f.proveedor_nit:
        if not f.proveedor_dv:
            v.alertas.append("El NIT del proveedor no trae dígito de verificación")
        elif f.proveedor_dv != calcular_dv(f.proveedor_nit):
            v.alertas.append(f"Dígito de verificación del NIT {f.proveedor_nit} no es válido ({f.proveedor_dv})")

    if not (fecha_ini <= f.fecha <= fecha_fin):
        v.alertas.append(f"Fecha {f.fecha:%d/%m/%Y} fuera del rango pedido")
    return v
