"""Subida a Siigo Nube. Fase 1: simulada (DEMO_MODE / DRY_RUN). La fase 5 conecta la API real."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_engine
from app.models import Correccion, Descarga, Factura
from app.services.jobs import Job

log = logging.getLogger("siigo")
LISTAS = ("clasificada", "aprobada")


def payload_preview(f: Factura) -> dict:
    """JSON aproximado que se enviaría (el formato definitivo se define en la fase 5)."""
    return {"proveedor": {"nit": f.proveedor_nit, "dv": f.proveedor_dv, "nombre": f.proveedor_nombre},
            "factura_proveedor": f.numero, "fecha": f.fecha.isoformat(), "cufe": f.cufe,
            "cuenta": f.cuenta_codigo, "subtotal": str(f.subtotal), "iva": str(f.iva), "total": str(f.total)}


def subir(job: Job) -> None:
    settings = get_settings()
    simular = settings.demo_mode or settings.dry_run
    with Session(get_engine()) as s:
        d = s.get(Descarga, job.descarga_id)
        d.estado = "subiendo"
        s.add(d); s.commit()
        facturas = s.exec(select(Factura).where(Factura.descarga_id == d.id, Factura.estado.in_(LISTAS))).all()
        job.total = len(facturas)
        subidas = fallidas = 0
        motivos = []
        for i, f in enumerate(facturas, 1):
            job.n, job.mensaje = i, "creando comprobantes de compra"
            try:
                if not simular:
                    raise RuntimeError("La API real de Siigo llega en la fase 5 (usa DRY_RUN=true)")
                if settings.demo_delay_factor > 0:
                    time.sleep(0.35 * settings.demo_delay_factor)
                log.info("DRY_RUN Siigo: %s", json.dumps(payload_preview(f), ensure_ascii=False))
                f.siigo_id, f.estado, f.error = f"SIM-{f.id:05d}", "subida", None
                subidas += 1
            except Exception as e:  # una factura que falla no detiene las demás
                f.estado, f.error = "error_siigo", str(e)
                fallidas += 1
                motivos.append({"factura": f.numero, "motivo": str(e)})
            s.add(f); s.commit()

        reglas = len(s.exec(select(Correccion).join(Factura).where(Factura.descarga_id == d.id)).all())
        d.resumen_subida = {"comprobantes": subidas, "fallidas": fallidas, "reglas_nuevas": reglas,
                            "segundos": job.estado()["segundos"], "motivos": motivos, "simulada": simular}
        d.estado = "subida"  # las fallidas quedan en el resumen y en cada factura
        d.subida_en = datetime.now()
        s.add(d); s.commit()
