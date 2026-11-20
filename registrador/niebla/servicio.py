"""Servicio del registrador: sondea los PLC, registra y entrega órdenes.

No toma decisiones de seguridad: esas viven en el PLC. Si este servicio se
detiene, el PLC sigue protegiendo la malla por sí mismo.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass

from . import mapa
from .config import Config
from .db import Db
from .eventos import Captacion, comparar
from .plc import ErrorPlc, PlcCliente, Secuenciador

log = logging.getLogger(__name__)


@dataclass
class OrdenPendiente:
    banco: int          # 0 = todos
    orden: mapa.Orden
    origen: str


class Servicio:
    def __init__(self, cfg: Config, plcs: list[PlcCliente], db: Db, registro_s: float = 60.0,
                 lector_bateria=None):
        self.cfg = cfg
        self.plcs = plcs
        self.db = db
        self.registro_s = registro_s
        self.lector_bateria = lector_bateria
        self.ultimo: dict[str, mapa.LecturaPlc] = {}
        self.enlace_ok: dict[str, bool] = {p.nombre: True for p in plcs}
        self._sec = {p.nombre: Secuenciador(p) for p in plcs}
        self._cap = {b: Captacion(cfg.bancos[b].ml_por_pulso) for p in plcs for b in p.bancos}
        self._t_registro = 0.0
        self._t_bateria = 0.0
        self._latido = 0
        self._ordenes: queue.Queue[OrdenPendiente] = queue.Queue()
        self._parar = threading.Event()

    # -------------------------------------------------------------- API interna
    def encolar_orden(self, banco: int, orden: mapa.Orden, origen: str = "api") -> None:
        validos = {0} | {b for p in self.plcs for b in p.bancos}
        if banco not in validos:
            raise ValueError(f"banco {banco} no existe")
        self._ordenes.put(OrdenPendiente(banco, orden, origen))

    def detener(self) -> None:
        self._parar.set()

    # -------------------------------------------------------------- ciclo
    def correr(self) -> None:
        log.info("registrador iniciado (%s, modo %s)", self.cfg.nombre, self.cfg.modo)
        self.db.evento("SERVICIO", "info", f"registrador iniciado en modo {self.cfg.modo}")
        while not self._parar.is_set():
            t0 = time.monotonic()
            self.paso(t0)
            self._parar.wait(max(0.0, self.cfg.intervalo_s - (time.monotonic() - t0)))
        self.db.evento("SERVICIO", "info", "registrador detenido")

    def paso(self, t: float) -> None:
        registrar = (t - self._t_registro) >= self.registro_s
        if registrar:
            self._t_registro = t
        self._latido += 1
        for plc in self.plcs:
            self._sondear(plc, registrar)
        self._entregar_ordenes()
        if self.lector_bateria and (t - self._t_bateria) >= 60:
            self._t_bateria = t
            self._reenviar_bateria()

    def _sondear(self, plc: PlcCliente, registrar: bool) -> None:
        try:
            lect = plc.leer()
            self._sec[plc.nombre].latido(self._latido)
        except (ErrorPlc, OSError, ValueError) as e:
            if self.enlace_ok.get(plc.nombre, True):
                self.db.evento("ENLACE", "critico", f"{plc.nombre}: sin comunicación ({e}). "
                               "El PLC sigue protegiendo en forma autónoma.")
            self.enlace_ok[plc.nombre] = False
            return
        if not self.enlace_ok.get(plc.nombre, True):
            self.db.evento("ENLACE", "info", f"{plc.nombre}: comunicación restablecida")
        self.enlace_ok[plc.nombre] = True
        if lect.simulado != self.cfg.simulacion:
            raise RuntimeError("una lectura simulada llegó a un servicio de campo (o al revés)")

        for ev in comparar(self.ultimo.get(plc.nombre), lect):
            self.db.evento(ev.tipo, ev.severidad, ev.detalle, ev.banco)
        for b in lect.bancos:
            _, reinicio = self._cap[b.banco].actualizar(b.balancin)
            if reinicio:
                self.db.evento("CAPTACION", "aviso", "contador de balancín reiniciado (reinicio del PLC)", b.banco)
        self.db.confirmar_ordenes(plc.nombre, lect.orden_aplicada)
        self.ultimo[plc.nombre] = lect

        if registrar:
            self.db.medicion(plc.nombre, lect)
            for b in lect.bancos:
                pulsos, litros = self._cap[b.banco].tomar()
                self.db.banco(b, pulsos, litros)

    def _entregar_ordenes(self) -> None:
        while True:
            try:
                o = self._ordenes.get_nowait()
            except queue.Empty:
                return
            for plc in self.plcs:
                if o.banco not in (0, *plc.bancos):
                    continue
                try:
                    seq = self._sec[plc.nombre].orden(o.banco, o.orden)
                except (ErrorPlc, OSError) as e:
                    self.db.evento("ORDEN", "aviso", f"no se pudo entregar {o.orden.name} a {plc.nombre}: {e}", o.banco or None)
                    seq = None
                self.db.orden(o.origen, plc.nombre, o.banco, o.orden.name, seq)

    def _reenviar_bateria(self) -> None:
        try:
            v = self.lector_bateria()
        except Exception as e:  # el lector es opcional y no debe tumbar el servicio
            log.warning("lectura de batería falló: %s", e)
            return
        for plc in self.plcs:
            try:
                self._sec[plc.nombre].bateria(v)
            except (ErrorPlc, OSError):
                pass
