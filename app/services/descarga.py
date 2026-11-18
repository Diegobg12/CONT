"""Proceso de descarga: DIAN (demo o robot) → lectura XML → clasificación."""
from __future__ import annotations

import time

from sqlmodel import Session, select

from app.config import ROOT, get_settings
from app.db import get_engine
from app.models import Descarga, Factura
from app.services import classifier
from app.services.jobs import Job
from app.services.xml_reader import FacturaLeida, leer_ruta

# Pasos que muestra la pantalla 3 (índice = Job.etapa)
ETAPAS = ["Sesión iniciada en la DIAN", "Listado de facturas recibidas", "Facturas descargadas",
          "Clasificación con el código contable"]


def _esperar(segundos: float) -> None:
    f = get_settings().demo_delay_factor
    if f > 0:
        time.sleep(segundos * f)


def _guardar(session: Session, d: Descarga, leida: FacturaLeida) -> Factura:
    f = Factura(
        descarga_id=d.id, cliente_id=d.cliente_id, cufe=leida.cufe, numero=leida.numero, fecha=leida.fecha,
        proveedor_nit=leida.proveedor_nit, proveedor_dv=leida.proveedor_dv, proveedor_nombre=leida.proveedor_nombre,
        comprador_nit=leida.comprador_nit, descripcion=leida.descripcion, lineas=leida.lineas_json(),
        subtotal=leida.subtotal, iva=leida.iva, retenciones=leida.retenciones, total=leida.total,
    )
    session.add(f)
    return f


def simular_dian(job: Job) -> None:
    """MODO DEMO: simula la DIAN con las facturas de fixtures/ y tiempos realistas."""
    settings = get_settings()
    job.tomar_token()  # en demo no se usa: se descarta de inmediato
    with Session(get_engine()) as s:
        d = s.get(Descarga, job.descarga_id)
        d.estado, d.origen = "descargando", "demo"
        s.add(d); s.commit()

        job.etapa, job.mensaje = 0, "Con el token del cliente"
        _esperar(2.0)
        if settings.demo_simular_pausa:
            job.pausa, d.estado = True, "pausada"
            s.add(d); s.commit()
            _esperar(5.0)
            job.pausa, d.estado = False, "descargando"
            s.add(d); s.commit()

        archivos = sorted((ROOT / "fixtures").glob("*.xml"))
        job.etapa, job.total = 1, len(archivos)
        job.mensaje = f"{len(archivos)} facturas del {d.fecha_ini:%d/%m/%Y} al {d.fecha_fin:%d/%m/%Y}"
        _esperar(1.5)

        # Demo repetible: se reemplazan las facturas de ejemplo que ya existieran para este cliente.
        leidas = [leer_ruta(a)[0] for a in archivos]
        cufes = [l.cufe for l in leidas]
        for vieja in s.exec(select(Factura).where(Factura.cliente_id == d.cliente_id, Factura.cufe.in_(cufes))).all():
            s.delete(vieja)
        s.commit()

        job.etapa = 2
        facturas = []
        for i, leida in enumerate(leidas, 1):
            _esperar(0.5)
            facturas.append(_guardar(s, d, leida))
            job.n, job.mensaje = i, f"{i} de {job.total} · con su XML"
        d.total = len(facturas)
        s.add(d); s.commit()

        job.etapa = 3
        for i, f in enumerate(facturas, 1):
            _esperar(0.2)
            classifier.clasificar(s, f, settings)
            s.add(f)
            job.mensaje = f"{i} de {len(facturas)} clasificadas"
        s.commit()

        pend = sum(1 for f in facturas if f.estado == "supervisor")
        job.etapa = 4
        job.mensaje = f"{len(facturas) - pend} asignadas · {pend} quedan para el supervisor"
        d.estado = "revision"
        s.add(d); s.commit()


def robot_real(job: Job) -> None:
    """Fase 3: robot Playwright con navegador visible. Aún no implementado."""
    job.tomar_token()
    with Session(get_engine()) as s:
        d = s.get(Descarga, job.descarga_id)
        d.estado, d.error = "error", "El robot real de la DIAN llega en la fase 3. Usa DEMO_MODE=true o el plan B."
        s.add(d); s.commit()
        job.error = d.error
