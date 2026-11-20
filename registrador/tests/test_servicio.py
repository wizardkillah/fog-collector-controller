import pytest
from conftest import cfg_prueba, lectura

from niebla import mapa
from niebla.config import PlcCfg
from niebla.db import Db
from niebla.plc import ErrorPlc
from niebla.servicio import Servicio
from niebla.sim import PlcSimulado


def servicio_sim(**kw):
    cfg = cfg_prueba()
    plc = PlcSimulado(PlcCfg("principal", "-", 502, [1, 2]), calma_s=30, **kw)
    return Servicio(cfg, [plc], Db(":memory:", simulado=True), registro_s=0), plc


def test_orden_se_entrega_y_se_confirma():
    srv, plc = servicio_sim()
    srv.paso(0)
    srv.encolar_orden(1, mapa.Orden.RESGUARDAR)
    srv.paso(1)
    srv.paso(2)
    o = srv.db.consulta("SELECT * FROM ordenes")
    assert len(o) == 1 and o[0]["confirmada"] == 1 and o[0]["plc_seq"] == 1


def test_orden_a_banco_inexistente_se_rechaza():
    srv, _ = servicio_sim()
    with pytest.raises(ValueError):
        srv.encolar_orden(7, mapa.Orden.HABILITAR)


def test_viento_fuerte_resguarda_y_queda_en_eventos():
    srv, plc = servicio_sim()
    for i in range(40):
        srv.paso(i)
    assert any(b.estado == mapa.Estado.CAPTANDO for b in srv.ultimo["principal"].bancos)
    plc.forzar_viento = 50
    for i in range(40, 60):
        srv.paso(i)
    assert all(b.estado == mapa.Estado.RESGUARDADO for b in srv.ultimo["principal"].bancos)
    tipos = {e["tipo"] for e in srv.db.eventos(500)}
    assert {"VIENTO", "ESTADO"} <= tipos


class PlcCaido:
    nombre = "principal"
    bancos = [1, 2]

    def leer(self):
        raise ErrorPlc("sin conexión")

    def leer_retencion(self, d, n):
        raise ErrorPlc("sin conexión")

    def escribir(self, d, v):
        raise ErrorPlc("sin conexión")

    def cerrar(self):
        pass


def test_enlace_perdido_se_registra_una_vez():
    cfg = cfg_prueba(modo="campo")
    srv = Servicio(cfg, [PlcCaido()], Db(":memory:", simulado=False), registro_s=0)
    for i in range(5):
        srv.paso(i)
    enlace = [e for e in srv.db.eventos() if e["tipo"] == "ENLACE"]
    assert len(enlace) == 1 and enlace[0]["severidad"] == "critico"
    assert not srv.enlace_ok["principal"]


class PlcFijo:
    nombre = "principal"
    bancos = [1, 2]

    def __init__(self, l):
        self.l = l
        self.hr = [0] * mapa.HR_TOTAL

    def leer(self):
        return self.l

    def leer_retencion(self, d, n):
        return self.hr[d:d + n]

    def escribir(self, d, v):
        self.hr[d:d + len(v)] = v

    def cerrar(self):
        pass


def test_dato_simulado_no_entra_en_servicio_de_campo():
    cfg = cfg_prueba(modo="campo")
    srv = Servicio(cfg, [PlcFijo(lectura(simulado=True))], Db(":memory:", simulado=False))
    with pytest.raises(RuntimeError):
        srv.paso(0)


def test_litros_solo_en_bancos_calibrados():
    cfg = cfg_prueba(modo="campo")
    l = lectura()
    plc = PlcFijo(l)
    srv = Servicio(cfg, [plc], Db(":memory:", simulado=False), registro_s=0)
    srv.paso(0)
    l.bancos[0].balancin = 20
    l.bancos[1].balancin = 20
    srv.paso(1)
    filas = srv.db.consulta("SELECT banco, pulsos_delta, litros_delta FROM bancos WHERE pulsos_delta > 0")
    d = {f["banco"]: f for f in filas}
    assert d[1]["litros_delta"] == 1.0
    assert d[2]["litros_delta"] is None
