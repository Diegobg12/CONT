"""Proceso de descarga: DIAN (demo, robot o plan B) → lectura XML → validación → cruce → clasificación."""
from __future__ import annotations

import shutil
import time

from sqlmodel import Session, delete, select

from app.config import ROOT, get_settings
from app.db import get_engine
from app.models import Cliente, Correccion, Descarga, Factura
from app.services import classifier
from app.services.excel_dian import ListadoInvalido, cruzar, leer_listado
from app.services.jobs import Job
from app.services.validacion import validar
from app.services.xml_reader import FacturaLeida, leer_archivo

# Pasos que muestra la pantalla 3 (índice = Job.etapa)
ETAPAS = ["Sesión iniciada en la DIAN", "Listado de facturas recibidas", "Facturas descargadas",
          "Clasificación con el código contable"]
FIXTURES = ROOT / "fixtures"


def _esperar(segundos: float) -> None:
    f = get_settings().demo_delay_factor
    if f > 0 and segundos > 0:
        time.sleep(segundos * f)


def _guardar(s: Session, d: Descarga, leida: FacturaLeida, alertas: list[str]) -> Factura:
    f = Factura(
        descarga_id=d.id, cliente_id=d.cliente_id, cufe=leida.cufe, numero=leida.numero, fecha=leida.fecha,
        proveedor_nit=leida.proveedor_nit, proveedor_dv=leida.proveedor_dv, proveedor_nombre=leida.proveedor_nombre,
        comprador_nit=leida.comprador_nit, descripcion=leida.descripcion, lineas=leida.lineas_json(),
        subtotal=leida.subtotal, iva=leida.iva, retenciones=leida.retenciones, total=leida.total, alertas=alertas,
    )
    s.add(f)
    return f


def procesar(s: Session, d: Descarga, job: Job, archivos: list[tuple[str, bytes]],
             listado: bytes | None = None, pausa_por_factura: float = 0.0) -> None:
    """Lee, valida, cruza con el listado y clasifica. Común a demo, robot y plan B."""
    settings = get_settings()
    cliente = s.get(Cliente, d.cliente_id)

    # Etapa 1: listado
    job.etapa = 1
    filas, rechazadas, facturas = [], [], []
    d.faltantes, d.listado = [], {}
    if listado:
        try:
            filas = leer_listado(listado)
        except ListadoInvalido as e:
            rechazadas.append({"archivo": "listado (Excel)", "cufe": None, "motivo": str(e)})
    resultados = [r for nombre, contenido in archivos for r in leer_archivo(nombre, contenido)]
    job.total = len(resultados)
    n_listado = sum(1 for f in filas if f.es_factura) if filas else len(resultados)
    job.mensaje = f"{n_listado} facturas del {d.fecha_ini:%d/%m/%Y} al {d.fecha_fin:%d/%m/%Y}"
    _esperar(1.5 if settings.demo_mode else 0)

    # Etapa 2: lectura + validación + guardado
    job.etapa = 2
    existentes = set(s.exec(select(Factura.cufe).where(Factura.cliente_id == d.cliente_id)).all())
    for i, r in enumerate(resultados, 1):
        _esperar(pausa_por_factura)
        job.n, job.mensaje = i, f"{i} de {job.total} · con su XML"
        if r.error:
            rechazadas.append({"archivo": r.archivo, "cufe": None, "motivo": r.error})
            continue
        v = validar(r.factura, cliente_nit=cliente.nit, fecha_ini=d.fecha_ini, fecha_fin=d.fecha_fin,
                    cufes_existentes=existentes, demo=settings.demo_mode)
        if v.rechazo:
            rechazadas.append({"archivo": r.archivo, "cufe": r.factura.cufe, "motivo": v.rechazo})
            continue
        existentes.add(r.factura.cufe)
        facturas.append(_guardar(s, d, r.factura, v.alertas))

    d.rechazadas = rechazadas
    d.total = len(facturas)
    if filas:
        cruce = cruzar(filas, {f.cufe for f in facturas} | {x["cufe"] for x in rechazadas if x["cufe"]})
        d.faltantes = cruce.pop("faltantes")
        d.listado = cruce
    s.add(d); s.commit()

    # Etapa 3: clasificación
    job.etapa = 3
    for i, f in enumerate(facturas, 1):
        _esperar(0.2 if settings.demo_mode else 0)
        classifier.clasificar(s, f, settings)
        s.add(f)
        job.mensaje = f"{i} de {len(facturas)} clasificadas"
    s.commit()

    pend = sum(1 for f in facturas if f.estado == "supervisor")
    job.etapa = 4
    job.mensaje = f"{len(facturas) - pend} asignadas · {pend} quedan para el supervisor"
    d.estado = "revision"
    s.add(d); s.commit()


def _borrar_demo_anterior(s: Session, cliente_id: int, cufes: list[str]) -> None:
    """Demo repetible: quita las facturas de ejemplo (y sus correcciones) que ya tuviera el cliente."""
    viejas = s.exec(select(Factura.id).where(Factura.cliente_id == cliente_id, Factura.cufe.in_(cufes))).all()
    if viejas:
        s.exec(delete(Correccion).where(Correccion.factura_id.in_(viejas)))
        s.exec(delete(Factura).where(Factura.id.in_(viejas)))
        s.commit()


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

        archivos = [(p.name, p.read_bytes()) for p in sorted(FIXTURES.glob("*.xml"))]
        cufes = [r.factura.cufe for n, c in archivos for r in leer_archivo(n, c) if r.factura]
        _borrar_demo_anterior(s, d.cliente_id, cufes)
        listado = FIXTURES / "listado_demo.xlsx"
        procesar(s, d, job, archivos, listado.read_bytes() if listado.exists() else None, pausa_por_factura=0.5)


def plan_b(archivos: list[tuple[str, bytes]], listado: bytes | None):
    """Plan B: el usuario sube el Excel y los ZIP/XML descargados a mano de la DIAN."""
    def correr(job: Job) -> None:
        with Session(get_engine()) as s:
            d = s.get(Descarga, job.descarga_id)
            d.estado, d.origen, d.error = "descargando", "plan_b", None
            s.add(d); s.commit()
            job.etapa, job.mensaje = 0, "Archivos subidos a mano (plan B)"
            procesar(s, d, job, archivos, listado)
    return correr


def robot_real(job: Job, opciones=None) -> None:
    """Robot asistido (navegador visible). Los archivos descargados se borran al terminar."""
    from app.services.dian_robot import RobotDIAN, RobotError

    token = job.tomar_token()
    carpeta = ROOT / "downloads" / f"descarga_{job.descarga_id}"
    with Session(get_engine()) as s:
        d = s.get(Descarga, job.descarga_id)
        d.estado, d.origen, d.error = "descargando", "robot", None
        s.add(d); s.commit()

        def al_pausar(pausado: bool) -> None:
            d.estado = "pausada" if pausado else "descargando"
            s.add(d); s.commit()

        try:
            robot = RobotDIAN(job, token, d.fecha_ini, d.fecha_fin, carpeta, al_pausar, opciones)
            token = None
            archivos, listado = robot.correr()
        except (RobotError, ValueError) as e:
            d.estado, d.error = "error", str(e)
            s.add(d); s.commit()
            job.error = d.error
            shutil.rmtree(carpeta, ignore_errors=True)
            return
        finally:
            token = None
        try:
            procesar(s, d, job, archivos, listado)
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)
