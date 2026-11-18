from tests.conftest import esperar

TOKEN = "https://catalogo-vpfe.dian.gov.co/User/AuthToken?pk=SECRETO-DE-PRUEBA"


def _nueva(client, cliente_id=None):
    cs = client.get("/api/clientes").json()
    assert len(cs) == 3
    cid = cliente_id or next(c["id"] for c in cs if c["razon_social"].startswith("Distribuidora Andina"))
    r = client.post("/api/descargas", json={"cliente_id": cid, "fecha_ini": "2026-10-01", "fecha_fin": "2026-10-31"})
    assert r.status_code == 200
    return r.json()["id"]


def test_flujo_completo_demo(client):
    d = _nueva(client)
    assert client.post(f"/api/descargas/{d}/iniciar", json={"token": TOKEN}).status_code == 200
    estado = esperar(client, d, "descarga")
    assert estado["estado"] == "revision" and estado["total"] == 12
    assert "SECRETO" not in str(estado)

    datos = client.get(f"/api/descargas/{d}/facturas").json()
    pend = [f for f in datos["facturas"] if f["estado"] == "supervisor"]
    assert len(pend) == 3  # exactamente 3 para el supervisor
    origenes = {f["origen"] for f in datos["facturas"] if f["estado"] != "supervisor"}
    assert origenes == {"regla", "ia"}

    # No se puede subir con pendientes
    assert client.post(f"/api/descargas/{d}/subir").status_code == 409

    for f in pend:
        r = client.post(f"/api/facturas/{f['id']}/asignar", json={"cuenta_codigo": f["sugerencias"][0]["codigo"]})
        assert r.status_code == 200
        assert r.json()["regla"]["confirmada"] is False  # 1 coincidencia

    assert client.post(f"/api/descargas/{d}/subir").status_code == 200
    final = esperar(client, d, "subida")
    r = final["resumen_subida"]
    assert final["estado"] == "subida"
    assert r["comprobantes"] == 12 and r["fallidas"] == 0 and r["reglas_nuevas"] == 3


def test_regla_se_confirma_tras_2_coincidencias(client):
    for vez in (1, 2):
        d = _nueva(client)
        client.post(f"/api/descargas/{d}/iniciar", json={"token": "x"})
        esperar(client, d, "descarga")
        pend = [f for f in client.get(f"/api/descargas/{d}/facturas").json()["facturas"] if f["estado"] == "supervisor"]
        assert len(pend) == 3
        r = client.post(f"/api/facturas/{pend[0]['id']}/asignar", json={"cuenta_codigo": "5145"}).json()
        assert r["regla"]["coincidencias"] == vez
    assert r["regla"]["confirmada"] is True


def test_cuenta_fuera_del_plan_se_rechaza(client):
    d = _nueva(client)
    client.post(f"/api/descargas/{d}/iniciar", json={"token": "x"})
    esperar(client, d, "descarga")
    f = client.get(f"/api/descargas/{d}/facturas").json()["facturas"][0]
    assert client.post(f"/api/facturas/{f['id']}/asignar", json={"cuenta_codigo": "9999"}).status_code == 422


def test_token_no_se_refleja_en_errores(client):
    d = _nueva(client)
    r = client.post(f"/api/descargas/{d}/iniciar", json={"token": 12345, "otro": TOKEN})
    assert "SECRETO" not in r.text
    r = client.post(f"/api/descargas/{d}/iniciar", json=["SECRETO"])
    assert r.status_code == 422 and "SECRETO" not in r.text


def test_rango_invalido(client):
    cid = client.get("/api/clientes").json()[0]["id"]
    r = client.post("/api/descargas", json={"cliente_id": cid, "fecha_ini": "2026-10-31", "fecha_fin": "2026-10-01"})
    assert r.status_code == 422
