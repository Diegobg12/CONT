import os
import time

import pytest

# Antes de importar la app: modo demo instantáneo y BD temporal.
os.environ.update(DEMO_MODE="true", DRY_RUN="true", DEMO_DELAY_FACTOR="0", DEMO_SIMULAR_PAUSA="false")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app import db
    from app.config import get_settings

    get_settings.cache_clear()
    db.set_engine(None)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
    db.set_engine(None)


def esperar(client, descarga_id: int, tipo: str, timeout: float = 10) -> dict:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        d = client.get(f"/api/descargas/{descarga_id}").json()
        j = d[f"job_{tipo}"]
        if j and j["terminado"]:
            return d
        time.sleep(0.05)
    raise TimeoutError(tipo)
