"""Altas y bajas locales de productos sin modificar el archivo maestro.

El archivo maestro sigue siendo la fuente principal y nunca se edita. El
administrador puede:

* **Dar de baja** un producto del maestro para que no se pueda escanear en
  sesiones nuevas.
* **Reactivarlo** si vuelve a la bodega.
* **Crear un producto local** que no esté en el archivo, usando las mismas
  columnas del catálogo.

Los ajustes se guardan en SQLite, se aplican al cargar el catálogo y quedan
incluidos en la copia de seguridad de cada sesión. Una sesión ya iniciada
conserva su catálogo original; los cambios rigen para las próximas sesiones.
El historial de productos vendidos o registrados no se elimina.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime

from .archivo_maestro import ArchivoMaestro, RegistroMaestro, normalizar_codigo_barras
from .base_datos import BaseDatos
from .modelos import Administrador
from .utilidades import ahora_utc, desde_iso

LOG = logging.getLogger(__name__)


class ErrorCatalogo(RuntimeError):
    """Operación de catálogo no válida."""


@dataclass(frozen=True)
class AjusteCatalogo:
    codigo_clave: str
    codigo: str
    descripcion: str
    campos: dict[str, str]
    origen: str
    estado: str
    motivo: str | None
    admin_nombre: str | None
    creado_en: datetime | None
    actualizado_en: datetime | None


@dataclass(frozen=True)
class VistaProducto:
    codigo_clave: str
    codigo: str
    descripcion: str
    estado: str
    origen: str
    campos: dict[str, str]
    motivo: str
    administrador: str
    actualizado_en: datetime | None

    @property
    def estado_visible(self) -> str:
        return {
            "activo": "Activo",
            "inactivo": "Dado de baja",
            "nuevo": "Nuevo local",
        }.get(self.estado, self.estado)


@dataclass(frozen=True)
class ResumenCatalogo:
    activos: int
    nuevos: int
    bajas: int
    ajustes: int


def _leer_campos(texto: str | None) -> dict[str, str]:
    try:
        datos = json.loads(texto or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(datos, dict):
        return {}
    return {str(k): str(v) for k, v in datos.items()}


class ServicioCatalogo:
    def __init__(self, db: BaseDatos):
        self.db = db

    # ------------------------------------------------------------------
    # Lectura y aplicación de ajustes
    # ------------------------------------------------------------------
    def ajustes(self) -> list[AjusteCatalogo]:
        resultado: list[AjusteCatalogo] = []
        for fila in self.db.listar_ajustes_catalogo():
            resultado.append(
                AjusteCatalogo(
                    codigo_clave=str(fila["codigo_clave"]),
                    codigo=str(fila["codigo"]),
                    descripcion=str(fila["descripcion"] or ""),
                    campos=_leer_campos(fila.get("campos_json")),
                    origen=str(fila["origen"]),
                    estado=str(fila["estado"]),
                    motivo=fila.get("motivo"),
                    admin_nombre=fila.get("admin_nombre"),
                    creado_en=desde_iso(fila.get("creado_en")),
                    actualizado_en=desde_iso(fila.get("actualizado_en")),
                )
            )
        return resultado

    def aplicar(self, maestro: ArchivoMaestro) -> ArchivoMaestro:
        """Devuelve el catálogo efectivo: maestro + altas - bajas."""

        ajustes = self.ajustes()
        if not ajustes:
            return maestro

        base_por_clave = {r.codigo_clave: r for r in maestro.registros}
        inactivos: dict[str, str] = {}
        altas: dict[str, AjusteCatalogo] = {}
        for ajuste in ajustes:
            if ajuste.estado == "inactivo":
                inactivos[ajuste.codigo_clave] = ajuste.descripcion
            elif ajuste.origen == "local" and ajuste.codigo_clave not in base_por_clave:
                altas[ajuste.codigo_clave] = ajuste

        registros = [
            registro
            for registro in maestro.registros
            if registro.codigo_clave not in inactivos
        ]
        for clave in sorted(altas):
            ajuste = altas[clave]
            campos = self._campos_completos(maestro, ajuste.campos)
            campos[maestro.columna_codigo] = ajuste.codigo
            campos[maestro.columna_descripcion] = ajuste.descripcion
            registros.append(
                RegistroMaestro(
                    codigo=ajuste.codigo,
                    codigo_clave=clave,
                    descripcion=ajuste.descripcion,
                    campos=campos,
                    fila=0,
                )
            )

        huella = self._huella_efectiva(maestro, ajustes)
        return ArchivoMaestro(
            ruta=maestro.ruta,
            nombre=maestro.nombre,
            hoja=maestro.hoja,
            columnas=maestro.columnas,
            columna_codigo=maestro.columna_codigo,
            columna_descripcion=maestro.columna_descripcion,
            registros=tuple(registros),
            advertencias=maestro.advertencias,
            cargado_en=maestro.cargado_en,
            huella=huella,
            formato=maestro.formato,
            inactivos=inactivos,
            ajustes_locales=len(ajustes),
        )

    def _campos_completos(
        self, maestro: ArchivoMaestro, campos: dict[str, str]
    ) -> dict[str, str]:
        return {columna: str(campos.get(columna, "")) for columna in maestro.columnas}

    def _huella_efectiva(
        self, maestro: ArchivoMaestro, ajustes: list[AjusteCatalogo]
    ) -> str:
        sha = hashlib.sha256()
        sha.update(b"DulcesitosCastillo:catalogo-efectivo:v1\0")
        sha.update(maestro.huella.encode("utf-8"))
        for ajuste in sorted(ajustes, key=lambda a: a.codigo_clave):
            payload = {
                "clave": ajuste.codigo_clave,
                "codigo": ajuste.codigo,
                "descripcion": ajuste.descripcion,
                "origen": ajuste.origen,
                "estado": ajuste.estado,
                "campos": ajuste.campos,
            }
            sha.update(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            sha.update(b"\0")
        return sha.hexdigest()

    # ------------------------------------------------------------------
    # Vista administrativa
    # ------------------------------------------------------------------
    def vista(self, maestro: ArchivoMaestro) -> list[VistaProducto]:
        ajustes = {a.codigo_clave: a for a in self.ajustes()}
        base_por_clave = {r.codigo_clave: r for r in maestro.registros}
        vista: list[VistaProducto] = []
        for clave, registro in base_por_clave.items():
            ajuste = ajustes.get(clave)
            estado = "inactivo" if ajuste and ajuste.estado == "inactivo" else "activo"
            vista.append(
                VistaProducto(
                    codigo_clave=clave,
                    codigo=registro.codigo,
                    descripcion=registro.descripcion,
                    estado=estado,
                    origen="maestro",
                    campos=registro.campos,
                    motivo=(ajuste.motivo or "") if ajuste else "",
                    administrador=(ajuste.admin_nombre or "") if ajuste else "",
                    actualizado_en=ajuste.actualizado_en if ajuste else None,
                )
            )
        for clave, ajuste in ajustes.items():
            if clave in base_por_clave:
                continue
            if ajuste.origen != "local":
                continue
            estado = "nuevo" if ajuste.estado == "activo" else "inactivo"
            vista.append(
                VistaProducto(
                    codigo_clave=clave,
                    codigo=ajuste.codigo,
                    descripcion=ajuste.descripcion,
                    estado=estado,
                    origen="local",
                    campos=ajuste.campos,
                    motivo=ajuste.motivo or "",
                    administrador=ajuste.admin_nombre or "",
                    actualizado_en=ajuste.actualizado_en,
                )
            )
        vista.sort(key=lambda p: (p.estado == "inactivo", p.codigo.casefold()))
        return vista

    def resumen(self, maestro: ArchivoMaestro) -> ResumenCatalogo:
        vista = self.vista(maestro)
        activos = sum(1 for p in vista if p.estado in {"activo", "nuevo"})
        nuevos = sum(1 for p in vista if p.origen == "local" and p.estado != "inactivo")
        bajas = sum(1 for p in vista if p.estado == "inactivo")
        return ResumenCatalogo(
            activos=activos,
            nuevos=nuevos,
            bajas=bajas,
            ajustes=self.db.contar_ajustes_catalogo(),
        )

    # ------------------------------------------------------------------
    # Altas
    # ------------------------------------------------------------------
    def crear_producto(
        self,
        *,
        admin: Administrador,
        maestro: ArchivoMaestro,
        codigo: str,
        descripcion: str,
        campos: dict[str, str],
    ) -> RegistroMaestro:
        codigo = str(codigo or "").strip()
        descripcion = str(descripcion or "").strip()
        if not codigo:
            raise ErrorCatalogo("El código del producto no puede estar vacío.")
        if len(codigo) > 200:
            raise ErrorCatalogo("El código del producto es demasiado largo.")
        if not descripcion:
            raise ErrorCatalogo("La descripción del producto es obligatoria.")
        if len(descripcion) > 300:
            raise ErrorCatalogo("La descripción no puede superar 300 caracteres.")
        clave = normalizar_codigo_barras(codigo)
        if not clave:
            raise ErrorCatalogo("El código del producto no es válido.")

        if maestro.buscar(codigo) is not None:
            raise ErrorCatalogo(
                "Ya existe un producto con ese código en el catálogo efectivo. "
                "Si está dado de baja, reactívalo desde la lista."
            )
        existente = self.db.ajuste_catalogo(clave)
        if existente is not None:
            if existente["estado"] == "inactivo":
                raise ErrorCatalogo(
                    "Ese código ya existe como producto local inactivo. "
                    "Reactívalo en lugar de crearlo de nuevo."
                )
            raise ErrorCatalogo("Ese código ya existe en el catálogo local.")

        datos = self._campos_completos(maestro, campos)
        datos[maestro.columna_codigo] = codigo
        datos[maestro.columna_descripcion] = descripcion
        self.db.guardar_ajuste_catalogo(
            codigo_clave=clave,
            codigo=codigo,
            descripcion=descripcion,
            campos=datos,
            origen="local",
            estado="activo",
            motivo="Alta local de producto",
            admin_id=admin.id,
            admin_nombre=admin.nombre,
        )
        LOG.info("Producto local creado: %s por admin %s", codigo, admin.cedula)
        return RegistroMaestro(
            codigo=codigo,
            codigo_clave=clave,
            descripcion=descripcion,
            campos=datos,
            fila=0,
        )

    # ------------------------------------------------------------------
    # Bajas y reactivaciones
    # ------------------------------------------------------------------
    def dar_de_baja(
        self,
        *,
        admin: Administrador,
        maestro: ArchivoMaestro,
        codigo: str,
        motivo: str = "",
    ) -> VistaProducto:
        clave = normalizar_codigo_barras(codigo)
        if not clave:
            raise ErrorCatalogo("Debes indicar el código del producto.")
        vista = {p.codigo_clave: p for p in self.vista(maestro)}
        producto = vista.get(clave)
        if producto is None:
            raise ErrorCatalogo("El producto no existe en el catálogo actual.")
        if producto.estado == "inactivo":
            raise ErrorCatalogo("El producto ya está dado de baja.")
        origen = producto.origen
        campos = self._campos_completos(maestro, producto.campos)
        campos[maestro.columna_codigo] = producto.codigo
        campos[maestro.columna_descripcion] = producto.descripcion
        self.db.guardar_ajuste_catalogo(
            codigo_clave=clave,
            codigo=producto.codigo,
            descripcion=producto.descripcion,
            campos=campos,
            origen=origen,
            estado="inactivo",
            motivo=(motivo or "").strip() or "Baja manual desde administración",
            admin_id=admin.id,
            admin_nombre=admin.nombre,
        )
        LOG.info("Producto dado de baja: %s por admin %s", producto.codigo, admin.cedula)
        return VistaProducto(
            codigo_clave=producto.codigo_clave,
            codigo=producto.codigo,
            descripcion=producto.descripcion,
            estado="inactivo",
            origen=origen,
            campos=campos,
            motivo=(motivo or "").strip() or "Baja manual desde administración",
            administrador=admin.nombre,
            actualizado_en=ahora_utc(),
        )

    def reactivar(
        self,
        *,
        admin: Administrador,
        maestro: ArchivoMaestro,
        codigo: str,
    ) -> VistaProducto:
        clave = normalizar_codigo_barras(codigo)
        ajuste = self.db.ajuste_catalogo(clave)
        if ajuste is None:
            raise ErrorCatalogo("Ese producto no tiene una baja pendiente de reactivar.")
        if ajuste["estado"] != "inactivo":
            raise ErrorCatalogo("El producto ya está activo.")
        codigo_visible = str(ajuste["codigo"])
        descripcion = str(ajuste["descripcion"] or "")
        campos = _leer_campos(ajuste.get("campos_json"))
        if str(ajuste["origen"]) == "maestro":
            self.db.eliminar_ajuste_catalogo(clave)
            estado = "activo"
            LOG.info("Baja revertida para %s por admin %s", codigo_visible, admin.cedula)
        else:
            # Si el maestro ya incorporó este producto, se elimina el ajuste
            # local para que el maestro sea la fuente de verdad.
            if maestro.buscar(codigo_visible) is not None:
                self.db.eliminar_ajuste_catalogo(clave)
                estado = "activo"
            else:
                self.db.guardar_ajuste_catalogo(
                    codigo_clave=clave,
                    codigo=codigo_visible,
                    descripcion=descripcion,
                    campos=self._campos_completos(maestro, campos),
                    origen="local",
                    estado="activo",
                    motivo="Reactivación local",
                    admin_id=admin.id,
                    admin_nombre=admin.nombre,
                )
                estado = "nuevo"
            LOG.info("Producto local reactivado: %s por admin %s", codigo_visible, admin.cedula)
        return VistaProducto(
            codigo_clave=clave,
            codigo=codigo_visible,
            descripcion=descripcion,
            estado=estado,
            origen=str(ajuste["origen"]),
            campos=campos,
            motivo="Reactivación",
            administrador=admin.nombre,
            actualizado_en=ahora_utc(),
        )

    # ------------------------------------------------------------------
    # Búsqueda en vista administrativa
    # ------------------------------------------------------------------
    def buscar(self, maestro: ArchivoMaestro, consulta: str) -> list[VistaProducto]:
        texto = (consulta or "").strip().casefold()
        vista = self.vista(maestro)
        if not texto:
            return vista
        return [
            producto
            for producto in vista
            if texto in producto.codigo.casefold()
            or texto in producto.descripcion.casefold()
        ]

    def cantidad_ajustes(self) -> int:
        return self.db.contar_ajustes_catalogo()
