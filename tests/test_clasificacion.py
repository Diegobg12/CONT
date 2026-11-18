"""Fase 4: reglas → IA (Haiku simulado con un cliente falso) → supervisor. Sin llamadas reales a la API."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_engine
from app.models import Cliente, Descarga, Factura, ReglaProveedor
from app.services import classifier, ia_haiku
from tests.conftest import esperar


class _FakeMessages:
    def __init__(self, respuesta=None, error=None):
        self.respuesta, self.error, self.llamadas = respuesta, error, []

    def parse(self, **kw):
        self.llamadas.append(kw)
        if self.error:
            raise self.error
        return self.respuesta


def _ia(monkeypatch, cuenta="5135", conf=0.93, segunda="5195", conf2=0.04, error=None):
    salida = ia_haiku.SugerenciaIA(tipo="servicio", cuenta=cuenta, centro_costo="", confianza=conf,
                                   explicacion="Servicio contratado.", segunda_cuenta=segunda, segunda_confianza=conf2)
    fake = _FakeMessages(SimpleNamespace(stop_reason="end_turn", parsed_output=salida, _request_id="req_test"), error)
    monkeypatch.setattr(ia_haiku, "_cliente", lambda settings: SimpleNamespace(messages=fake))
    st = get_settings()
    monkeypatch.setattr(st, "demo_mode", False)
    monkeypatch.setattr(st, "anthropic_api_key", "sk-ant-test")
    return fake


def _factura(s, cliente_nit="900456789", proveedor="901000001", desc="Servicio de vigilancia octubre", estado="leida",
             cuenta=None, cufe=None):
    c = s.exec(select(Cliente).where(Cliente.nit == cliente_nit)).one()
    d = Descarga(cliente_id=c.id, fecha_ini=date(2026, 10, 1), fecha_fin=date(2026, 10, 31))
    s.add(d); s.flush()
    f = Factura(descarga_id=d.id, cliente_id=c.id, cufe=cufe or f"cufe-{proveedor}-{desc}"[:90], numero="X1",
                fecha=date(2026, 10, 5), proveedor_nit=proveedor, proveedor_nombre=f"Proveedor {proveedor}",
                descripcion=desc, lineas=[{"descripcion": desc, "cantidad": "1", "valor": "1000000"}],
                subtotal=Decimal(1000000), iva=Decimal(190000), total=Decimal(1190000), estado=estado,
                cuenta_codigo=cuenta, origen="supervisor" if cuenta else None)
    s.add(f); s.flush()
    return f


# ---------- umbral ----------

@pytest.mark.parametrize("c1,c2,esperado", [
    (0.96, 0.03, False),  # segura y con margen
    (0.79, 0.05, True),   # bajo el umbral 0.80
    (0.85, 0.72, True),   # menos de 15 puntos entre opciones
    (0.80, 0.65, False),  # justo en el límite: pasa
])
def test_umbral(c1, c2, esperado):
    assert classifier.necesita_supervisor(c1, c2, get_settings()) is esperado


# ---------- reglas ----------

def test_regla_confirmada_gana_sin_ia(client, monkeypatch):
    fake = _ia(monkeypatch)
    with Session(get_engine()) as s:
        f = _factura(s, proveedor="900112233")  # Empaques Andinos: regla confirmada en la semilla
        classifier.clasificar(s, f, get_settings())
        assert (f.origen, f.cuenta_codigo, f.estado) == ("regla", "1435", "clasificada") and f.regla_id
    assert fake.llamadas == []


def test_regla_no_confirmada_no_se_aplica(client, monkeypatch):
    _ia(monkeypatch)
    with Session(get_engine()) as s:
        f0 = _factura(s, proveedor="901777777", desc="Asesoría", estado="supervisor")
        classifier.asignar_supervisor(s, f0, "5110")  # 1 coincidencia: no confirmada
        f = _factura(s, proveedor="901777777", desc="Asesoría noviembre")
        classifier.clasificar(s, f, get_settings())
        assert f.origen == "ia"


def test_reglas_no_se_mezclan_entre_clientes(client, monkeypatch):
    _ia(monkeypatch)
    with Session(get_engine()) as s:
        f = _factura(s, cliente_nit="901223004", proveedor="900112233")  # regla existe solo para Andina
        classifier.clasificar(s, f, get_settings())
        assert f.origen == "ia"


# ---------- IA (Haiku) ----------

def test_ia_segura_clasifica(client, monkeypatch):
    fake = _ia(monkeypatch)
    with Session(get_engine()) as s:
        f = _factura(s)
        classifier.clasificar(s, f, get_settings())
        assert (f.origen, f.cuenta_codigo, f.estado, f.tipo) == ("ia", "5135", "clasificada", "servicio")
        assert f.respuesta_ia["request_id"] == "req_test" and f.respuesta_ia["modelo"] == "claude-haiku-5-5"
    kw = fake.llamadas[0]
    assert kw["model"] == "claude-haiku-5-5" and kw["output_format"] is ia_haiku.SugerenciaIA


def test_ia_dudosa_va_al_supervisor_con_dos_sugerencias(client, monkeypatch):
    _ia(monkeypatch, cuenta="5145", conf=0.52, segunda="1520", conf2=0.38)
    with Session(get_engine()) as s:
        f = _factura(s)
        classifier.clasificar(s, f, get_settings())
        assert f.estado == "supervisor" and f.cuenta_codigo is None
        assert [x["codigo"] for x in f.sugerencias] == ["5145", "1520"]


def test_ia_cuenta_inventada_va_al_supervisor(client, monkeypatch):
    _ia(monkeypatch, cuenta="9999")
    with Session(get_engine()) as s:
        f = _factura(s)
        classifier.clasificar(s, f, get_settings())
        assert f.estado == "supervisor" and "no está en el plan" in f.explicacion


def test_ia_caida_va_al_supervisor(client, monkeypatch):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    _ia(monkeypatch, error=anthropic.APIConnectionError(request=req))
    with Session(get_engine()) as s:
        f = _factura(s)
        classifier.clasificar(s, f, get_settings())
        assert f.estado == "supervisor" and "Sin conexión" in f.explicacion


def test_sin_llave_va_al_supervisor(client, monkeypatch):
    st = get_settings()
    monkeypatch.setattr(st, "demo_mode", False)
    monkeypatch.setattr(st, "anthropic_api_key", "")
    with Session(get_engine()) as s:
        f = _factura(s)
        classifier.clasificar(s, f, st)
        assert f.estado == "supervisor" and "ANTHROPIC_API_KEY" in f.explicacion


def test_contexto_solo_del_mismo_cliente(client, monkeypatch):
    with Session(get_engine()) as s:
        _factura(s, proveedor="901000001", desc="Servicio de vigilancia septiembre", estado="aprobada", cuenta="5135", cufe="a1")
        _factura(s, cliente_nit="901223004", proveedor="901000001", desc="Servicio de vigilancia secreto",
                 estado="aprobada", cuenta="5195", cufe="b1")
        f = _factura(s, desc="Servicio de vigilancia octubre", cufe="a2")
        sistema, mensaje = ia_haiku.construir_contexto(s, f)
        assert "Distribuidora Andina" in sistema and "5240 Publicidad" in sistema
        assert "Café Montaña" not in sistema + mensaje and "secreto" not in mensaje
        assert "vigilancia septiembre" in mensaje and "→ 5135" in mensaje


def test_ejemplos_max_5_y_mismo_proveedor_primero(client):
    with Session(get_engine()) as s:
        for i in range(7):
            _factura(s, proveedor=f"80000000{i}", desc=f"Servicio vigilancia {i}", estado="aprobada", cuenta="5135", cufe=f"o{i}")
        _factura(s, proveedor="901000001", desc="Otra cosa", estado="aprobada", cuenta="5195", cufe="p1")
        f = _factura(s, desc="Servicio vigilancia nuevo", cufe="n1")
        ej = ia_haiku.ejemplos_parecidos(s, f)
        assert len(ej) == 5 and ej[0].proveedor_nit == "901000001"


# ---------- reiniciar demo ----------

def test_reiniciar_demo(client):
    from tests.test_flujo_demo import _nueva
    for _ in range(2):  # dos rondas: las 3 reglas del supervisor quedan confirmadas
        d = _nueva(client)
        client.post(f"/api/descargas/{d}/iniciar", json={"token": "x"})
        esperar(client, d, "descarga")
        for f in client.get(f"/api/descargas/{d}/facturas").json()["facturas"]:
            if f["estado"] == "supervisor":
                client.post(f"/api/facturas/{f['id']}/asignar", json={"cuenta_codigo": f["sugerencias"][0]["codigo"]})
    assert client.post("/api/demo/reiniciar").json() == {"ok": True}
    with Session(get_engine()) as s:
        assert len(s.exec(select(ReglaProveedor)).all()) == 4  # solo las de la semilla
        assert s.exec(select(Factura)).all() == []
    d = _nueva(client)
    client.post(f"/api/descargas/{d}/iniciar", json={"token": "x"})
    esperar(client, d, "descarga")
    pend = [f for f in client.get(f"/api/descargas/{d}/facturas").json()["facturas"] if f["estado"] == "supervisor"]
    assert len(pend) == 3  # la demo vuelve a empezar igual


def test_reiniciar_solo_en_demo(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert client.post("/api/demo/reiniciar").status_code == 403
