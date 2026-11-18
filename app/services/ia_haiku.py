"""Sugerencia de cuenta PUC con Claude Haiku (salida estructurada).

Se usa SOLO cuando DEMO_MODE=false y hay ANTHROPIC_API_KEY. En demo se usa la IA simulada.
El contexto es siempre del MISMO cliente: ficha, plan de cuentas, notas y hasta 5 facturas
aprobadas parecidas. Nunca se mezclan datos entre clientes.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

import anthropic
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import Settings
from app.models import Cliente, CuentaPUC, Factura

log = logging.getLogger("ia")
MAX_EJEMPLOS = 5
ESTADOS_APROBADOS = ("clasificada", "aprobada", "subida")


class SugerenciaIA(BaseModel):
    tipo: Literal["gasto", "costo", "inventario", "activo", "servicio"]
    cuenta: str
    centro_costo: str
    confianza: float
    explicacion: str
    segunda_cuenta: str
    segunda_confianza: float


SISTEMA = """Eres un contador colombiano que clasifica facturas de compra recibidas por una empresa.
Para cada factura eliges la cuenta del PUC (del plan de cuentas de ESA empresa) donde se registra.

Reglas:
- Usa solo códigos que estén en el plan de cuentas dado. Nunca inventes cuentas.
- "tipo" es uno de: gasto, costo, inventario, activo, servicio.
- "confianza" y "segunda_confianza" van de 0 a 1 y reflejan qué tan seguro estás. Si la factura es ambigua
  (por ejemplo, no se sabe si un bien se revende, se regala o se capitaliza), baja la confianza: un supervisor
  humano revisará los casos dudosos, así que es mejor admitir la duda que adivinar.
- "segunda_cuenta" es la alternativa más probable (distinta de "cuenta").
- "centro_costo": déjalo vacío ("") si no hay información para elegirlo.
- "explicacion": una o dos frases en español, concretas, para el contador.
- Las facturas anteriores aprobadas de la misma empresa muestran su criterio: síguelo cuando aplique."""


def _cliente(settings: Settings) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=2, timeout=60.0)


def _palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-záéíóúñ]{4,}", (texto or "").lower())}


def ejemplos_parecidos(s: Session, f: Factura, limite: int = MAX_EJEMPLOS) -> list[Factura]:
    """Facturas aprobadas del MISMO cliente: primero del mismo proveedor, luego por palabras en común."""
    candidatas = s.exec(
        select(Factura).where(Factura.cliente_id == f.cliente_id, Factura.id != f.id,
                              Factura.estado.in_(ESTADOS_APROBADOS), Factura.cuenta_codigo.is_not(None))
        .order_by(Factura.fecha.desc()).limit(500)
    ).all()
    base = _palabras(f.descripcion)

    def puntaje(x: Factura) -> tuple:
        return (x.proveedor_nit == f.proveedor_nit, len(base & _palabras(x.descripcion)))

    elegidas = sorted(candidatas, key=puntaje, reverse=True)
    return [x for x in elegidas if puntaje(x) > (False, 0)][:limite]


def construir_contexto(s: Session, f: Factura) -> tuple[str, str]:
    """Devuelve (sistema, mensaje). El sistema es estable por cliente (cacheable); el mensaje cambia por factura."""
    c = s.get(Cliente, f.cliente_id)
    plan = s.exec(select(CuentaPUC).where(CuentaPUC.cliente_id == f.cliente_id, CuentaPUC.activa == True)  # noqa: E712
                  .order_by(CuentaPUC.codigo)).all()
    ficha = (f"EMPRESA: {c.razon_social} (NIT {c.nit})\nACTIVIDAD: {c.actividad or 'sin dato'}\n"
             f"NOTAS DEL CONTADOR: {c.notas_contador or 'ninguna'}\n\nPLAN DE CUENTAS:\n"
             + "\n".join(f"- {p.codigo} {p.nombre} ({p.tipo})" for p in plan))
    lineas = "\n".join(f"  · {l.get('descripcion')} · cant {l.get('cantidad')} · ${l.get('valor')}" for l in f.lineas or [])
    ejemplos = ejemplos_parecidos(s, f)
    previas = "\n".join(f"- {e.proveedor_nombre}: «{e.descripcion}» → {e.cuenta_codigo} ({e.origen})" for e in ejemplos)
    mensaje = (f"FACTURA A CLASIFICAR\nProveedor: {f.proveedor_nombre} (NIT {f.proveedor_nit})\n"
               f"Número: {f.numero} · Fecha: {f.fecha}\nLíneas:\n{lineas}\n"
               f"Subtotal: ${f.subtotal} · IVA: ${f.iva} · Total: ${f.total}\n\n"
               f"FACTURAS ANTERIORES APROBADAS DE ESTA EMPRESA:\n{previas or '(ninguna todavía)'}")
    return SISTEMA + "\n\n" + ficha, mensaje


def sugerir(s: Session, f: Factura, settings: Settings) -> dict | None:
    """Consulta a Claude Haiku. Devuelve el dict de sugerencia o None si no se pudo (va al supervisor)."""
    sistema, mensaje = construir_contexto(s, f)
    codigos = set(s.exec(select(CuentaPUC.codigo).where(CuentaPUC.cliente_id == f.cliente_id)).all())
    try:
        r = _cliente(settings).messages.parse(
            model=settings.classifier_model,
            max_tokens=2048,
            output_config={"effort": "low"},
            system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": mensaje}],
            output_format=SugerenciaIA,
        )
    except anthropic.AuthenticationError:
        log.error("ANTHROPIC_API_KEY inválida")
        return {"error": "La llave de Anthropic no es válida"}
    except anthropic.RateLimitError:
        return {"error": "Límite de uso de la IA alcanzado; intenta más tarde"}
    except anthropic.APIStatusError as e:
        return {"error": f"La IA respondió con error {e.status_code}"}
    except anthropic.APIConnectionError:
        return {"error": "Sin conexión con la IA"}

    if r.stop_reason == "refusal" or r.parsed_output is None:
        return {"error": "La IA no devolvió una sugerencia"}
    p: SugerenciaIA = r.parsed_output
    if p.cuenta not in codigos:
        return {"error": f"La IA sugirió la cuenta {p.cuenta}, que no está en el plan del cliente"}
    clamp = lambda x: max(0.0, min(1.0, float(x)))  # noqa: E731
    return {
        "cuenta": p.cuenta, "confianza": clamp(p.confianza),
        "segunda": p.segunda_cuenta if p.segunda_cuenta in codigos else p.cuenta,
        "confianza2": clamp(p.segunda_confianza) if p.segunda_cuenta in codigos else 0.0,
        "tipo": p.tipo, "centro_costo": p.centro_costo or None, "explicacion": p.explicacion,
        "modelo": settings.classifier_model, "request_id": getattr(r, "_request_id", None),
    }
