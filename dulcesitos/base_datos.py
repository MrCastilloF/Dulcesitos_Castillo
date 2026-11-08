"""Persistencia local en SQLite.

La base guarda únicamente hashes de credenciales. Los códigos de acceso y las
claves de administración nunca se escriben en texto plano. Cada lectura se
confirma de inmediato para que un cierre inesperado de la aplicación no pierda
el trabajo del operador.

El esquema está versionado en ``PRAGMA user_version``. La versión 4 agrega el
origen del registro (lector o manual) y la novedad escrita por el operador.
Las versiones anteriores se actualizan de forma idempotente al abrir la base.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .modelos import (
    Administrador,
    ArchivoGenerado,
    EstadisticasSesion,
    Operador,
    RegistroSesion,
    Sesion,
    SesionOperador,
)
from .utilidades import a_iso, desde_iso

LOG = logging.getLogger(__name__)
VERSION_ESQUEMA = 4


class ErrorBaseDatos(RuntimeError):
    """Error controlado de persistencia."""


class ErrorCodigo(ErrorBaseDatos):
    """El código de acceso no está disponible para la operación solicitada."""


ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS administradores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    cedula TEXT NOT NULL UNIQUE,
    correo TEXT NOT NULL,
    clave_hash TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS operadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    cedula TEXT NOT NULL UNIQUE,
    correo TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS codigos_acceso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    huella TEXT NOT NULL UNIQUE,
    codigo_hash TEXT NOT NULL,
    pista TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('pendiente', 'activo', 'revocado')),
    operador_id INTEGER REFERENCES operadores(id) ON DELETE SET NULL,
    nombre_asignado TEXT,
    cedula_asignada TEXT,
    correo_asignado TEXT,
    emitido_por INTEGER NOT NULL REFERENCES administradores(id),
    creado_en TEXT NOT NULL,
    expira_en TEXT NOT NULL,
    activado_en TEXT,
    revocado_en TEXT,
    revocado_por INTEGER REFERENCES administradores(id),
    ultimo_uso_en TEXT,
    usos INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_codigos_operador
    ON codigos_acceso(operador_id, estado);
CREATE INDEX IF NOT EXISTS ix_codigos_expira
    ON codigos_acceso(expira_en);

CREATE TABLE IF NOT EXISTS sesiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operador_id INTEGER NOT NULL REFERENCES operadores(id),
    operador_nombre TEXT NOT NULL,
    operador_cedula TEXT NOT NULL,
    codigo_id INTEGER REFERENCES codigos_acceso(id) ON DELETE SET NULL,
    estado TEXT NOT NULL CHECK (estado IN ('abierta', 'finalizada')),
    inicio_en TEXT NOT NULL,
    fin_en TEXT,
    maestro_nombre TEXT NOT NULL,
    maestro_ruta TEXT NOT NULL,
    maestro_hash TEXT NOT NULL,
    instantanea_ruta TEXT,
    calibracion_codigo TEXT NOT NULL,
    calibracion_en TEXT NOT NULL,
    autorizado_por TEXT,
    metodo_autorizacion TEXT,
    creado_en TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_sesion_abierta_operador
    ON sesiones(operador_id) WHERE estado = 'abierta';
CREATE INDEX IF NOT EXISTS ix_sesiones_estado ON sesiones(estado, inicio_en);

CREATE TABLE IF NOT EXISTS lecturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones(id) ON DELETE CASCADE,
    codigo_ingresado TEXT NOT NULL,
    codigo_clave TEXT NOT NULL,
    resultado TEXT NOT NULL CHECK (
        resultado IN ('registrado', 'duplicado', 'no_encontrado')
    ),
    producto_codigo TEXT,
    descripcion TEXT,
    datos_json TEXT,
    creado_en TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lecturas_sesion ON lecturas(sesion_id, creado_en);

CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones(id) ON DELETE CASCADE,
    lectura_id INTEGER REFERENCES lecturas(id) ON DELETE SET NULL,
    codigo TEXT NOT NULL,
    codigo_clave TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    datos_json TEXT NOT NULL,
    escaneado_en TEXT NOT NULL,
    operador_nombre TEXT NOT NULL,
    operador_cedula TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'lector' CHECK (origen IN ('lector', 'manual')),
    novedad TEXT,
    UNIQUE (sesion_id, codigo_clave)
);

CREATE INDEX IF NOT EXISTS ix_registros_sesion ON registros(sesion_id, escaneado_en);

CREATE TABLE IF NOT EXISTS exportaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('xlsx', 'pdf', 'txt')),
    nombre_archivo TEXT NOT NULL,
    ruta TEXT NOT NULL,
    tamano_bytes INTEGER NOT NULL DEFAULT 0,
    creado_en TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_exportaciones_sesion ON exportaciones(sesion_id);

CREATE TABLE IF NOT EXISTS catalogo_ajustes (
    codigo_clave TEXT PRIMARY KEY,
    codigo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    campos_json TEXT NOT NULL,
    origen TEXT NOT NULL CHECK (origen IN ('maestro', 'local')),
    estado TEXT NOT NULL CHECK (estado IN ('activo', 'inactivo')),
    motivo TEXT,
    admin_id INTEGER REFERENCES administradores(id) ON DELETE SET NULL,
    admin_nombre TEXT,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_catalogo_ajustes_estado
    ON catalogo_ajustes(estado, origen);

CREATE TABLE IF NOT EXISTS ajustes_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones(id) ON DELETE CASCADE,
    registro_id INTEGER NOT NULL UNIQUE REFERENCES registros(id) ON DELETE CASCADE,
    codigo TEXT NOT NULL,
    stock_original REAL,
    stock_nuevo REAL NOT NULL,
    diferencia REAL,
    operador_nombre TEXT NOT NULL,
    operador_cedula TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ajustes_stock_sesion
    ON ajustes_stock(sesion_id);

CREATE TABLE IF NOT EXISTS ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
"""


