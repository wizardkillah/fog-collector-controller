"""Comunicación con los PLC por Modbus TCP.

El registrador es el ÚNICO proceso que habla con los PLC (un solo dueño de la
comunicación). La API web no abre conexiones propias: encola órdenes que el
servicio entrega en su próximo ciclo.
"""
from __future__ import annotations

import logging
from typing import Protocol

from . import mapa
from .config import PlcCfg

log = logging.getLogger(__name__)

UNIDAD = 255  # identificador de unidad Modbus TCP del Opta


class ErrorPlc(RuntimeError):
    pass


class PlcCliente(Protocol):
    nombre: str
    bancos: list[int]

    def leer(self) -> mapa.LecturaPlc: ...
    def escribir(self, direccion: int, valores: list[int]) -> None: ...
    def leer_retencion(self, direccion: int, cantidad: int) -> list[int]: ...
    def cerrar(self) -> None: ...


class ModbusPlc:
    def __init__(self, cfg: PlcCfg, timeout: float = 2.0):
        from pymodbus.client import ModbusTcpClient

        self.nombre = cfg.nombre
        self.bancos = list(cfg.bancos)
        self._cli = ModbusTcpClient(cfg.host, port=cfg.puerto, timeout=timeout, retries=1)

    def _conectar(self) -> None:
        if not self._cli.connected and not self._cli.connect():
            raise ErrorPlc(f"{self.nombre}: sin conexión")

    def leer(self) -> mapa.LecturaPlc:
        self._conectar()
        r = self._cli.read_input_registers(0, count=mapa.IR_TOTAL, device_id=UNIDAD)
        if r.isError():
            raise ErrorPlc(f"{self.nombre}: error de lectura {r}")
        return mapa.decodificar(list(r.registers), n_bancos=len(self.bancos))

    def leer_retencion(self, direccion: int, cantidad: int) -> list[int]:
        self._conectar()
        r = self._cli.read_holding_registers(direccion, count=cantidad, device_id=UNIDAD)
        if r.isError():
            raise ErrorPlc(f"{self.nombre}: error de lectura {r}")
        return list(r.registers)

    def escribir(self, direccion: int, valores: list[int]) -> None:
        self._conectar()
        r = self._cli.write_registers(direccion, [v & 0xFFFF for v in valores], device_id=UNIDAD)
        if r.isError():
            raise ErrorPlc(f"{self.nombre}: error de escritura {r}")

    def cerrar(self) -> None:
        self._cli.close()


# ---------------------------------------------------------------- órdenes y datos
class Secuenciador:
    """Emite órdenes al PLC incrementando un número de secuencia.

    El PLC ejecuta la orden una sola vez por cada valor nuevo y devuelve el eco
    en IR_ORDEN_APLICADA, lo que permite confirmar la entrega.
    """

    def __init__(self, plc: PlcCliente):
        self.plc = plc
        self._seq: int | None = None

    def _siguiente(self, reg_seq: int) -> int:
        actual = self.plc.leer_retencion(reg_seq, 1)[0]
        return (actual + 1) & 0xFFFF or 1

    def orden(self, banco: int, orden: mapa.Orden) -> int:
        seq = self._siguiente(mapa.HR_ORDEN_SEQ)
        # Se escriben banco y código primero y la secuencia al final (un solo bloque).
        self.plc.escribir(mapa.HR_ORDEN_SEQ, [seq, banco, int(orden)])
        return seq

    def bateria(self, volt: float) -> None:
        seq = self._siguiente(mapa.HR_BATERIA_SEQ)
        self.plc.escribir(mapa.HR_BATERIA_MV, [round(volt * 1000), seq])

    def parametros(self, rafaga_kmh: float, medio_kmh: float, rehab_kmh: float, calma_min: int) -> None:
        seq = self._siguiente(mapa.HR_PARAM_SEQ)
        self.plc.escribir(
            mapa.HR_PARAM_RAFAGA,
            [round(rafaga_kmh * 10), round(medio_kmh * 10), round(rehab_kmh * 10), int(calma_min), seq],
        )

    def latido(self, n: int) -> None:
        self.plc.escribir(mapa.HR_LATIDO, [n & 0xFFFF])
