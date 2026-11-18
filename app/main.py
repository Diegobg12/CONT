"""Aplicación FastAPI: API en /api y las 5 pantallas como archivos estáticos."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.api.rutas import router
from app.config import get_settings
from app.db import get_engine, init_db
from app.seed import sembrar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(get_engine()) as s:
        sembrar(s)
    st = get_settings()
    logging.getLogger("app").info("Listo · DEMO_MODE=%s · DRY_RUN=%s", st.demo_mode, st.dry_run)
    yield


app = FastAPI(title="Facturas DIAN → Siigo (beta)", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validacion(request: Request, exc: RequestValidationError):
    # FastAPI devuelve por defecto el valor recibido: lo quitamos para no reflejar nunca el token.
    errores = [{"campo": ".".join(str(x) for x in e.get("loc", [])), "mensaje": e.get("msg", "")} for e in exc.errors()]
    return JSONResponse({"detail": errores}, status_code=422)


app.include_router(router)


@app.get("/", include_in_schema=False)
def inicio():
    return RedirectResponse("/1-cliente-fechas.html")


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
