"""Selectores del portal DIAN (catalogo-vpfe.dian.gov.co) para el robot.

⚠️ Son la PRIMERA versión, escrita sin la grabación real. Cuando exista
`samples/dian_codegen.py`, reemplaza aquí los selectores por los grabados.
Cada clave tiene varias alternativas: el robot usa la primera que aparezca.
Si la DIAN cambia su página, este es el ÚNICO archivo que hay que tocar.
"""

# Hosts permitidos para el enlace del token (y para la navegación del robot).
HOSTS_DIAN = ("catalogo-vpfe.dian.gov.co",)

# Página de documentos recibidos (relativa al host del token).
RUTA_RECIBIDOS = "/Document/Received"

SELECTORES: dict[str, list[str]] = {
    # Señal de que la sesión quedó iniciada (menú o enlace a documentos).
    "sesion_ok": ["a[href*='/Document/Received']", "text=Recibidos", "text=Cerrar sesión"],
    # Rango de fechas: input único tipo "AAAA/MM/DD - AAAA/MM/DD" (daterangepicker).
    "rango_fechas": ["#dashboard-report-range", "input[name='RangoFechas']", "input.daterange"],
    "boton_buscar": ["#buscarDocumentos", "button:has-text('Buscar')", "input[value='Buscar']"],
    "tabla": ["#tableDocuments", "table.documents-table", "table"],
    # Filas de la tabla con documentos (excluye encabezado).
    "filas": ["#tableDocuments tbody tr", "table tbody tr"],
    # Botón de descarga dentro de cada fila.
    "descargar_fila": ["button.download-document", "a.download-document", "[title*='Descargar']", "text=Descargar"],
    "exportar_excel": ["#exportExcel", "button:has-text('Exportar Excel')", "a:has-text('Excel')"],
    "siguiente_pagina": ["#tableDocuments_next:not(.disabled) a", "a:has-text('Siguiente'):not(.disabled)"],
}

# Formato del rango de fechas que espera el portal.
FORMATO_RANGO = "{ini:%Y/%m/%d} - {fin:%Y/%m/%d}"

# Textos que indican verificación humana o bloqueo → el robot se PAUSA (no evade).
TEXTOS_VERIFICACION = (
    "solicitud bloqueada por controles de seguridad",
    "verifique que no es un robot",
    "no soy un robot",
    "verificación de seguridad",
    "captcha",
)
SELECTORES_VERIFICACION = (
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
    "#challenge-form",
    ".g-recaptcha",
)
# Textos que indican token vencido/inválido → error claro (pedir uno nuevo).
TEXTOS_TOKEN_INVALIDO = ("token no es válido", "token ha expirado", "token expirado", "token invalido", "token inválido")
