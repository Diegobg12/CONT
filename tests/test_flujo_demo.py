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


# ---------- Plan B (subida manual de Excel + ZIP) ----------

def _zip_fixtures() -> bytes:
    import io, zipfile
    from pathlib import Path
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for p in sorted((Path(__file__).resolve().parent.parent / "fixtures").glob("*.xml")):
            z.writestr(p.name, p.read_bytes())
        z.writestr("roto.xml", b"<no")
    return buf.getvalue()


def _excel_con_faltante() -> bytes:
    import io
    from pathlib import Path
    from openpyxl import load_workbook
    wb = load_workbook(Path(__file__).resolve().parent.parent / "fixtures" / "listado_demo.xlsx")
    ws = wb.active
    fila = [c.value for c in ws[2]]
    fila[1] = "f" * 96  # CUFE que no vino en los ZIP
    ws.append(fila)
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def test_plan_b_con_faltantes_y_duplicados(client):
    d = _nueva(client)
    archivos = [("archivos", ("dian.zip", _zip_fixtures(), "application/zip"))]
    r = client.post(f"/api/descargas/{d}/plan-b", files=archivos + [
        ("listado", ("listado.xlsx", _excel_con_faltante(), "application/vnd.ms-excel"))])
    assert r.status_code == 200, r.text
    est = esperar(client, d, "descarga")
    assert est["estado"] == "revision" and est["origen"] == "plan_b" and est["total"] == 12
    assert len(est["faltantes"]) == 1 and est["faltantes"][0]["cufe"] == "f" * 96
    assert [x["archivo"] for x in est["rechazadas"]] == ["dian.zip/roto.xml"]
    assert est["listado"]["en_listado"] == 13

    # Los mismos ZIP en otra descarga del mismo cliente: todo CUFE repetido
    d2 = _nueva(client)
    client.post(f"/api/descargas/{d2}/plan-b", files=archivos)
    est2 = esperar(client, d2, "descarga")
    assert est2["total"] == 0
    assert sum("repetido" in x["motivo"] for x in est2["rechazadas"]) == 12
