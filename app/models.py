"""Modelo de datos. El token de la DIAN NUNCA se guarda aquí."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def ahora() -> datetime:
    return datetime.now()


class Cliente(SQLModel, table=True):
    __tablename__ = "clientes"
    id: Optional[int] = Field(default=None, primary_key=True)
    nit: str = Field(index=True, unique=True)  # sin puntos ni DV
    dv: str
    razon_social: str
    email_rut: str  # se muestra enmascarado
    actividad: str = ""
    notas_contador: str = ""
    programa: str = "Siigo Nube"


class CuentaPUC(SQLModel, table=True):
    __tablename__ = "plan_cuentas"
    __table_args__ = (UniqueConstraint("cliente_id", "codigo"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    cliente_id: int = Field(foreign_key="clientes.id", index=True)
    codigo: str
    nombre: str
    tipo: str  # gasto | costo | inventario | activo | servicio
    activa: bool = True


class Descarga(SQLModel, table=True):
    __tablename__ = "descargas"
    id: Optional[int] = Field(default=None, primary_key=True)
    cliente_id: int = Field(foreign_key="clientes.id", index=True)
    fecha_ini: date
    fecha_fin: date
    # creada | descargando | pausada | revision | subiendo | subida | error
    estado: str = "creada"
    origen: str = "robot"  # robot | plan_b | demo
    total: int = 0
    faltantes: list = Field(default_factory=list, sa_column=Column(JSON))
    error: Optional[str] = None
    resumen_subida: dict = Field(default_factory=dict, sa_column=Column(JSON))
    creada_en: datetime = Field(default_factory=ahora)
    subida_en: Optional[datetime] = None


class Factura(SQLModel, table=True):
    __tablename__ = "facturas"
    __table_args__ = (UniqueConstraint("cliente_id", "cufe"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    descarga_id: int = Field(foreign_key="descargas.id", index=True)
    cliente_id: int = Field(foreign_key="clientes.id", index=True)
    cufe: str
    numero: str
    fecha: date
    proveedor_nit: str = Field(index=True)
    proveedor_dv: str = ""
    proveedor_nombre: str
    comprador_nit: str = ""
    descripcion: str = ""
    lineas: list = Field(default_factory=list, sa_column=Column(JSON))
    subtotal: Decimal = Field(default=Decimal(0), max_digits=16, decimal_places=2)
    iva: Decimal = Field(default=Decimal(0), max_digits=16, decimal_places=2)
    retenciones: Decimal = Field(default=Decimal(0), max_digits=16, decimal_places=2)
    total: Decimal = Field(default=Decimal(0), max_digits=16, decimal_places=2)
    # Clasificación
    tipo: Optional[str] = None
    cuenta_codigo: Optional[str] = None
    centro_costo: Optional[str] = None
    origen: Optional[str] = None  # regla | ia | supervisor
    confianza: Optional[float] = None
    sugerencias: list = Field(default_factory=list, sa_column=Column(JSON))  # [{codigo, confianza}, ...]
    explicacion: str = ""
    regla_id: Optional[int] = Field(default=None, foreign_key="reglas_proveedor.id")
    respuesta_ia: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # leida | clasificada | supervisor | aprobada | subida | error_siigo
    estado: str = "leida"
    siigo_id: Optional[str] = None
    error: Optional[str] = None


class ReglaProveedor(SQLModel, table=True):
    __tablename__ = "reglas_proveedor"
    __table_args__ = (UniqueConstraint("cliente_id", "proveedor_nit"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    cliente_id: int = Field(foreign_key="clientes.id", index=True)
    proveedor_nit: str
    tipo: str
    cuenta_codigo: str
    centro_costo: Optional[str] = None
    coincidencias: int = 1
    confirmada: bool = False  # se confirma tras 2 coincidencias
    creada_en: datetime = Field(default_factory=ahora)
    actualizada_en: datetime = Field(default_factory=ahora)


class Correccion(SQLModel, table=True):
    __tablename__ = "correcciones"
    id: Optional[int] = Field(default=None, primary_key=True)
    factura_id: int = Field(foreign_key="facturas.id", index=True)
    cliente_id: int = Field(foreign_key="clientes.id", index=True)
    sugerencia: Optional[str] = None
    cuenta_elegida: str
    usuario: str = "supervisor"
    creada_en: datetime = Field(default_factory=ahora)
