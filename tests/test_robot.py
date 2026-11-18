"""Robot DIAN contra la DIAN SIMULADA local (tests/mock_dian.py). Nunca toca el portal real.

En estos tests el navegador va oculto (headless) solo para poder correrlos sin ventana;
en uso real el robot siempre abre el navegador visible.
"""
from datetime import date

import pytest

from app.services.dian_robot import EnlaceInvalido, Opciones, RobotDIAN, RobotError, validar_enlace
from app.services.jobs import Job
from tests.mock_dian import DianSimulada

pytest.importorskip("playwright")


def _opciones(**kw):
    base = dict(headless=True, hosts=("127.0.0.1",), exigir_https=False, timeout_ms=8000,
                pausa_entre_descargas=(0, 0), espera_verificacion_s=20, slow_mo_ms=0)
    base.update(kw)
    return Opciones(**base)


def _robot(dian, tmp_path, token="BUENO", pausas=None, **kw):
    job = Job(descarga_id=1, tipo="descarga")
    al_pausar = (lambda p: pausas.append(p)) if pausas is not None else None
    r = RobotDIAN(job, dian.enlace(token), date(2026, 10, 1), date(2026, 10, 31), tmp_path, al_pausar, _opciones(**kw))
    return r, job


def test_descarga_todo_con_paginacion(tmp_path):
    with DianSimulada() as dian:
        robot, job = _robot(dian, tmp_path)
        archivos, listado = robot.correr()
    assert len(archivos) == 12  # 3 páginas de 5 + 5 + 2
    assert all(n.endswith(".zip") for n, _ in archivos)
    assert listado and listado[:2] == b"PK"
    assert job.n == 12 and job.total == 12 and job.pausa is False


def test_pausa_ante_verificacion_humana_y_continua(tmp_path):
    pausas = []
    with DianSimulada() as dian:
        robot, job = _robot(dian, tmp_path, token="CAPTCHA", pausas=pausas)
        archivos, _ = robot.correr()
    assert pausas == [True, False]  # se pausó y luego siguió solo
    assert len(archivos) == 12


def test_verificacion_sin_resolver_termina_con_error_claro(tmp_path, monkeypatch):
    import app.services.dian_robot as r
    monkeypatch.setattr(r.RobotDIAN, "_hay_verificacion", lambda self, page: True)
    with DianSimulada() as dian:
        robot, job = _robot(dian, tmp_path, espera_verificacion_s=1)
        with pytest.raises(RobotError, match="verificación"):
            robot.correr()
    assert job.pausa is False


def test_token_vencido(tmp_path):
    with DianSimulada() as dian:
        robot, _ = _robot(dian, tmp_path, token="VENCIDO")
        with pytest.raises(RobotError, match="no es válido o ya venció"):
            robot.correr()


def test_selector_que_no_existe_da_instruccion_y_no_filtra_token(tmp_path, monkeypatch):
    import app.services.dian_selectores as S
    monkeypatch.setitem(S.SELECTORES, "boton_buscar", ["#no-existe"])
    with DianSimulada() as dian:
        robot, _ = _robot(dian, tmp_path, token="SECRETO123", timeout_ms=1500)
        with pytest.raises(RobotError) as e:
            robot.correr()
    msg = str(e.value)
    assert "boton_buscar" in msg and "dian_selectores.py" in msg
    assert "SECRETO123" not in msg


def test_redacta_token_en_errores(tmp_path):
    with DianSimulada() as dian:
        robot, _ = _robot(dian, tmp_path, token="SECRETO123")
        assert "SECRETO123" not in robot.redactar(f"Timeout navegando a {dian.enlace('SECRETO123')}")


@pytest.mark.parametrize("url", [
    "", "hola", "http://catalogo-vpfe.dian.gov.co/User/AuthToken?x=1",
    "https://dian.gov.co.evil.com/User/AuthToken", "https://evil.com/?u=catalogo-vpfe.dian.gov.co",
])
def test_enlace_invalido(url):
    with pytest.raises(EnlaceInvalido) as e:
        validar_enlace(url)
    assert url not in str(e.value) or not url


def test_enlace_valido():
    assert validar_enlace(" https://catalogo-vpfe.dian.gov.co/User/AuthToken?pk=1&token=abc ").startswith("https://")


def test_flujo_robot_completo_por_api(client, monkeypatch, tmp_path):
    """El robot real conectado al flujo: descarga → lee → valida → cruza → clasifica. Borra los archivos al final."""
    from app.services import descarga as proc
    from tests.conftest import esperar

    with DianSimulada() as dian:
        original = proc.robot_real
        monkeypatch.setattr(proc, "robot_real", lambda job: original(job, _opciones()))
        monkeypatch.setattr(proc, "ROOT", tmp_path)
        from app.config import get_settings
        monkeypatch.setattr(get_settings(), "demo_mode", False)
        import app.services.dian_robot as r
        monkeypatch.setattr(r, "validar_enlace", lambda url, hosts=None, exigir_https=True: url)
        import app.api.rutas as rutas
        monkeypatch.setattr(rutas, "validar_enlace", lambda url: url)

        cid = client.get("/api/clientes").json()[0]["id"]
        d = client.post("/api/descargas", json={"cliente_id": cid, "fecha_ini": "2026-10-01",
                                                "fecha_fin": "2026-10-31"}).json()["id"]
        assert client.post(f"/api/descargas/{d}/iniciar", json={"token": dian.enlace()}).status_code == 200
        est = esperar(client, d, "descarga", timeout=60)

    assert est["origen"] == "robot" and est["estado"] == "revision", est["error"]
    assert est["total"] == 12 and est["faltantes"] == [] and est["rechazadas"] == []
    assert not (tmp_path / "downloads" / f"descarga_{d}").exists()  # no quedan archivos en disco
