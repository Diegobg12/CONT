"""Robot ASISTIDO de la DIAN con Playwright.

Reglas (no negociables):
- Navegador VISIBLE en uso real. `headless=True` existe SOLO para los tests contra la DIAN simulada local.
- Si la DIAN pide verificación humana o bloquea la solicitud, el robot se PAUSA y espera a que la
  persona la resuelva en la ventana. No resuelve captchas, no rota IPs, no se oculta.
- Ritmo humano: una acción a la vez, pausas entre descargas, reintentos limitados.
- El enlace del token solo vive en memoria y se borra de cualquier mensaje de error.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from app.services import dian_selectores as SEL
from app.services.jobs import Job

log = logging.getLogger("robot")


class RobotError(RuntimeError):
    pass


class EnlaceInvalido(ValueError):
    pass


def validar_enlace(url: str, hosts=SEL.HOSTS_DIAN, exigir_https: bool = True) -> str:
    """Comprueba que el token sea un enlace de la DIAN. El mensaje de error nunca incluye el enlace."""
    url = (url or "").strip()
    partes = urlsplit(url)
    if partes.scheme not in (("https",) if exigir_https else ("https", "http")) or partes.hostname not in hosts:
        raise EnlaceInvalido(
            "Pega el enlace completo que llegó al correo (empieza por https://catalogo-vpfe.dian.gov.co/…)")
    return url


@dataclass
class Opciones:
    headless: bool = False  # SOLO tests. En uso real siempre visible.
    hosts: tuple[str, ...] = SEL.HOSTS_DIAN
    exigir_https: bool = True
    timeout_ms: int = 30_000  # por acción
    pausa_entre_descargas: tuple[float, float] = (1.5, 3.0)  # ritmo humano
    reintentos: int = 2
    espera_verificacion_s: int = 15 * 60  # cuánto esperar a que la persona resuelva la verificación
    slow_mo_ms: int = 150


class RobotDIAN:
    def __init__(self, job: Job, token_url: str, fecha_ini, fecha_fin, carpeta: Path,
                 al_pausar: Callable[[bool], None] | None = None, opciones: Opciones | None = None):
        self.job = job
        self.op = opciones or Opciones()
        self._token = validar_enlace(token_url, self.op.hosts, self.op.exigir_https)
        p = urlsplit(self._token)
        self.origen = f"{p.scheme}://{p.netloc}"
        self.ini, self.fin = fecha_ini, fecha_fin
        self.carpeta = carpeta
        self.al_pausar = al_pausar or (lambda _: None)

    # ---------- utilidades ----------

    def redactar(self, texto: str) -> str:
        """Quita el token de cualquier texto (los errores de Playwright incluyen URLs)."""
        t = str(texto)
        if self._token:
            t = t.replace(self._token, "[enlace del token]")
            consulta = urlsplit(self._token).query
            if consulta:
                t = t.replace(consulta, "[token]")
        return t

    def _ritmo(self) -> None:
        a, b = self.op.pausa_entre_descargas
        if b > 0:
            time.sleep(random.uniform(a, b))

    def _primero(self, page, clave: str, timeout_ms: int | None = None):
        """Devuelve el primer selector visible de la lista `clave`, o error claro para actualizar selectores."""
        total = timeout_ms if timeout_ms is not None else self.op.timeout_ms
        fin = time.monotonic() + total / 1000
        while True:
            for sel in SEL.SELECTORES[clave]:
                loc = page.locator(sel).first
                try:
                    if loc.count() and loc.is_visible():
                        return loc
                except Exception:
                    pass
            self._verificar(page)
            if time.monotonic() > fin:
                raise RobotError(
                    f"No encontré «{clave}» en la página de la DIAN. Si la DIAN cambió su página, "
                    f"actualiza app/services/dian_selectores.py con la grabación de playwright codegen.")
            time.sleep(0.3)

    def _hay_verificacion(self, page) -> bool:
        try:
            texto = (page.locator("body").inner_text(timeout=2000) or "").lower()
        except Exception:
            return False
        if any(t in texto for t in SEL.TEXTOS_VERIFICACION):
            return True
        return any(page.locator(s).count() for s in SEL.SELECTORES_VERIFICACION)

    def _verificar(self, page) -> None:
        """Si la DIAN pide verificación humana: PAUSA hasta que la persona la resuelva en la ventana."""
        if not self._hay_verificacion(page):
            return
        log.info("La DIAN pidió verificación humana: robot en pausa")
        self.job.pausa = True
        self.al_pausar(True)
        try:
            page.bring_to_front()
        except Exception:
            pass
        limite = time.monotonic() + self.op.espera_verificacion_s
        try:
            while self._hay_verificacion(page):
                if time.monotonic() > limite:
                    raise RobotError("Nadie completó la verificación de la DIAN a tiempo. Vuelve a intentar o usa el plan B.")
                time.sleep(2)
        finally:
            self.job.pausa = False
            self.al_pausar(False)
        log.info("Verificación completada: el robot continúa")
        page.wait_for_load_state("domcontentloaded")

    def _token_invalido(self, page) -> bool:
        try:
            texto = page.locator("body").inner_text(timeout=2000).lower()
        except Exception:
            return False
        return any(t in texto for t in SEL.TEXTOS_TOKEN_INVALIDO)

    # ---------- pasos ----------

    def _iniciar_sesion(self, page) -> None:
        self.job.etapa, self.job.mensaje = 0, "Abriendo la DIAN con el token del cliente"
        page.goto(self._token, wait_until="domcontentloaded")
        self._verificar(page)
        if self._token_invalido(page):
            raise RobotError("La DIAN dice que el token no es válido o ya venció. Solicita uno nuevo.")
        self._primero(page, "sesion_ok")
        self.job.mensaje = "Con el token del cliente"

    def _buscar(self, page) -> None:
        self.job.etapa, self.job.mensaje = 1, "Buscando documentos recibidos"
        page.goto(self.origen + SEL.RUTA_RECIBIDOS, wait_until="domcontentloaded")
        self._verificar(page)
        rango = SEL.FORMATO_RANGO.format(ini=self.ini, fin=self.fin)
        campo = self._primero(page, "rango_fechas")
        # El campo suele ser de solo lectura (selector de calendario): se escribe el valor como lo haría el calendario.
        campo.evaluate(
            "(el, v) => { el.removeAttribute('readonly'); el.value = v;"
            " el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }",
            rango)
        self._primero(page, "boton_buscar").click()
        page.wait_for_load_state("domcontentloaded")
        self._verificar(page)
        self._primero(page, "tabla")

    def _exportar_listado(self, page) -> bytes | None:
        try:
            boton = self._primero(page, "exportar_excel", timeout_ms=5000)
            with page.expect_download(timeout=self.op.timeout_ms) as info:
                boton.click()
            ruta = self.carpeta / "listado.xlsx"
            info.value.save_as(ruta)
            return ruta.read_bytes()
        except Exception as e:  # el listado ayuda pero no es obligatorio
            log.warning("No se pudo exportar el listado: %s", self.redactar(e))
            return None

    def _boton_descarga(self, fila):
        for sel in SEL.SELECTORES["descargar_fila"]:
            b = fila.locator(sel).first
            if b.count():
                return b
        return None

    def _descargar_documentos(self, page) -> list[tuple[str, bytes]]:
        self.job.etapa, self.job.n = 2, 0
        archivos: list[tuple[str, bytes]] = []
        pagina = 1
        while True:
            filas = page.locator(SEL.SELECTORES["filas"][0])
            if not filas.count():
                filas = page.locator(SEL.SELECTORES["filas"][1])
            con_boton = [i for i in range(filas.count()) if self._boton_descarga(filas.nth(i)) is not None]
            self.job.total = len(archivos) + len(con_boton)
            for i in con_boton:
                boton = self._boton_descarga(filas.nth(i))
                for intento in range(self.op.reintentos + 1):
                    try:
                        with page.expect_download(timeout=self.op.timeout_ms) as info:
                            boton.click()
                        dl = info.value
                        nombre = f"p{pagina:02d}_{i + 1:03d}_{dl.suggested_filename or 'documento.zip'}"
                        ruta = self.carpeta / nombre
                        dl.save_as(ruta)
                        archivos.append((nombre, ruta.read_bytes()))
                        break
                    except Exception as e:
                        self._verificar(page)
                        if intento == self.op.reintentos:
                            raise RobotError(f"No se pudo descargar el documento {len(archivos) + 1}: "
                                             f"{self.redactar(type(e).__name__)}") from None
                        time.sleep(2 * (intento + 1))
                self.job.n = len(archivos)
                self.job.mensaje = f"{self.job.n} de {self.job.total} · con su XML"
                self._ritmo()
                self._verificar(page)
            siguiente = None
            for sel in SEL.SELECTORES["siguiente_pagina"]:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    siguiente = loc
                    break
            if siguiente is None:
                return archivos
            siguiente.click()
            page.wait_for_load_state("domcontentloaded")
            self._verificar(page)
            pagina += 1

    def correr(self) -> tuple[list[tuple[str, bytes]], bytes | None]:
        from playwright.sync_api import Error as PWError
        from playwright.sync_api import sync_playwright

        self.carpeta.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as p:
                navegador = p.chromium.launch(headless=self.op.headless, slow_mo=self.op.slow_mo_ms)
                contexto = navegador.new_context(accept_downloads=True, locale="es-CO")
                page = contexto.new_page()
                page.set_default_timeout(self.op.timeout_ms)
                try:
                    self._iniciar_sesion(page)
                    self._buscar(page)
                    listado = self._exportar_listado(page)
                    archivos = self._descargar_documentos(page)
                    return archivos, listado
                finally:
                    contexto.close()
                    navegador.close()
        except RobotError as e:
            raise RobotError(self.redactar(e)) from None
        except PWError as e:
            raise RobotError("Falló el navegador del robot: " + self.redactar(str(e).splitlines()[0])) from None
        finally:
            self._token = ""  # el token no sobrevive a la sesión
