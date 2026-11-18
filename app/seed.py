"""Semilla: 3 clientes de la demo, PUC básico y reglas confirmadas de algunos proveedores."""
from sqlmodel import Session, select

from app.demo_data import CLIENTES, PROVEEDORES, PUC
from app.models import Cliente, CuentaPUC, ReglaProveedor
from app.services.nit import calcular_dv


def sembrar(session: Session) -> None:
    if session.exec(select(Cliente)).first():
        return
    for c in CLIENTES:
        cli = Cliente(dv=calcular_dv(c["nit"]), **c)
        session.add(cli)
        session.flush()
        for codigo, nombre, tipo in PUC:
            session.add(CuentaPUC(cliente_id=cli.id, codigo=codigo, nombre=nombre, tipo=tipo))
    session.flush()

    # Reglas ya confirmadas para Distribuidora Andina (historial previo simulado).
    andina = session.exec(select(Cliente).where(Cliente.nit == CLIENTES[0]["nit"])).one()
    tipos = {codigo: tipo for codigo, _, tipo in PUC}
    for p in PROVEEDORES:
        if p["clasif"][0] == "regla":
            cuenta = p["clasif"][1]
            session.add(ReglaProveedor(cliente_id=andina.id, proveedor_nit=p["nit"], tipo=tipos[cuenta],
                                       cuenta_codigo=cuenta, coincidencias=3, confirmada=True))
    session.commit()
