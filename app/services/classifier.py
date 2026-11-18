"""Clasificación de facturas: reglas del proveedor → IA → supervisor.

Todo se filtra por cliente_id: nunca se mezclan reglas ni ejemplos entre clientes.
IA: en DEMO_MODE se simula (fixtures/demo_ia.json); con DEMO_MODE=false y ANTHROPIC_API_KEY usa Claude Haiku.
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache

from sqlmodel import Session, select

from app.config import ROOT, Settings
from app.models import Correccion, CuentaPUC, Factura, ReglaProveedor

COINCIDENCIAS_PARA_CONFIRMAR = 2


@lru_cache
def _demo_ia() -> dict:
    ruta = ROOT / "fixtures" / "demo_ia.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def _tipo(session: Session, cliente_id: int, codigo: str) -> str | None:
    c = session.exec(select(CuentaPUC).where(CuentaPUC.cliente_id == cliente_id, CuentaPUC.codigo == codigo)).first()
    return c.tipo if c else None


def _consultar_ia(session: Session, factura: Factura, settings: Settings) -> dict | None:
    if settings.demo_mode:
        r = _demo_ia().get(factura.proveedor_nit)
        return dict(r, modelo="demo") if r else None
    if not settings.anthropic_api_key:
        return {"error": "IA desactivada: falta ANTHROPIC_API_KEY"}
    from app.services import ia_haiku
    return ia_haiku.sugerir(session, factura, settings)


def necesita_supervisor(confianza: float, confianza2: float, settings: Settings) -> bool:
    return confianza < settings.confidence_threshold or (confianza - confianza2) < settings.confidence_gap


def clasificar(session: Session, factura: Factura, settings: Settings) -> Factura:
    regla = session.exec(
        select(ReglaProveedor).where(
            ReglaProveedor.cliente_id == factura.cliente_id,
            ReglaProveedor.proveedor_nit == factura.proveedor_nit,
            ReglaProveedor.confirmada == True,  # noqa: E712
        )
    ).first()
    if regla:
        factura.cuenta_codigo, factura.tipo, factura.centro_costo = regla.cuenta_codigo, regla.tipo, regla.centro_costo
        factura.origen, factura.regla_id, factura.confianza = "regla", regla.id, 1.0
        factura.estado = "clasificada"
        return factura

    ia = _consultar_ia(session, factura, settings)
    if not ia or "error" in ia:
        factura.estado, factura.origen = "supervisor", None
        factura.respuesta_ia = ia or {}
        factura.explicacion = (ia or {}).get("error") or "Proveedor sin regla y sin sugerencia de la IA."
        return factura

    factura.respuesta_ia = ia
    factura.sugerencias = [
        {"codigo": ia["cuenta"], "confianza": ia["confianza"]},
        {"codigo": ia["segunda"], "confianza": ia["confianza2"]},
    ]
    factura.explicacion = ia.get("explicacion", "")
    if necesita_supervisor(ia["confianza"], ia["confianza2"], settings):
        factura.estado, factura.origen, factura.cuenta_codigo = "supervisor", None, None
        factura.confianza = ia["confianza"]
    else:
        factura.cuenta_codigo = ia["cuenta"]
        factura.tipo = ia.get("tipo") or _tipo(session, factura.cliente_id, ia["cuenta"])
        factura.centro_costo = ia.get("centro_costo")
        factura.origen, factura.confianza, factura.estado = "ia", ia["confianza"], "clasificada"
    return factura


def asignar_supervisor(session: Session, factura: Factura, codigo: str, usuario: str = "supervisor") -> ReglaProveedor:
    """Guarda la corrección y crea/actualiza la regla del proveedor para ESTE cliente."""
    tipo = _tipo(session, factura.cliente_id, codigo)
    if tipo is None:
        raise ValueError(f"La cuenta {codigo} no está en el plan de cuentas del cliente")

    sugerida = factura.sugerencias[0]["codigo"] if factura.sugerencias else None
    session.add(Correccion(factura_id=factura.id, cliente_id=factura.cliente_id, sugerencia=sugerida,
                           cuenta_elegida=codigo, usuario=usuario))

    regla = session.exec(
        select(ReglaProveedor).where(
            ReglaProveedor.cliente_id == factura.cliente_id, ReglaProveedor.proveedor_nit == factura.proveedor_nit
        )
    ).first()
    if regla is None:
        regla = ReglaProveedor(cliente_id=factura.cliente_id, proveedor_nit=factura.proveedor_nit, tipo=tipo,
                               cuenta_codigo=codigo, coincidencias=1)
    elif regla.cuenta_codigo == codigo:
        regla.coincidencias += 1
    else:  # el supervisor cambió de opinión: la regla vuelve a empezar
        regla.cuenta_codigo, regla.tipo, regla.coincidencias, regla.confirmada = codigo, tipo, 1, False
    regla.confirmada = regla.coincidencias >= COINCIDENCIAS_PARA_CONFIRMAR
    regla.actualizada_en = datetime.now()
    session.add(regla)
    session.flush()

    factura.cuenta_codigo, factura.tipo, factura.origen = codigo, tipo, "supervisor"
    factura.regla_id, factura.estado = regla.id, "aprobada"
    session.add(factura)
    return regla
