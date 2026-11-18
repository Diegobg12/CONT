"""Estado en memoria de las tareas en curso (descarga DIAN y subida a Siigo).

El token de la DIAN vive SOLO aquí, en memoria, y se borra apenas el robot lo usa.
Nunca se serializa, ni se loguea, ni se devuelve en la API.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger("jobs")


@dataclass
class Job:
    descarga_id: int
    tipo: str  # descarga | subida
    etapa: int = 0  # índice del paso en curso
    n: int = 0
    total: int = 0
    pausa: bool = False
    mensaje: str = ""
    error: str | None = None
    terminado: bool = False
    inicio: float = field(default_factory=time.monotonic)
    _token: str | None = field(default=None, repr=False)

    def tomar_token(self) -> str | None:
        """Entrega el token una sola vez y lo borra de memoria."""
        t, self._token = self._token, None
        return t

    def estado(self) -> dict:
        return {"tipo": self.tipo, "etapa": self.etapa, "n": self.n, "total": self.total, "pausa": self.pausa,
                "mensaje": self.mensaje, "error": self.error, "terminado": self.terminado,
                "segundos": round(time.monotonic() - self.inicio)}


_jobs: dict[tuple[int, str], Job] = {}
_lock = threading.Lock()


def obtener(descarga_id: int, tipo: str) -> Job | None:
    return _jobs.get((descarga_id, tipo))


def en_curso(descarga_id: int, tipo: str) -> bool:
    j = obtener(descarga_id, tipo)
    return bool(j and not j.terminado)


def alguno_en_curso(tipo: str) -> bool:
    """Una empresa a la vez: ¿hay alguna tarea de este tipo corriendo?"""
    return any(j.tipo == tipo and not j.terminado for j in _jobs.values())


def limpiar() -> None:
    """Olvida las tareas terminadas (reinicio de la demo)."""
    with _lock:
        for k in [k for k, j in _jobs.items() if j.terminado]:
            del _jobs[k]


def lanzar(descarga_id: int, tipo: str, objetivo, token: str | None = None) -> Job:
    with _lock:
        if en_curso(descarga_id, tipo):
            raise RuntimeError("Ya hay una tarea en curso para esta descarga")
        job = Job(descarga_id=descarga_id, tipo=tipo, _token=token)
        _jobs[(descarga_id, tipo)] = job

    def correr():
        try:
            objetivo(job)
        except Exception as e:  # el mensaje no debe incluir el token
            log.exception("Fallo en tarea %s de la descarga %s", tipo, descarga_id)
            job.error = f"{type(e).__name__}: {e}"
        finally:
            job.tomar_token()
            job.pausa = False
            job.terminado = True

    threading.Thread(target=correr, daemon=True, name=f"{tipo}-{descarga_id}").start()
    return job
