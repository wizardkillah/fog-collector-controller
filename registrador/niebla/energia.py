"""Lectura opcional del controlador solar (EPEVER Tracer AN, Modbus RTU por USB-RS485).

Registro 0x331A: tensión de batería en V x100 (hoja de protocolo EPEVER).
Confirmar con el modelo instalado antes de usar en campo.
"""
from __future__ import annotations

from .config import EnergiaCfg

REG_TENSION_BATERIA = 0x331A


def lector_epever(cfg: EnergiaCfg):
    from pymodbus.client import ModbusSerialClient

    cli = ModbusSerialClient(port=cfg.puerto, baudrate=115200, bytesize=8, parity="N", stopbits=1, timeout=1)

    def leer() -> float:
        if not cli.connected and not cli.connect():
            raise OSError(f"sin conexión con el controlador solar en {cfg.puerto}")
        r = cli.read_input_registers(REG_TENSION_BATERIA, count=1, device_id=cfg.direccion)
        if r.isError():
            raise OSError(f"error de lectura EPEVER: {r}")
        return r.registers[0] / 100

    return leer
