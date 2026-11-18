from decimal import Decimal
from pathlib import Path

from app.demo_data import COMPRADOR_DEMO
from app.services.nit import calcular_dv
from app.services.xml_reader import leer_ruta

FIXTURES = sorted((Path(__file__).resolve().parent.parent / "fixtures").glob("*.xml"))


def test_hay_12_fixtures():
    assert len(FIXTURES) == 12


def test_fixtures_se_leen_y_cuadran():
    cufes = set()
    for ruta in FIXTURES:
        (f,) = leer_ruta(ruta)
        assert len(f.cufe) == 96
        assert f.comprador_nit == COMPRADOR_DEMO["nit"]
        assert f.proveedor_dv == calcular_dv(f.proveedor_nit)
        assert f.lineas and f.proveedor_nombre
        assert abs(f.subtotal + f.iva - f.total) <= Decimal("1")
        assert sum(l.valor for l in f.lineas) == f.subtotal
        cufes.add(f.cufe)
    assert len(cufes) == len(FIXTURES)


def test_dv_nit_conocido():
    assert calcular_dv("860002400") == "2"  # ejemplo verificable a mano
