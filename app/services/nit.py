"""NIT colombiano: dígito de verificación (algoritmo DIAN) y formato."""
import re

_PESOS = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]


def limpiar(nit: str) -> str:
    return re.sub(r"\D", "", nit or "")


def calcular_dv(nit: str) -> str:
    digitos = limpiar(nit)[::-1]
    suma = sum(int(d) * _PESOS[i] for i, d in enumerate(digitos))
    r = suma % 11
    return str(r if r in (0, 1) else 11 - r)


def formatear(nit: str, dv: str = "") -> str:
    n = f"{int(limpiar(nit)):,}".replace(",", ".")
    return f"{n}-{dv}" if dv else n
