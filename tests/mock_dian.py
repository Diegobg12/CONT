"""DIAN SIMULADA para probar el robot sin tocar el portal real (solo tests, en 127.0.0.1).

Imita la forma del portal: enlace de token → inicio → documentos recibidos con rango de
fechas, tabla paginada, botón de descarga por fila y exportación a Excel.
Tokens especiales: "VENCIDO" (token inválido) y "CAPTCHA" (pide verificación humana 2 s).
"""
from __future__ import annotations

import io
import threading
import zipfile
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.services.xml_reader import leer_xml

FIX = Path(__file__).resolve().parent.parent / "fixtures"
POR_PAGINA = 5


def _documentos():
    docs = []
    for p in sorted(FIX.glob("*.xml")):
        f = leer_xml(p.read_bytes())
        docs.append({"archivo": p, "fecha": f.fecha, "numero": f.numero, "proveedor": f.proveedor_nombre})
    return docs


class _Handler(BaseHTTPRequestHandler):
    docs = _documentos()
    estado = {"bloqueos": 0}

    def log_message(self, *a):  # silencio
        pass

    def _html(self, cuerpo: str, codigo=200, extra_head=""):
        b = f"<!doctype html><html><head><meta charset='utf-8'>{extra_head}</head><body>{cuerpo}</body></html>".encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _archivo(self, nombre: str, datos: bytes, tipo: str):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Disposition", f'attachment; filename="{nombre}"')
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _redir(self, a: str, cookie: str | None = None):
        self.send_response(302)
        self.send_header("Location", a)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _filtrados(self, q):
        rango = q.get("rango", [""])[0]
        try:
            ini, fin = [datetime.strptime(x.strip(), "%Y/%m/%d").date() for x in rango.split(" - ")]
        except ValueError:
            return None, rango
        return [d for d in self.docs if ini <= d["fecha"] <= fin], rango

    def do_GET(self):
        u = urlsplit(self.path)
        q = parse_qs(u.query)
        logueado = "sesion=1" in (self.headers.get("Cookie") or "")

        if u.path == "/User/AuthToken":
            token = q.get("token", [""])[0]
            if token == "VENCIDO":
                return self._html("<h3>El token ha expirado. Solicite uno nuevo.</h3>")
            if token == "CAPTCHA":
                # Pide verificación; la "persona" la completa a los 2 s (el JS la quita) y entra.
                return self._html(
                    "<div id='challenge-form'><p>Solicitud bloqueada por controles de seguridad</p></div>"
                    "<script>setTimeout(() => { document.cookie = 'sesion=1; path=/'; location.href = '/Home'; }, 2000)</script>")
            return self._redir("/Home", "sesion=1; Path=/")

        if not logueado:
            return self._html("<p>Debe iniciar sesión</p>", 401)

        if u.path == "/Home":
            return self._html("<nav><a href='/Document/Received'>Recibidos</a> <a href='#'>Cerrar sesión</a></nav>")

        if u.path == "/Document/Received":
            docs, rango = self._filtrados(q)
            pagina = int(q.get("p", ["1"])[0])
            form = (f"<input id='dashboard-report-range' readonly value='{escape(rango)}'>"
                    "<button id='buscarDocumentos' onclick=\"location.href='/Document/Received?rango='"
                    "+encodeURIComponent(document.getElementById('dashboard-report-range').value)\">Buscar</button>")
            if docs is None:
                return self._html(form)
            ini = (pagina - 1) * POR_PAGINA
            filas = "".join(
                f"<tr><td>{d['fecha']}</td><td>{escape(d['numero'])}</td><td>{escape(d['proveedor'])}</td>"
                f"<td><button class='download-document' onclick=\"location.href='/Document/Download?id={self.docs.index(d)}'\">"
                f"Descargar</button></td></tr>"
                for d in docs[ini:ini + POR_PAGINA])
            sig = ""
            if ini + POR_PAGINA < len(docs):
                sig = f"<span id='tableDocuments_next'><a href='/Document/Received?rango={escape(rango)}&p={pagina + 1}'>Siguiente</a></span>"
            exportar = f"<a id='exportExcel' href='/Document/Export?rango={escape(rango)}'>Exportar Excel</a>"
            return self._html(f"{form}{exportar}<table id='tableDocuments'><thead><tr><th>Fecha</th></tr></thead>"
                              f"<tbody>{filas}</tbody></table>{sig}")

        if u.path == "/Document/Download":
            d = self.docs[int(q["id"][0])]
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr(d["archivo"].name, d["archivo"].read_bytes())
                z.writestr(d["archivo"].stem + ".pdf", b"%PDF-1.4 demo")
            return self._archivo(f"{d['numero']}.zip", buf.getvalue(), "application/zip")

        if u.path == "/Document/Export":
            return self._archivo("documentos.xlsx", (FIX / "listado_demo.xlsx").read_bytes(),
                                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        self._html("no existe", 404)


class DianSimulada:
    def __enter__(self):
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return self

    def enlace(self, token: str = "BUENO") -> str:
        return f"{self.url}/User/AuthToken?pk=10910094|900456789&rk=900456789&token={token}"

    def __exit__(self, *a):
        self.srv.shutdown()
