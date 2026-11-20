"""Integración real por Modbus TCP contra un servidor que imita el mapa del PLC."""
import socket
import threading
import time

import pytest
from conftest import lectura

from niebla import mapa
from niebla.config import PlcCfg
from niebla.plc import ModbusPlc, Secuenciador

pymodbus = pytest.importorskip("pymodbus")


def puerto_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def servidor():
    from pymodbus.datastore import ModbusDeviceContext, ModbusSequentialDataBlock, ModbusServerContext
    from pymodbus.server import ModbusTcpServer
    import asyncio

    regs = mapa.codificar(lectura(uptime_s=1234))
    # pymodbus desplaza en 1 la dirección de los bloques secuenciales
    ctx = ModbusDeviceContext(ir=ModbusSequentialDataBlock(1, regs), hr=ModbusSequentialDataBlock(1, [0] * mapa.HR_TOTAL))
    contexto = ModbusServerContext(devices=ctx, single=True)
    puerto = puerto_libre()
    estado = {}

    async def principal():
        srv = ModbusTcpServer(contexto, address=("127.0.0.1", puerto))
        estado["srv"], estado["bucle"] = srv, asyncio.get_running_loop()
        await srv.serve_forever()

    hilo = threading.Thread(target=lambda: asyncio.run(principal()), daemon=True)
    hilo.start()
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", puerto), timeout=0.1).close()
            break
        except OSError:
            time.sleep(0.05)
    yield puerto, ctx
    estado["bucle"].call_soon_threadsafe(lambda: asyncio.ensure_future(estado["srv"].shutdown()))
    hilo.join(timeout=2)


def test_lectura_y_orden_por_modbus(servidor):
    puerto, ctx = servidor
    plc = ModbusPlc(PlcCfg("principal", "127.0.0.1", puerto, [1, 2]))
    l = plc.leer()
    assert l.uptime_s == 1234
    assert l.bancos[1].banco == 2
    sec = Secuenciador(plc)
    seq = sec.orden(2, mapa.Orden.RESGUARDAR)
    assert seq == 1
    hr = plc.leer_retencion(mapa.HR_ORDEN_SEQ, 3)
    assert hr == [1, 2, int(mapa.Orden.RESGUARDAR)]
    assert sec.orden(0, mapa.Orden.HABILITAR) == 2
    sec.bateria(12.84)
    assert plc.leer_retencion(mapa.HR_BATERIA_MV, 2) == [12840, 1]
    plc.cerrar()