class BaseDatos:
    """Acceso encapsulado a la base SQLite local."""

    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(
            str(self.ruta), timeout=15, isolation_level=None
        )
        self._conexion.row_factory = sqlite3.Row
        self._configurar()
        self._crear_esquema()

    # ------------------------------------------------------------------
    # Infraestructura
    # ------------------------------------------------------------------
    def _configurar(self) -> None:
        cur = self._conexion.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA synchronous = NORMAL")
        cur.execute("PRAGMA busy_timeout = 15000")
        cur.close()

    def _crear_esquema(self) -> None:
        with self._conexion:
            self._conexion.executescript(ESQUEMA)
            version = self._conexion.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3, VERSION_ESQUEMA):
                raise ErrorBaseDatos(
                    "La base de datos fue creada por una versión más reciente "
                    f"(esquema {version}). Actualiza la aplicación."
                )
            self._migrar_columnas_registros()
            self._conexion.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")
            self._conexion.execute(
                "INSERT OR IGNORE INTO meta(clave, valor) VALUES ('esquema', ?)",
                (str(VERSION_ESQUEMA),),
            )

    def _migrar_columnas_registros(self) -> None:
        columnas = {
            str(fila["name"])
            for fila in self._conexion.execute("PRAGMA table_info(registros)")
        }
        if "origen" not in columnas:
            self._conexion.execute(
                "ALTER TABLE registros ADD COLUMN origen TEXT NOT NULL DEFAULT 'lector'"
            )
        if "novedad" not in columnas:
            self._conexion.execute("ALTER TABLE registros ADD COLUMN novedad TEXT")

    def cerrar(self) -> None:
        try:
            self._conexion.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> BaseDatos:
        return self

    def __exit__(self, *args: object) -> None:
        self.cerrar()

    @contextmanager
    def transaccion(self) -> Iterator[sqlite3.Connection]:
        self._conexion.execute("BEGIN IMMEDIATE")
        try:
            yield self._conexion
        except Exception:
            self._conexion.rollback()
            raise
        else:
            self._conexion.commit()

    def verificar_integridad(self) -> tuple[bool, str]:
        try:
            fila = self._conexion.execute("PRAGMA quick_check").fetchone()
            mensaje = fila[0] if fila else "sin resultado"
            return mensaje == "ok", mensaje
        except sqlite3.Error as exc:
            return False, str(exc)

    def respaldar(self, destino: str | Path) -> Path:
        """Copia consistente de la base usando la API de respaldo de SQLite."""

        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(str(destino)) as copia:
                self._conexion.backup(copia)
        except sqlite3.Error as exc:
            raise ErrorBaseDatos(f"No se pudo crear el respaldo: {exc}") from exc
        return destino

    def _una(self, sql: str, parametros: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self._conexion.execute(sql, parametros).fetchone()

    def _todas(self, sql: str, parametros: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return list(self._conexion.execute(sql, parametros).fetchall())

    # ------------------------------------------------------------------
    # Administradores
    # ------------------------------------------------------------------
    def hay_administrador(self) -> bool:
        fila = self._una("SELECT 1 FROM administradores WHERE activo = 1 LIMIT 1")
        return fila is not None

    def crear_administrador(
        self, nombre: str, cedula: str, correo: str, clave_hash: str
    ) -> Administrador:
        ahora = a_iso(datetime.now().astimezone())
        try:
            with self.transaccion() as conexion:
                cur = conexion.execute(
                    """
                    INSERT INTO administradores
                        (nombre, cedula, correo, clave_hash, creado_en, actualizado_en)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (nombre, cedula, correo, clave_hash, ahora, ahora),
                )
                admin_id = int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ErrorBaseDatos(
                "Ya existe un administrador con esa cédula."
            ) from exc
        return Administrador(
            id=admin_id,
            nombre=nombre,
            cedula=cedula,
            correo=correo,
            creado_en=desde_iso(ahora),
        )

    def administrador_por_cedula(self, cedula: str) -> dict[str, Any] | None:
        fila = self._una(
            "SELECT * FROM administradores WHERE cedula = ? AND activo = 1",
            (cedula,),
        )
        return dict(fila) if fila else None

    def administrador_por_id(self, admin_id: int) -> Administrador | None:
        fila = self._una(
            "SELECT * FROM administradores WHERE id = ? AND activo = 1",
            (admin_id,),
        )
        if not fila:
            return None
        return Administrador(
            id=int(fila["id"]),
            nombre=str(fila["nombre"]),
            cedula=str(fila["cedula"]),
            correo=str(fila["correo"]),
            creado_en=desde_iso(fila["creado_en"]),
        )

    def administradores_activos(self) -> list[dict[str, Any]]:
        return [
            dict(fila)
            for fila in self._todas(
                "SELECT * FROM administradores WHERE activo = 1 ORDER BY id"
            )
        ]

    def actualizar_clave_administrador(
        self, admin_id: int, clave_hash: str
    ) -> None:
        ahora = a_iso(datetime.now().astimezone())
        with self._conexion:
            self._conexion.execute(
                """
                UPDATE administradores
                   SET clave_hash = ?, actualizado_en = ?
                 WHERE id = ? AND activo = 1
                """,
                (clave_hash, ahora, admin_id),
            )

    # ------------------------------------------------------------------
    # Operadores
    # ------------------------------------------------------------------
    def operador_por_cedula(self, cedula: str) -> Operador | None:
        fila = self._una("SELECT * FROM operadores WHERE cedula = ?", (cedula,))
        return self._fila_operador(fila) if fila else None

    def operador_por_id(self, operador_id: int) -> Operador | None:
        fila = self._una("SELECT * FROM operadores WHERE id = ?", (operador_id,))
        return self._fila_operador(fila) if fila else None

    def _fila_operador(self, fila: sqlite3.Row) -> Operador:
        expira = self._una(
            """
            SELECT MAX(expira_en) AS expira_en
              FROM codigos_acceso
             WHERE operador_id = ? AND estado = 'activo'
            """,
            (fila["id"],),
        )
        return Operador(
            id=int(fila["id"]),
            nombre=str(fila["nombre"]),
            cedula=str(fila["cedula"]),
            correo=str(fila["correo"]),
            creado_en=desde_iso(fila["creado_en"]),
            activo=bool(fila["activo"]),
            acceso_expira_en=desde_iso(expira["expira_en"]) if expira else None,
        )

    def crear_operador(
        self, nombre: str, cedula: str, correo: str
    ) -> dict[str, Any]:
        ahora = a_iso(datetime.now().astimezone())
        try:
            with self.transaccion() as conexion:
                cur = conexion.execute(
                    """
                    INSERT INTO operadores
                        (nombre, cedula, correo, creado_en, actualizado_en, activo)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (nombre, cedula, correo, ahora, ahora),
                )
                operador_id = int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ErrorBaseDatos("Ya existe un operador con esa cédula.") from exc
        return {
            "id": operador_id,
            "nombre": nombre,
            "cedula": cedula,
            "correo": correo,
            "creado_en": ahora,
            "activo": 1,
        }

    def listar_operadores(self, limite: int = 300) -> list[dict[str, Any]]:
        filas = self._todas(
            """
            SELECT o.*,
                   c.id AS acceso_id,
                   c.pista AS acceso_pista,
                   c.estado AS acceso_estado,
                   c.expira_en AS acceso_expira_en,
                   c.ultimo_uso_en AS acceso_ultimo_uso,
                   (SELECT COUNT(*) FROM registros r WHERE r.operador_cedula = o.cedula)
                       AS total_registros,
                   (SELECT COUNT(*) FROM sesiones s WHERE s.operador_id = o.id)
                       AS total_sesiones
              FROM operadores o
              LEFT JOIN codigos_acceso c
                     ON c.id = (
                         SELECT c2.id
                           FROM codigos_acceso c2
                          WHERE c2.operador_id = o.id
                            AND c2.estado = 'activo'
                          ORDER BY c2.expira_en DESC, c2.id DESC
                          LIMIT 1
                     )
             ORDER BY o.nombre COLLATE NOCASE
             LIMIT ?
            """,
            (limite,),
        )
        return [dict(fila) for fila in filas]

    # ------------------------------------------------------------------
    # Códigos de acceso
    # ------------------------------------------------------------------
    def crear_codigo_acceso(
        self,
        *,
        huella: str,
        codigo_hash: str,
        pista: str,
        estado: str,
        operador_id: int | None,
        nombre_asignado: str | None,
        cedula_asignada: str | None,
        correo_asignado: str | None,
        emitido_por: int,
        creado_en: str,
        expira_en: str,
    ) -> int:
        try:
            with self.transaccion() as conexion:
                cur = conexion.execute(
                    """
                    INSERT INTO codigos_acceso
                        (huella, codigo_hash, pista, estado, operador_id,
                         nombre_asignado, cedula_asignada, correo_asignado,
                         emitido_por, creado_en, expira_en, usos)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        huella,
                        codigo_hash,
                        pista,
                        estado,
                        operador_id,
                        nombre_asignado,
                        cedula_asignada,
                        correo_asignado,
                        emitido_por,
                        creado_en,
                        expira_en,
                    ),
                )
                return int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ErrorBaseDatos(
                "No fue posible generar un código único. Intenta de nuevo."
            ) from exc

    def codigo_por_huella(self, huella: str) -> dict[str, Any] | None:
        fila = self._una(
            """
            SELECT c.*, o.nombre AS operador_nombre_actual,
                   a.nombre AS emitido_por_nombre
              FROM codigos_acceso c
              LEFT JOIN operadores o ON o.id = c.operador_id
              LEFT JOIN administradores a ON a.id = c.emitido_por
             WHERE c.huella = ?
            """,
            (huella,),
        )
        return dict(fila) if fila else None

    def codigo_por_id(self, codigo_id: int) -> dict[str, Any] | None:
        fila = self._una(
            """
            SELECT c.*, o.nombre AS operador_nombre_actual,
                   a.nombre AS emitido_por_nombre
              FROM codigos_acceso c
              LEFT JOIN operadores o ON o.id = c.operador_id
              LEFT JOIN administradores a ON a.id = c.emitido_por
             WHERE c.id = ?
            """,
            (codigo_id,),
        )
        return dict(fila) if fila else None

    def listar_codigos(self, limite: int = 400) -> list[dict[str, Any]]:
        filas = self._todas(
            """
            SELECT c.*, o.nombre AS operador_nombre_actual,
                   a.nombre AS emitido_por_nombre
              FROM codigos_acceso c
              LEFT JOIN operadores o ON o.id = c.operador_id
              LEFT JOIN administradores a ON a.id = c.emitido_por
             ORDER BY c.id DESC
             LIMIT ?
            """,
            (limite,),
        )
        return [dict(fila) for fila in filas]

    def codigos_activos_operador(self, operador_id: int) -> list[dict[str, Any]]:
        filas = self._todas(
            """
            SELECT * FROM codigos_acceso
             WHERE operador_id = ? AND estado = 'activo'
             ORDER BY id DESC
            """,
            (operador_id,),
        )
        return [dict(fila) for fila in filas]

    def revocar_codigo(self, codigo_id: int, admin_id: int) -> bool:
        ahora = a_iso(datetime.now().astimezone())
        with self.transaccion() as conexion:
            cur = conexion.execute(
                """
                UPDATE codigos_acceso
                   SET estado = 'revocado', revocado_en = ?, revocado_por = ?
                 WHERE id = ? AND estado != 'revocado'
                """,
                (ahora, admin_id, codigo_id),
            )
            return cur.rowcount > 0

    def revocar_codigos_operador(
        self, operador_id: int, admin_id: int, excepto_id: int | None = None
    ) -> int:
        ahora = a_iso(datetime.now().astimezone())
        with self.transaccion() as conexion:
            if excepto_id is None:
                cur = conexion.execute(
                    """
                    UPDATE codigos_acceso
                       SET estado = 'revocado', revocado_en = ?, revocado_por = ?
                     WHERE operador_id = ? AND estado != 'revocado'
                    """,
                    (ahora, admin_id, operador_id),
                )
            else:
                cur = conexion.execute(
                    """
                    UPDATE codigos_acceso
                       SET estado = 'revocado', revocado_en = ?, revocado_por = ?
                     WHERE operador_id = ? AND estado != 'revocado' AND id != ?
                    """,
                    (ahora, admin_id, operador_id, excepto_id),
                )
            return cur.rowcount

    def canjear_codigo(
        self,
        *,
        codigo_id: int,
        nombre: str,
        cedula: str,
        correo: str,
        ahora: str,
        operador_existente_id: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Activa una invitación y crea/reutiliza el operador en una transacción."""

        with self.transaccion() as conexion:
            fila = conexion.execute(
                "SELECT * FROM codigos_acceso WHERE id = ?", (codigo_id,)
            ).fetchone()
            if fila is None:
                raise ErrorCodigo("El código de acceso no existe.")
            if fila["estado"] != "pendiente":
                raise ErrorCodigo("El código de acceso ya fue utilizado o revocado.")
            if fila["expira_en"] <= ahora:
                raise ErrorCodigo("El código de acceso está vencido.")

            if operador_existente_id is None:
                try:
                    cur = conexion.execute(
                        """
                        INSERT INTO operadores
                            (nombre, cedula, correo, creado_en, actualizado_en, activo)
                        VALUES (?, ?, ?, ?, ?, 1)
                        """,
                        (nombre, cedula, correo, ahora, ahora),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ErrorBaseDatos(
                        "Ya existe un operador con esa cédula. Solicita al "
                        "administrador un código de renovación."
                    ) from exc
                operador_id = int(cur.lastrowid)
            else:
                operador_id = int(operador_existente_id)

            conexion.execute(
                """
                UPDATE codigos_acceso
                   SET estado = 'activo', operador_id = ?, activado_en = ?,
                       ultimo_uso_en = ?, usos = usos + 1
                 WHERE id = ?
                """,
                (operador_id, ahora, ahora, codigo_id),
            )
            operador = conexion.execute(
                "SELECT * FROM operadores WHERE id = ?", (operador_id,)
            ).fetchone()
            if operador is None:
                raise ErrorBaseDatos("No fue posible recuperar el operador.")
            return dict(operador), dict(
                conexion.execute(
                    "SELECT * FROM codigos_acceso WHERE id = ?", (codigo_id,)
                ).fetchone()
            )

    def registrar_uso_codigo(self, codigo_id: int) -> None:
        ahora = a_iso(datetime.now().astimezone())
        with self._conexion:
            self._conexion.execute(
                """
                UPDATE codigos_acceso
                   SET ultimo_uso_en = ?, usos = usos + 1
                 WHERE id = ? AND estado = 'activo'
                """,
                (ahora, codigo_id),
            )

    # ------------------------------------------------------------------
    # Sesiones
    # ------------------------------------------------------------------
    def crear_sesion(
        self,
        *,
        operador: SesionOperador,
        maestro_nombre: str,
        maestro_ruta: str,
        maestro_hash: str,
        instantanea_ruta: str | None,
        calibracion_codigo: str,
        ahora: str,
    ) -> int:
        try:
            with self.transaccion() as conexion:
                cur = conexion.execute(
                    """
                    INSERT INTO sesiones
                        (operador_id, operador_nombre, operador_cedula, codigo_id,
                         estado, inicio_en, maestro_nombre, maestro_ruta,
                         maestro_hash, instantanea_ruta, calibracion_codigo,
                         calibracion_en, creado_en)
                    VALUES (?, ?, ?, ?, 'abierta', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operador.operador_id,
                        operador.nombre,
                        operador.cedula,
                        operador.codigo_id,
                        ahora,
                        maestro_nombre,
                        maestro_ruta,
                        maestro_hash,
                        instantanea_ruta,
                        calibracion_codigo,
                        ahora,
                        ahora,
                    ),
                )
                return int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ErrorBaseDatos(
                "Este operador ya tiene una sesión de inventario abierta. "
                "Reábrela para continuar o finalízala antes de iniciar otra."
            ) from exc

    def archivar_sesion_incompleta(self, sesion_id: int) -> None:
        """Descarta una sesión recién creada si falló la copia del catálogo."""

        with self._conexion:
            self._conexion.execute(
                "DELETE FROM sesiones WHERE id = ? AND estado = 'abierta'",
                (sesion_id,),
            )

    def actualizar_instantanea(self, sesion_id: int, ruta: str) -> None:
        with self._conexion:
            self._conexion.execute(
                "UPDATE sesiones SET instantanea_ruta = ? WHERE id = ?",
                (ruta, sesion_id),
            )

    def sesion_abierta_operador(self, operador_id: int) -> Sesion | None:
        fila = self._una(
            "SELECT * FROM sesiones WHERE operador_id = ? AND estado = 'abierta'",
            (operador_id,),
        )
        return self._fila_sesion(fila) if fila else None

    def sesion_por_id(self, sesion_id: int) -> Sesion | None:
        fila = self._una("SELECT * FROM sesiones WHERE id = ?", (sesion_id,))
        if not fila:
            return None
        sesion = self._fila_sesion(fila)
        return self._con_exportaciones(sesion)

    def _fila_sesion(self, fila: sqlite3.Row) -> Sesion:
        return Sesion(
            id=int(fila["id"]),
            operador_id=int(fila["operador_id"]),
            operador_nombre=str(fila["operador_nombre"]),
            operador_cedula=str(fila["operador_cedula"]),
            codigo_id=int(fila["codigo_id"]) if fila["codigo_id"] else None,
            estado=str(fila["estado"]),
            inicio_en=desde_iso(fila["inicio_en"]),
            fin_en=desde_iso(fila["fin_en"]),
            maestro_nombre=str(fila["maestro_nombre"]),
            maestro_ruta=str(fila["maestro_ruta"]),
            maestro_hash=str(fila["maestro_hash"]),
            instantanea_ruta=fila["instantanea_ruta"],
            calibracion_codigo=str(fila["calibracion_codigo"]),
            calibracion_en=desde_iso(fila["calibracion_en"]),
            autorizado_por=fila["autorizado_por"],
            metodo_autorizacion=fila["metodo_autorizacion"],
        )

    def _con_exportaciones(self, sesion: Sesion) -> Sesion:
        filas = self._todas(
            "SELECT tipo, ruta, tamano_bytes FROM exportaciones WHERE sesion_id = ?",
            (sesion.id,),
        )
        exportaciones = tuple(
            ArchivoGenerado(
                tipo=fila["tipo"],
                ruta=Path(fila["ruta"]),
                tamano_bytes=int(fila["tamano_bytes"]),
            )
            for fila in filas
        )
        return Sesion(
            **{
                **sesion.__dict__,
                "exportaciones": exportaciones,
            }
        )

    def finalizar_sesion(
        self,
        sesion_id: int,
        *,
        fin_en: str,
        autorizado_por: str,
        metodo_autorizacion: str,
    ) -> None:
        with self.transaccion() as conexion:
            fila = conexion.execute(
                "SELECT estado FROM sesiones WHERE id = ?", (sesion_id,)
            ).fetchone()
            if fila is None:
                raise ErrorBaseDatos("La sesión no existe.")
            if fila["estado"] != "abierta":
                raise ErrorBaseDatos("La sesión ya fue finalizada.")
            conexion.execute(
                """
                UPDATE sesiones
                   SET estado = 'finalizada', fin_en = ?,
                       autorizado_por = ?, metodo_autorizacion = ?
                 WHERE id = ?
                """,
                (fin_en, autorizado_por, metodo_autorizacion, sesion_id),
            )

    def finalizar_sesion_con_exportaciones(
        self,
        *,
        sesion_id: int,
        fin_en: str,
        autorizado_por: str,
        metodo_autorizacion: str,
        archivos: Sequence[ArchivoGenerado],
    ) -> None:
        """Cierra la sesión y registra sus archivos en una sola transacción."""

        with self.transaccion() as conexion:
            fila = conexion.execute(
                "SELECT estado FROM sesiones WHERE id = ?", (sesion_id,)
            ).fetchone()
            if fila is None:
                raise ErrorBaseDatos("La sesión no existe.")
            if fila["estado"] != "abierta":
                raise ErrorBaseDatos("La sesión ya fue finalizada.")
            conexion.execute(
                """
                UPDATE sesiones
                   SET estado = 'finalizada', fin_en = ?,
                       autorizado_por = ?, metodo_autorizacion = ?
                 WHERE id = ?
                """,
                (fin_en, autorizado_por, metodo_autorizacion, sesion_id),
            )
            for archivo in archivos:
                conexion.execute(
                    """
                    INSERT INTO exportaciones
                        (sesion_id, tipo, nombre_archivo, ruta, tamano_bytes, creado_en)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sesion_id,
                        archivo.tipo,
                        archivo.ruta.name,
                        str(archivo.ruta),
                        archivo.tamano_bytes,
                        fin_en,
                    ),
                )

    def listar_sesiones(self, limite: int = 200) -> list[dict[str, Any]]:
        filas = self._todas(
            """
            SELECT s.*,
                   (SELECT COUNT(*) FROM registros r WHERE r.sesion_id = s.id)
                       AS total_registrados,
                   (SELECT COUNT(*) FROM lecturas l
                     WHERE l.sesion_id = s.id AND l.resultado = 'duplicado')
                       AS total_duplicados,
                   (SELECT COUNT(*) FROM lecturas l
                     WHERE l.sesion_id = s.id AND l.resultado = 'no_encontrado')
                       AS total_no_encontrados,
                   (SELECT COUNT(*) FROM exportaciones e WHERE e.sesion_id = s.id)
                       AS total_archivos
              FROM sesiones s
             ORDER BY s.inicio_en DESC
             LIMIT ?
            """,
            (limite,),
        )
        return [dict(fila) for fila in filas]

    # ------------------------------------------------------------------
    # Lecturas y registros
    # ------------------------------------------------------------------
    def obtener_registro_por_clave(
        self, sesion_id: int, codigo_clave: str
    ) -> RegistroSesion | None:
        fila = self._una(
            """
            SELECT r.*, a.stock_original AS ajuste_stock_original,
                   a.stock_nuevo AS ajuste_stock_nuevo,
                   a.diferencia AS ajuste_diferencia,
                   a.creado_en AS ajuste_creado_en
              FROM registros r
              LEFT JOIN ajustes_stock a ON a.registro_id = r.id
             WHERE r.sesion_id = ? AND r.codigo_clave = ?
            """,
            (sesion_id, codigo_clave),
        )
        return self._fila_registro(fila) if fila else None

    def registrar_lectura(
        self,
        *,
        sesion_id: int,
        codigo_ingresado: str,
        codigo_clave: str,
        resultado: str,
        producto_codigo: str = "",
        descripcion: str = "",
        datos: dict[str, str] | None = None,
        creado_en: str,
        operador_nombre: str | None = None,
        operador_cedula: str | None = None,
        origen: str = "lector",
        novedad: str = "",
    ) -> tuple[int, RegistroSesion | None]:
        """Guarda el evento y, si corresponde, el producto, de forma atómica."""

        datos_json = json.dumps(datos or {}, ensure_ascii=False)
        try:
            with self.transaccion() as conexion:
                estado = conexion.execute(
                    "SELECT estado, operador_nombre, operador_cedula "
                    "FROM sesiones WHERE id = ?",
                    (sesion_id,),
                ).fetchone()
                if estado is None:
                    raise ErrorBaseDatos("La sesión no existe.")
                if estado["estado"] != "abierta":
                    raise ErrorBaseDatos("La sesión ya está cerrada.")
                nombre = operador_nombre or estado["operador_nombre"]
                cedula = operador_cedula or estado["operador_cedula"]

                cur = conexion.execute(
                    """
                    INSERT INTO lecturas
                        (sesion_id, codigo_ingresado, codigo_clave, resultado,
                         producto_codigo, descripcion, datos_json, creado_en)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sesion_id,
                        codigo_ingresado,
                        codigo_clave,
                        resultado,
                        producto_codigo,
                        descripcion,
                        datos_json,
                        creado_en,
                    ),
                )
                lectura_id = int(cur.lastrowid)
                registro: RegistroSesion | None = None
                if resultado == "registrado":
                    try:
                        cur_reg = conexion.execute(
                            """
                            INSERT INTO registros
                                (sesion_id, lectura_id, codigo, codigo_clave,
                                 descripcion, datos_json, escaneado_en,
                                 operador_nombre, operador_cedula, origen, novedad)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                sesion_id,
                                lectura_id,
                                producto_codigo,
                                codigo_clave,
                                descripcion,
                                datos_json,
                                creado_en,
                                nombre,
                                cedula,
                                origen,
                                novedad or None,
                            ),
                        )
                    except sqlite3.IntegrityError as exc:
                        raise ErrorBaseDatos(
                            "El producto ya estaba registrado en esta sesión."
                        ) from exc
                    registro = RegistroSesion(
                        id=int(cur_reg.lastrowid),
                        sesion_id=sesion_id,
                        codigo=producto_codigo,
                        codigo_clave=codigo_clave,
                        descripcion=descripcion,
                        campos=datos or {},
                        escaneado_en=desde_iso(creado_en),
                        operador_nombre=nombre,
                        operador_cedula=cedula,
                        origen=origen,
                        novedad=novedad or "",
                    )
                return lectura_id, registro
        except sqlite3.Error as exc:
            raise ErrorBaseDatos(f"No se pudo guardar la lectura: {exc}") from exc

    def _fila_registro(self, fila: sqlite3.Row) -> RegistroSesion:
        try:
            datos = json.loads(fila["datos_json"])
        except (TypeError, ValueError):
            datos = {}
        claves = set(fila.keys())
        stock_original = fila["ajuste_stock_original"] if "ajuste_stock_original" in claves else None
        stock_nuevo = fila["ajuste_stock_nuevo"] if "ajuste_stock_nuevo" in claves else None
        diferencia = fila["ajuste_diferencia"] if "ajuste_diferencia" in claves else None
        ajuste_en = fila["ajuste_creado_en"] if "ajuste_creado_en" in claves else None
        return RegistroSesion(
            id=int(fila["id"]),
            sesion_id=int(fila["sesion_id"]),
            codigo=str(fila["codigo"]),
            codigo_clave=str(fila["codigo_clave"]),
            descripcion=str(fila["descripcion"] or ""),
            campos={str(k): str(v) for k, v in datos.items()},
            escaneado_en=desde_iso(fila["escaneado_en"]),
            operador_nombre=str(fila["operador_nombre"]),
            operador_cedula=str(fila["operador_cedula"]),
            stock_original=float(stock_original) if stock_original is not None else None,
            stock_nuevo=float(stock_nuevo) if stock_nuevo is not None else None,
            stock_diferencia=float(diferencia) if diferencia is not None else None,
            ajuste_stock_en=desde_iso(ajuste_en),
            origen=str(fila["origen"] or "lector") if "origen" in claves else "lector",
            novedad=str(fila["novedad"] or "") if "novedad" in claves else "",
        )

    def listar_registros(
        self, sesion_id: int, *, descendente: bool = False
    ) -> list[RegistroSesion]:
        orden = "DESC" if descendente else "ASC"
        filas = self._todas(
            f"""
            SELECT r.*, a.stock_original AS ajuste_stock_original,
                   a.stock_nuevo AS ajuste_stock_nuevo,
                   a.diferencia AS ajuste_diferencia,
                   a.creado_en AS ajuste_creado_en
              FROM registros r
              LEFT JOIN ajustes_stock a ON a.registro_id = r.id
             WHERE r.sesion_id = ?
             ORDER BY r.escaneado_en {orden}, r.id {orden}
            """,
            (sesion_id,),
        )
        return [self._fila_registro(fila) for fila in filas]

    def ultimo_registro(self, sesion_id: int) -> RegistroSesion | None:
        fila = self._una(
            """
            SELECT r.*, a.stock_original AS ajuste_stock_original,
                   a.stock_nuevo AS ajuste_stock_nuevo,
                   a.diferencia AS ajuste_diferencia,
                   a.creado_en AS ajuste_creado_en
              FROM registros r
              LEFT JOIN ajustes_stock a ON a.registro_id = r.id
             WHERE r.sesion_id = ?
             ORDER BY r.escaneado_en DESC, r.id DESC
             LIMIT 1
            """,
            (sesion_id,),
        )
        return self._fila_registro(fila) if fila else None

    def guardar_ajuste_stock(
        self,
        *,
        sesion_id: int,
        registro_id: int,
        codigo: str,
        stock_original: float | None,
        stock_nuevo: float,
        diferencia: float | None,
        operador_nombre: str,
        operador_cedula: str,
    ) -> None:
        ahora = a_iso(datetime.now().astimezone())
        with self.transaccion() as conexion:
            sesion = conexion.execute(
                "SELECT estado FROM sesiones WHERE id = ?", (sesion_id,)
            ).fetchone()
            if sesion is None:
                raise ErrorBaseDatos("La sesión no existe.")
            if sesion["estado"] != "abierta":
                raise ErrorBaseDatos("La sesión ya está cerrada.")
            registro = conexion.execute(
                "SELECT 1 FROM registros WHERE id = ? AND sesion_id = ?",
                (registro_id, sesion_id),
            ).fetchone()
            if registro is None:
                raise ErrorBaseDatos("El registro no pertenece a la sesión.")
            conexion.execute(
                """
                INSERT INTO ajustes_stock
                    (sesion_id, registro_id, codigo, stock_original, stock_nuevo,
                     diferencia, operador_nombre, operador_cedula, creado_en,
                     actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(registro_id) DO UPDATE SET
                    stock_original = excluded.stock_original,
                    stock_nuevo = excluded.stock_nuevo,
                    diferencia = excluded.diferencia,
                    operador_nombre = excluded.operador_nombre,
                    operador_cedula = excluded.operador_cedula,
                    actualizado_en = excluded.actualizado_en
                """,
                (
                    sesion_id,
                    registro_id,
                    codigo,
                    stock_original,
                    stock_nuevo,
                    diferencia,
                    operador_nombre,
                    operador_cedula,
                    ahora,
                    ahora,
                ),
            )

    def eliminar_ajuste_stock(self, registro_id: int) -> bool:
        with self.transaccion() as conexion:
            cur = conexion.execute(
                "DELETE FROM ajustes_stock WHERE registro_id = ?",
                (registro_id,),
            )
            return cur.rowcount > 0

    def listar_ajustes_stock(self, sesion_id: int) -> list[dict[str, Any]]:
        filas = self._todas(
            """
            SELECT * FROM ajustes_stock
             WHERE sesion_id = ?
             ORDER BY actualizado_en DESC, id DESC
            """,
            (sesion_id,),
        )
        return [dict(fila) for fila in filas]

    def deshacer_ultimo(self, sesion_id: int) -> RegistroSesion | None:
        with self.transaccion() as conexion:
            fila = conexion.execute(
                """
                SELECT * FROM registros
                 WHERE sesion_id = ?
                 ORDER BY escaneado_en DESC, id DESC
                 LIMIT 1
                """,
                (sesion_id,),
            ).fetchone()
            if fila is None:
                return None
            lectura_id = fila["lectura_id"]
            conexion.execute("DELETE FROM registros WHERE id = ?", (fila["id"],))
            if lectura_id:
                conexion.execute(
                    """
                    DELETE FROM lecturas
                     WHERE id = ? AND resultado = 'registrado' AND sesion_id = ?
                    """,
                    (lectura_id, sesion_id),
                )
            return self._fila_registro(fila)

    def estadisticas_sesion(self, sesion_id: int) -> EstadisticasSesion:
        fila = self._una(
            """
            SELECT
                (SELECT COUNT(*) FROM registros WHERE sesion_id = ?) AS registrados,
                (SELECT COUNT(*) FROM lecturas
                  WHERE sesion_id = ? AND resultado = 'duplicado') AS duplicados,
                (SELECT COUNT(*) FROM lecturas
                  WHERE sesion_id = ? AND resultado = 'no_encontrado')
                    AS no_encontrados,
                (SELECT MAX(creado_en) FROM lecturas WHERE sesion_id = ?)
                    AS ultima_lectura,
                (SELECT COUNT(*) FROM ajustes_stock WHERE sesion_id = ?)
                    AS ajustes_stock,
                (SELECT COUNT(*) FROM registros
                  WHERE sesion_id = ? AND origen = 'manual') AS manuales
            """,
            (sesion_id, sesion_id, sesion_id, sesion_id, sesion_id, sesion_id),
        )
        return EstadisticasSesion(
            registrados=int(fila["registrados"] or 0),
            duplicados=int(fila["duplicados"] or 0),
            no_encontrados=int(fila["no_encontrados"] or 0),
            ultima_lectura_en=desde_iso(fila["ultima_lectura"]),
            ajustes_stock=int(fila["ajustes_stock"] or 0),
            manuales=int(fila["manuales"] or 0),
        )

    # ------------------------------------------------------------------
    # Exportaciones
    # ------------------------------------------------------------------
    def registrar_exportaciones(
        self, sesion_id: int, archivos: Sequence[ArchivoGenerado]
    ) -> None:
        ahora = a_iso(datetime.now().astimezone())
        with self.transaccion() as conexion:
            for archivo in archivos:
                conexion.execute(
                    """
                    INSERT INTO exportaciones
                        (sesion_id, tipo, nombre_archivo, ruta, tamano_bytes, creado_en)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sesion_id,
                        archivo.tipo,
                        archivo.ruta.name,
                        str(archivo.ruta),
                        archivo.tamano_bytes,
                        ahora,
                    ),
                )

    def listar_exportaciones(self, sesion_id: int) -> list[ArchivoGenerado]:
        filas = self._todas(
            "SELECT tipo, ruta, tamano_bytes FROM exportaciones WHERE sesion_id = ?",
            (sesion_id,),
        )
        return [
            ArchivoGenerado(
                tipo=fila["tipo"],
                ruta=Path(fila["ruta"]),
                tamano_bytes=int(fila["tamano_bytes"]),
            )
            for fila in filas
        ]

    # ------------------------------------------------------------------
    # Ajustes locales del catálogo
    # ------------------------------------------------------------------
    def listar_ajustes_catalogo(self) -> list[dict[str, Any]]:
        filas = self._todas(
            """
            SELECT * FROM catalogo_ajustes
             ORDER BY actualizado_en DESC, codigo COLLATE NOCASE
            """
        )
        return [dict(fila) for fila in filas]

    def ajuste_catalogo(self, codigo_clave: str) -> dict[str, Any] | None:
        fila = self._una(
            "SELECT * FROM catalogo_ajustes WHERE codigo_clave = ?",
            (codigo_clave,),
        )
        return dict(fila) if fila else None

    def guardar_ajuste_catalogo(
        self,
        *,
        codigo_clave: str,
        codigo: str,
        descripcion: str,
        campos: dict[str, str],
        origen: str,
        estado: str,
        motivo: str | None,
        admin_id: int | None,
        admin_nombre: str | None,
    ) -> None:
        if origen not in {"maestro", "local"}:
            raise ValueError("Origen de ajuste no válido.")
        if estado not in {"activo", "inactivo"}:
            raise ValueError("Estado de ajuste no válido.")
        ahora = a_iso(datetime.now().astimezone())
        datos = json.dumps(campos, ensure_ascii=False)
        with self.transaccion() as conexion:
            conexion.execute(
                """
                INSERT INTO catalogo_ajustes
                    (codigo_clave, codigo, descripcion, campos_json, origen,
                     estado, motivo, admin_id, admin_nombre, creado_en, actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(codigo_clave) DO UPDATE SET
                    codigo = excluded.codigo,
                    descripcion = excluded.descripcion,
                    campos_json = excluded.campos_json,
                    origen = excluded.origen,
                    estado = excluded.estado,
                    motivo = excluded.motivo,
                    admin_id = excluded.admin_id,
                    admin_nombre = excluded.admin_nombre,
                    actualizado_en = excluded.actualizado_en
                """,
                (
                    codigo_clave,
                    codigo,
                    descripcion,
                    datos,
                    origen,
                    estado,
                    motivo,
                    admin_id,
                    admin_nombre,
                    ahora,
                    ahora,
                ),
            )

    def eliminar_ajuste_catalogo(self, codigo_clave: str) -> bool:
        with self.transaccion() as conexion:
            cur = conexion.execute(
                "DELETE FROM catalogo_ajustes WHERE codigo_clave = ?",
                (codigo_clave,),
            )
            return cur.rowcount > 0

    def contar_ajustes_catalogo(self) -> int:
        fila = self._una("SELECT COUNT(*) AS total FROM catalogo_ajustes")
        return int(fila["total"]) if fila else 0

    # ------------------------------------------------------------------
    # Ajustes y respaldos
    # ------------------------------------------------------------------
    def obtener_ajuste(self, clave: str, por_defecto: str | None = None) -> str | None:
        fila = self._una("SELECT valor FROM ajustes WHERE clave = ?", (clave,))
        return str(fila["valor"]) if fila else por_defecto

    def guardar_ajuste(self, clave: str, valor: str) -> None:
        ahora = a_iso(datetime.now().astimezone())
        with self._conexion:
            self._conexion.execute(
                """
                INSERT INTO ajustes(clave, valor, actualizado_en)
                VALUES (?, ?, ?)
                ON CONFLICT(clave) DO UPDATE
                   SET valor = excluded.valor, actualizado_en = excluded.actualizado_en
                """,
                (clave, valor, ahora),
            )

    def respaldar_en(self, carpeta: str | Path) -> Path:
        from .utilidades import fecha_para_archivo

        destino = (
            Path(carpeta)
            / f"respaldo_inventario_{fecha_para_archivo(datetime.now().astimezone())}.db"
        )
        return self.respaldar(destino)

    def copiar_base_cruda(self, destino: str | Path) -> Path:
        """Copia binaria simple; se conserva para utilidades de soporte."""

        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.ruta, destino)
        return destino

    # ------------------------------------------------------------------
    # Consultas de apoyo para pruebas y panel
    # ------------------------------------------------------------------
    def contar(self, tabla: str) -> int:
        tablas = {
            "administradores",
            "operadores",
            "codigos_acceso",
            "sesiones",
            "lecturas",
            "registros",
            "exportaciones",
        }
        if tabla not in tablas:
            raise ValueError("Tabla no permitida.")
        fila = self._una(f"SELECT COUNT(*) AS total FROM {tabla}")
        return int(fila["total"]) if fila else 0
