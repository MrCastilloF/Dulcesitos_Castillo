"""Primitivas de seguridad local.

Decisiones deliberadas
----------------------
* Nunca se almacena un código de acceso ni una clave de administración en
  texto plano. Se usa PBKDF2-HMAC-SHA256 con sal aleatoria por credencial.
* Cada código de acceso se puede localizar sin conocer el secreto mediante una
  huella SHA-256 determinista. El código generado tiene 60 bits de entropía
  (12 caracteres de un alfabeto de 32), por lo que esa huella no permite
  recuperarlo; la verificación final siempre usa PBKDF2 y comparación en tiempo
  constante.
* Los códigos no se pueden recuperar después de mostrarse una vez. Si se
  pierden, el administrador debe emitir uno nuevo.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

ALGORITMO = "pbkdf2_sha256"
ITERACIONES_POR_DEFECTO = 480_000
LONGITUD_SAL = 16
ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LONGITUD_ALEATORIA = 12
PREFIJO_CODIGO = "DLC"
LONGITUD_CODIGO = len(PREFIJO_CODIGO) + LONGITUD_ALEATORIA
PATRON_CODIGO = re.compile(r"^DLC-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


class ErrorSeguridad(ValueError):
    """Error controlado del módulo de seguridad."""


@dataclass(frozen=True)
class ClaveHasheada:
    algoritmo: str
    iteraciones: int
    sal: bytes
    resumen: bytes

    def a_texto(self) -> str:
        sal_b64 = base64.urlsafe_b64encode(self.sal).decode("ascii").rstrip("=")
        hash_b64 = base64.urlsafe_b64encode(self.resumen).decode("ascii").rstrip("=")
        return f"{self.algoritmo}${self.iteraciones}${sal_b64}${hash_b64}"


def _b64_decodificar(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def hash_clave(clave: str, iteraciones: int = ITERACIONES_POR_DEFECTO) -> str:
    """Devuelve una cadena autocontenida apta para guardar en SQLite."""

    if not isinstance(clave, str) or not clave:
        raise ErrorSeguridad("La clave no puede estar vacía.")
    if iteraciones < 100_000:
        raise ErrorSeguridad("El número de iteraciones es demasiado bajo.")
    sal = secrets.token_bytes(LONGITUD_SAL)
    resumen = hashlib.pbkdf2_hmac(
        "sha256", clave.encode("utf-8"), sal, iteraciones, dklen=32
    )
    return ClaveHasheada(ALGORITMO, iteraciones, sal, resumen).a_texto()


def verificar_clave(clave: str, valor_guardado: str) -> bool:
    """Verifica una clave sin filtrar información por tiempo de ejecución."""

    if not clave or not valor_guardado:
        return False
    try:
        algoritmo, iteraciones_txt, sal_b64, hash_b64 = valor_guardado.split("$", 3)
        if algoritmo != ALGORITMO:
            return False
        iteraciones = int(iteraciones_txt)
        if iteraciones < 100_000 or iteraciones > 5_000_000:
            return False
        sal = _b64_decodificar(sal_b64)
        esperado = _b64_decodificar(hash_b64)
        calculado = hashlib.pbkdf2_hmac(
            "sha256", clave.encode("utf-8"), sal, iteraciones, dklen=len(esperado)
        )
        return hmac.compare_digest(calculado, esperado)
    except (ValueError, TypeError, binascii.Error):
        return False


def normalizar_codigo_acceso(codigo: str) -> str:
    """Normaliza un código para compararlo sin depender de guiones/espacios."""

    return re.sub(r"[^A-Za-z0-9]", "", codigo or "").upper()


def formatear_codigo_acceso(codigo: str) -> str:
    limpio = normalizar_codigo_acceso(codigo)
    if len(limpio) != LONGITUD_CODIGO:
        return limpio
    aleatorio = limpio[len(PREFIJO_CODIGO) :]
    return (
        f"{PREFIJO_CODIGO}-"
        + "-".join(aleatorio[i : i + 4] for i in range(0, LONGITUD_ALEATORIA, 4))
    )


def generar_codigo_acceso() -> str:
    """Genera un código legible y difícil de adivinar, con formato DLC-XXXX..."""

    grupos = []
    for _ in range(LONGITUD_ALEATORIA // 4):
        grupos.append("".join(secrets.choice(ALFABETO_CODIGO) for _ in range(4)))
    return f"{PREFIJO_CODIGO}-" + "-".join(grupos)


def huella_codigo_acceso(codigo: str) -> str:
    """Huella determinista para localizar una credencial sin guardar el código."""

    normalizado = normalizar_codigo_acceso(codigo)
    if not normalizado:
        raise ErrorSeguridad("El código de acceso está vacío.")
    return hashlib.sha256(
        ("DulcesitosCastillo:codigo-acceso:v1:" + normalizado).encode("utf-8")
    ).hexdigest()


def pista_codigo(codigo: str) -> str:
    """Últimos cuatro caracteres mostrables en el panel administrativo."""

    normalizado = normalizar_codigo_acceso(codigo)
    return f"••••-{normalizado[-4:]}" if len(normalizado) >= 4 else "••••"


def validar_fortaleza_clave(clave: str) -> list[str]:
    """Reglas de la clave de administración. Devuelve errores legibles."""

    errores: list[str] = []
    if len(clave) < 10:
        errores.append("Debe tener al menos 10 caracteres.")
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", clave):
        errores.append("Debe incluir al menos una letra.")
    if not re.search(r"\d", clave):
        errores.append("Debe incluir al menos un número.")
    if re.search(r"\s", clave):
        errores.append("No puede contener espacios.")
    if clave.lower() in {
        "administrador",
        "admin12345",
        "1234567890",
        "dulcesitos",
        "password",
        "contrasena",
    }:
        errores.append("La clave es demasiado predecible.")
    return errores


def comparar_seguro(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
