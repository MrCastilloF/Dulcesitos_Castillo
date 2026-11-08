"""Retroalimentación sonora breve para operaciones de bodega."""

from __future__ import annotations

import logging
import os
import threading

LOG = logging.getLogger(__name__)


class Sonidos:
    """Tonos cortos no bloqueantes (Windows). Se pueden desactivar por entorno."""

    def __init__(self) -> None:
        self.habilitado = (
            os.name == "nt" and os.environ.get("DULCESITOS_SIN_SONIDO", "") != "1"
        )

    def _reproducir(self, secuencia: list[tuple[int, int]]) -> None:
        if not self.habilitado:
            return

        def tarea() -> None:
            try:
                import winsound

                for frecuencia, duracion in secuencia:
                    winsound.Beep(frecuencia, duracion)
            except Exception:
                LOG.debug("No fue posible reproducir el tono", exc_info=True)

        threading.Thread(target=tarea, daemon=True).start()

    def exito(self) -> None:
        self._reproducir([(1046, 55), (1568, 75)])

    def advertencia(self) -> None:
        self._reproducir([(740, 95), (560, 110)])

    def error(self) -> None:
        self._reproducir([(300, 130), (220, 150)])

    def calibracion(self) -> None:
        self._reproducir([(880, 55), (1174, 55), (1568, 95)])
