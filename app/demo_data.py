"""Datos ficticios para la semilla y el MODO DEMO (proveedores y facturas inventados)."""

CLIENTES = [
    {"nit": "900456789", "razon_social": "Distribuidora Andina SAS", "email_rut": "rlegal@andina.co",
     "actividad": "Comercio al por mayor de alimentos y productos de consumo masivo"},
    {"nit": "901223004", "razon_social": "Café Montaña SAS", "email_rut": "gerencia@cafemontana.co",
     "actividad": "Tostión, empaque y venta de café"},
    {"nit": "900871330", "razon_social": "Transportes Llano", "email_rut": "contabilidad@transllano.co",
     "actividad": "Transporte de carga por carretera"},
]

# Plan de cuentas PUC básico (igual para los 3 clientes de la demo).
PUC = [
    ("1435", "Mercancías no fabricadas", "inventario"),
    ("1520", "Maquinaria y equipo", "activo"),
    ("1524", "Equipo de oficina", "activo"),
    ("1528", "Equipo de computación", "activo"),
    ("5110", "Honorarios", "gasto"),
    ("5120", "Arrendamientos", "gasto"),
    ("5130", "Seguros", "gasto"),
    ("5135", "Servicios", "servicio"),
    ("5145", "Mantenimiento y reparaciones", "gasto"),
    ("5195", "Diversos", "gasto"),
    ("5235", "Servicios (ventas)", "servicio"),
    ("5240", "Publicidad y propaganda (ventas)", "gasto"),
]

# Proveedores de las facturas de ejemplo (todas recibidas por Distribuidora Andina SAS).
# clasif: "regla" = ya existe regla confirmada en la semilla
#         ("ia", cuenta, conf, segunda, conf2, explicación) = respuesta simulada de la IA
PROVEEDORES = [
    {"nit": "900112233", "nombre": "Empaques Andinos SAS", "fecha": "2026-10-01",
     "lineas": [("Cajas de cartón corrugado x 500", 500, 16840)], "iva": True, "clasif": ("regla", "1435")},
    {"nit": "830045671", "nombre": "Inmobiliaria Sur SAS", "fecha": "2026-10-03",
     "lineas": [("Arriendo bodega octubre", 1, 4800000)], "iva": False, "retefuente": 0.035,
     "clasif": ("regla", "5120")},
    {"nit": "800334455", "nombre": "Estación de Servicio La 80", "fecha": "2026-10-05",
     "lineas": [("Combustible vehículo de reparto", 1, 386500)], "iva": False, "clasif": ("regla", "5195")},
    {"nit": "901556677", "nombre": "TecnoServicios del Caribe SAS", "fecha": "2026-10-07",
     "lineas": [("Mantenimiento preventivo montacargas", 1, 1250000), ("Repuestos sistema hidráulico", 2, 450000)],
     "iva": True,
     "clasif": ("ia", "5145", 0.52, "1520", 0.38, "Mezcla servicio y repuestos; los repuestos podrían capitalizarse.")},
    {"nit": "860078912", "nombre": "Papelería Central SAS", "fecha": "2026-10-09",
     "lineas": [("Resmas de papel carta x 20", 20, 14500), ("Tóner impresora", 1, 56500)], "iva": True,
     "clasif": ("ia", "5195", 0.96, "5135", 0.03, "Útiles y papelería de oficina.")},
    {"nit": "79845123", "nombre": "Asesorías Legales Pérez", "fecha": "2026-10-12",
     "lineas": [("Honorarios asesoría laboral octubre", 1, 3000000)], "iva": True, "retefuente": 0.11,
     "clasif": ("ia", "5110", 0.92, "5135", 0.06, "Servicio profesional prestado por persona natural.")},
    {"nit": "900667788", "nombre": "Lácteos La Pradera SAS", "fecha": "2026-10-15",
     "lineas": [("Leche entera x 1.200 unidades", 1200, 10650)], "iva": False, "clasif": ("regla", "1435")},
    {"nit": "901998877", "nombre": "Distribuciones Omega SAS", "fecha": "2026-10-18",
     "lineas": [("Kit promocional exhibidor x 30", 30, 53000)], "iva": True,
     "clasif": ("ia", "5240", 0.47, "1435", 0.44, "¿Se vende o se regala? Depende del uso del exhibidor.")},
    {"nit": "890223344", "nombre": "Transportes Rápido Sur SAS", "fecha": "2026-10-21",
     "lineas": [("Flete Bogotá – Tunja", 1, 960000)], "iva": False, "retefuente": 0.01,
     "clasif": ("ia", "5235", 0.88, "5135", 0.07, "Flete de entrega a clientes (gasto de ventas).")},
    {"nit": "900990011", "nombre": "Mundo Digital SAS", "fecha": "2026-10-24",
     "lineas": [("Computador portátil 16 GB", 1, 4739496)], "iva": True,
     "clasif": ("ia", "1528", 0.61, "5195", 0.33, "Depende de la política de activos del cliente.")},
    {"nit": "860002400", "nombre": "Seguros del Valle SA", "fecha": "2026-10-27",
     "lineas": [("Póliza todo riesgo flota de reparto", 1, 2350000)], "iva": True,
     "clasif": ("ia", "5130", 0.94, "5195", 0.03, "Prima de seguro de vehículos.")},
    {"nit": "901445566", "nombre": "Aseo Integral SAS", "fecha": "2026-10-30",
     "lineas": [("Servicio de aseo bodega octubre", 1, 1450000)], "iva": True, "retefuente": 0.02,
     "clasif": ("ia", "5135", 0.90, "5195", 0.05, "Servicio de aseo contratado.")},
]

# Cliente comprador de las facturas de ejemplo.
COMPRADOR_DEMO = CLIENTES[0]
