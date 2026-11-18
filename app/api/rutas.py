"""API JSON consumida por las 5 pantallas."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, select
from sqlmodel import delete as sql_delete

from app.config import get_settings
from app.db import get_session
from app.models import Cliente, Correccion, CuentaPUC, Descarga, Factura
from app.services import classifier, descarga as proc_descarga, jobs, siigo
from app.services.dian_robot import EnlaceInvalido, validar_enlace
from app.services.nit import formatear

router = APIRouter(prefix="/api")


def enmascarar(email: str) -> str:
    usuario, _, dominio = email.partition("@")
    return f"{usuario[:1]}••••••@{dominio}" if dominio else "••••••"


def _cliente_json(c: Cliente) -> dict:
    return {"id": c.id, "razon_social": c.razon_social, "nit": formatear(c.nit, c.dv),
            "email": enmascarar(c.email_rut), "programa": c.programa}


def _descarga_json(s: Session, d: Descarga) -> dict:
    # Primero el estado de las tareas y luego la BD: así nunca se ve "terminado" con un estado viejo.
    estados = {t: (j.estado() if (j := jobs.obtener(d.id, t)) else None) for t in ("descarga", "subida")}
    s.refresh(d)
    c = s.get(Cliente, d.cliente_id)
    out = {"id": d.id, "cliente": _cliente_json(c), "fecha_ini": d.fecha_ini.isoformat(),
           "fecha_fin": d.fecha_fin.isoformat(), "estado": d.estado, "origen": d.origen, "total": d.total,
           "error": d.error, "resumen_subida": d.resumen_subida or None, "etapas": proc_descarga.ETAPAS,
           "faltantes": d.faltantes or [], "rechazadas": d.rechazadas or [], "listado": d.listado or None}
    for tipo, estado in estados.items():
        out[f"job_{tipo}"] = estado
    return out


def _descarga_o_404(s: Session, descarga_id: int) -> Descarga:
    d = s.get(Descarga, descarga_id)
    if not d:
        raise HTTPException(404, "Descarga no encontrada")
    return d


@router.get("/config")
def config():
    st = get_settings()
    return {"demo_mode": st.demo_mode, "dry_run": st.dry_run}


@router.get("/clientes")
def listar_clientes(s: Session = Depends(get_session)):
    return [_cliente_json(c) for c in s.exec(select(Cliente).order_by(Cliente.id))]


@router.get("/clientes/{cliente_id}/descargas")
def descargas_cliente(cliente_id: int, s: Session = Depends(get_session)):
    ds = s.exec(select(Descarga).where(Descarga.cliente_id == cliente_id, Descarga.total > 0)
                .order_by(Descarga.fecha_ini.desc(), Descarga.id.desc()).limit(5))
    return [{"id": d.id, "fecha_ini": d.fecha_ini.isoformat(), "fecha_fin": d.fecha_fin.isoformat(),
             "total": d.total, "estado": d.estado} for d in ds]


class NuevaDescarga(BaseModel):
    cliente_id: int
    fecha_ini: date
    fecha_fin: date

    @model_validator(mode="after")
    def rango(self):
        if self.fecha_fin < self.fecha_ini:
            raise ValueError("La fecha final es anterior a la inicial")
        return self


@router.post("/descargas")
def crear_descarga(body: NuevaDescarga, s: Session = Depends(get_session)):
    if not s.get(Cliente, body.cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    d = Descarga(**body.model_dump())
    s.add(d); s.commit(); s.refresh(d)
    return _descarga_json(s, d)


@router.get("/descargas/{descarga_id}")
def ver_descarga(descarga_id: int, s: Session = Depends(get_session)):
    return _descarga_json(s, _descarga_o_404(s, descarga_id))


@router.post("/descargas/{descarga_id}/solicitar-token")
def solicitar_token(descarga_id: int, s: Session = Depends(get_session)):
    d = _descarga_o_404(s, descarga_id)
    c = s.get(Cliente, d.cliente_id)
    # Demo: simulado. Real: la solicitud se hace en el portal de la DIAN (fase 3).
    return {"enviado_a": enmascarar(c.email_rut), "vence_min": 60, "simulado": get_settings().demo_mode}


class Token(BaseModel):
    model_config = {"hide_input_in_errors": True}
    token: str = Field(min_length=1)

    def __repr__(self) -> str:
        return "Token(***)"


@router.post("/descargas/{descarga_id}/iniciar")
def iniciar(descarga_id: int, body: Token, s: Session = Depends(get_session)):
    d = _descarga_o_404(s, descarga_id)
    if d.estado not in ("creada", "error"):
        raise HTTPException(409, "Esta descarga ya se inició")
    demo = get_settings().demo_mode
    if not demo:
        try:
            validar_enlace(body.token)  # el mensaje de error no incluye el enlace
        except EnlaceInvalido as e:
            raise HTTPException(422, str(e))
        if jobs.alguno_en_curso("descarga"):
            raise HTTPException(409, "El robot ya está descargando otra empresa. Una empresa a la vez.")
    objetivo = proc_descarga.simular_dian if demo else proc_descarga.robot_real
    d.error = None
    s.add(d); s.commit()
    try:
        jobs.lanzar(d.id, "descarga", objetivo, token=body.token.strip())
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


MAX_PLAN_B = 200 * 1024 * 1024  # 200 MB en total


@router.post("/descargas/{descarga_id}/plan-b")
async def subir_plan_b(descarga_id: int, archivos: list[UploadFile] = File(...),
                       listado: UploadFile | None = File(None), s: Session = Depends(get_session)):
    """Plan B: Excel del listado (opcional) + ZIP/XML descargados a mano de la DIAN."""
    d = _descarga_o_404(s, descarga_id)
    if jobs.en_curso(d.id, "descarga"):
        raise HTTPException(409, "Hay una descarga en curso para este cliente")
    if d.estado in ("subiendo", "subida"):
        raise HTTPException(409, "Esta descarga ya se subió a Siigo")
    datos, tam = [], 0
    for a in archivos:
        contenido = await a.read()
        tam += len(contenido)
        datos.append((a.filename or "archivo", contenido))
    excel = await listado.read() if listado is not None and listado.filename else None
    tam += len(excel or b"")
    if tam > MAX_PLAN_B:
        raise HTTPException(413, "Los archivos superan 200 MB")
    if d.total:  # reemplaza lo que hubiera de un intento anterior en esta descarga
        ids = s.exec(select(Factura.id).where(Factura.descarga_id == d.id, Factura.estado != "subida")).all()
        s.exec(sql_delete(Correccion).where(Correccion.factura_id.in_(ids)))
        s.exec(sql_delete(Factura).where(Factura.id.in_(ids)))
        s.commit()
    jobs.lanzar(d.id, "descarga", proc_descarga.plan_b(datos, excel))
    return {"ok": True, "archivos": len(datos)}


def _fila(f: Factura, puc: dict[str, str]) -> dict:
    cuenta = f"{f.cuenta_codigo} · {puc.get(f.cuenta_codigo, '')}" if f.cuenta_codigo else None
    return {"id": f.id, "fecha": f.fecha.isoformat(), "cufe": f.cufe, "numero": f.numero,
            "descripcion": f.descripcion, "proveedor": f.proveedor_nombre, "total": str(f.total),
            "cuenta": cuenta, "origen": f.origen, "confianza": f.confianza, "estado": f.estado,
            "sugerencias": [dict(x, nombre=puc.get(x["codigo"], "")) for x in (f.sugerencias or [])],
            "explicacion": f.explicacion, "regla_nueva": f.origen == "supervisor", "error": f.error,
            "alertas": f.alertas or []}


@router.get("/descargas/{descarga_id}/facturas")
def facturas(descarga_id: int, s: Session = Depends(get_session)):
    d = _descarga_o_404(s, descarga_id)
    cuentas = s.exec(select(CuentaPUC).where(CuentaPUC.cliente_id == d.cliente_id, CuentaPUC.activa == True)  # noqa: E712
                     .order_by(CuentaPUC.codigo)).all()
    puc = {c.codigo: c.nombre for c in cuentas}
    fs = s.exec(select(Factura).where(Factura.descarga_id == d.id).order_by(Factura.fecha, Factura.id)).all()
    return {
        "descarga": _descarga_json(s, d),
        "puc": [{"codigo": c.codigo, "nombre": c.nombre} for c in cuentas],
        "facturas": [_fila(f, puc) for f in fs],
        "kpis": {"total": len(fs), "pendientes": sum(f.estado == "supervisor" for f in fs),
                 "valor_total": str(sum((f.total for f in fs), Decimal(0)))},
    }


class Asignacion(BaseModel):
    cuenta_codigo: str


@router.post("/facturas/{factura_id}/asignar")
def asignar(factura_id: int, body: Asignacion, s: Session = Depends(get_session)):
    f = s.get(Factura, factura_id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    if f.estado in ("subida",):
        raise HTTPException(409, "La factura ya se subió a Siigo")
    try:
        regla = classifier.asignar_supervisor(s, f, body.cuenta_codigo)
    except ValueError as e:
        raise HTTPException(422, str(e))
    s.commit()
    return {"ok": True, "regla": {"id": regla.id, "coincidencias": regla.coincidencias, "confirmada": regla.confirmada}}


@router.post("/descargas/{descarga_id}/subir")
def subir(descarga_id: int, s: Session = Depends(get_session)):
    d = _descarga_o_404(s, descarga_id)
    pendientes = s.exec(select(Factura).where(Factura.descarga_id == d.id, Factura.estado == "supervisor")).first()
    if pendientes:
        raise HTTPException(409, "Hay facturas pendientes del supervisor")
    if d.estado not in ("revision", "subida"):
        raise HTTPException(409, f"La descarga no está lista para subir (estado: {d.estado})")
    try:
        jobs.lanzar(d.id, "subida", siigo.subir)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}
