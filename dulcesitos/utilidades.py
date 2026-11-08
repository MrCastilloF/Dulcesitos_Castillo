"""Utilidades de fechas, validación, texto y apertura de archivos."""

from __future__ import annotations

import os
import re
import subprocess
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path


class ErrorValidacion(ValueError):
    """Dato de formulario inválido con mensaje apto para mostrar al usuario."""


PATRON_CEDULA = re.compile(r"^\d{5,12}$")
PATRON_CORREO = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
MESES_CORTOS = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def a_iso(fecha: datetime | None) -> str | None:
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc).isoformat(timespec="seconds")


def desde_iso(texto: str | None) -> datetime | None:
    if not texto:
        return None
    limpio = texto.strip()
    if limpio.endswith("Z"):
        limpio = limpio[:-1] + "+00:00"
    try:
        resultado = datetime.fromisoformat(limpio)
    except ValueError:
        return None
    if resultado.tzinfo is None:
        resultado = resultado.replace(tzinfo=timezone.utc)
    return resultado


def a_local(fecha: datetime) -> datetime:
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone()


def formatear_fecha(fecha: datetime | None) -> str:
    if fecha is None:
        return "—"
    local = a_local(fecha)
    return f"{local.day:02d}/{local.month:02d}/{local.year}"


def formatear_fecha_hora(fecha: datetime | None) -> str:
    if fecha is None:
        return "—"
    local = a_local(fecha)
    return (
        f"{local.day:02d}/{local.month:02d}/{local.year} "
        f"{local.hour:02d}:{local.minute:02d}"
    )


def formatear_fecha_hora_segundos(fecha: datetime | None) -> str:
    if fecha is None:
        return "—"
    local = a_local(fecha)
    return (
        f"{local.day:02d}/{local.month:02d}/{local.year} "
        f"{local.hour:02d}:{local.minute:02d}:{local.second:02d}"
    )


def formatear_hora(fecha: datetime | None) -> str:
    if fecha is None:
        return "—"
    local = a_local(fecha)
    return f"{local.hour:02d}:{local.minute:02d}"


def formatear_fecha_larga(fecha: datetime | None) -> str:
    if fecha is None:
        return "—"
    local = a_local(fecha)
    return f"{local.day} de {MESES_CORTOS[local.month - 1]}. de {local.year}"


def limpiar_espacios(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto or "").replace("\xa0", " ")).strip()


def quitar_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def normalizar_para_comparar(texto: str) -> str:
    return re.sub(r"\s+", " ", quitar_acentos(texto or "").casefold()).strip()


def normalizar_cedula(cedula: str) -> str:
    limpio = re.sub(r"[^0-9]", "", cedula or "")
    return limpio


def normalizar_correo(correo: str) -> str:
    return (correo or "").strip().casefold()


def normalizar_nombre(nombre: str) -> str:
    return re.sub(r"\s+", " ", limpiar_espacios(nombre)).strip()


def validar_nombre(nombre: str, etiqueta: str = "nombre completo") -> str:
    limpio = normalizar_nombre(nombre)
    if len(limpio) < 3:
        raise ErrorValidacion(f"El {etiqueta} debe tener al menos 3 caracteres.")
    if len(limpio) > 100:
        raise ErrorValidacion(f"El {etiqueta} no puede superar 100 caracteres.")
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", limpio):
        raise ErrorValidacion(f"El {etiqueta} debe contener letras.")
    if re.search(r"[<>{}]", limpio):
        raise ErrorValidacion(f"El {etiqueta} contiene caracteres no permitidos.")
    return limpio


def validar_cedula(cedula: str) -> str:
    limpio = normalizar_cedula(cedula)
    if not PATRON_CEDULA.match(limpio):
        raise ErrorValidacion(
            "La cédula debe contener entre 5 y 12 dígitos, sin puntos ni espacios."
        )
    return limpio


def validar_correo(correo: str) -> str:
    limpio = normalizar_correo(correo)
    if len(limpio) > 160 or not PATRON_CORREO.match(limpio):
        raise ErrorValidacion("Escribe un correo electrónico válido.")
    return limpio


def validar_codigo_acceso_ingresado(codigo: str) -> str:
    from .seguridad import normalizar_codigo_acceso

    limpio = normalizar_codigo_acceso(codigo)
    if len(limpio) != 15 or not limpio.startswith("DLC"):
        raise ErrorValidacion(
            "El código de acceso debe tener el formato DLC-ABCD-EFGH-JKLM."
        )
    return limpio


def nombre_coincide(ingresado: str, registrado: str) -> bool:
    return normalizar_para_comparar(ingresado) == normalizar_para_comparar(registrado)


def iniciales(nombre: str, maximo: int = 2) -> str:
    partes = [p for p in normalizar_nombre(nombre).split(" ") if p]
    if not partes:
        return "??"
    letras = [partes[0][0]]
    if len(partes) > 1:
        letras.append(partes[-1][0])
    return "".join(letras).upper()[:maximo]


def truncar(texto: str, maximo: int, sufijo: str = "…") -> str:
    texto = str(texto or "")
    if len(texto) <= maximo:
        return texto
    return texto[: max(0, maximo - len(sufijo))].rstrip() + sufijo


def slug_archivo(texto: str, maximo: int = 36) -> str:
    base = quitar_acentos(texto or "").lower()
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    if not base:
        base = "operador"
    return base[:maximo].rstrip("_")


def fecha_para_archivo(fecha: datetime) -> str:
    local = a_local(fecha)
    return local.strftime("%Y%m%d_%H%M%S")


def nombre_archivo_unico(carpeta: Path, base: str, extension: str) -> Path:
    candidato = carpeta / f"{base}{extension}"
    contador = 2
    while candidato.exists():
        candidato = carpeta / f"{base}_{contador}{extension}"
        contador += 1
    return candidato


def unir_valores(valores: Iterable[object], separador: str = " · ") -> str:
    return separador.join(str(v).strip() for v in valores if str(v or "").strip())


def formatear_tamano(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB"


def abrir_archivo(ruta: str | Path) -> bool:
    """Abre un archivo con la aplicación predeterminada de Windows."""

    ruta = str(ruta)
    try:
        if os.name == "nt":
            os.startfile(ruta)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", ruta])
        return True
    except OSError:
        return False


def abrir_carpeta(ruta: str | Path) -> bool:
    ruta = str(ruta)
    try:
        if os.name == "nt":
            os.startfile(ruta)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", ruta])
        return True
    except OSError:
        return False


def imprimir_archivo(ruta: str | Path) -> bool:
    """Envía un PDF al flujo de impresión de Windows."""

    if os.name != "nt":
        return False
    try:
        os.startfile(str(ruta), "print")  # type: ignore[attr-defined]
        return True
    except OSError:
        return False


def sello_tiempo_local(fecha: datetime | None = None) -> str:
    local = a_local(fecha or ahora_utc())
    return local.strftime("%Y-%m-%d %H:%M:%S")


def rango_dias(fecha: datetime, dias: int) -> datetime:
    from datetime import timedelta

    return fecha + timedelta(days=dias)


def fecha_visible_corta(valor: date | datetime) -> str:
    return f"{valor.day:02d}/{valor.month:02d}/{valor.year}"
