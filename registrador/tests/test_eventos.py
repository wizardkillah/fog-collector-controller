from conftest import lectura

from niebla import mapa
from niebla.eventos import Captacion, comparar


def tipos(evs):
    return [(e.tipo, e.severidad) for e in evs]


def test_cambio_de_estado_y_falla():
    a = lectura()
    b = lectura(motivo=mapa.Motivo.RAFAGA)
    b.bancos[0].estado = mapa.Estado.FALLA
    b.bancos[0].fallas = mapa.Falla.TIEMPO_RESGUARDO
    evs = comparar(a, b)
    assert ("ESTADO", "critico") in tipos(evs)
    assert ("FALLA", "critico") in tipos(evs)
    assert ("VIENTO", "aviso") in tipos(evs)


def test_sensor_de_viento_perdido_y_recuperado():
    a = lectura()
    b = lectura(motivo=mapa.Motivo.VIENTO_SIN_DATO, viento_valido=False)
    assert ("SENSOR_VIENTO", "critico") in tipos(comparar(a, b))
    assert ("SENSOR_VIENTO", "info") in tipos(comparar(b, a))


def test_reinicio_y_rebalse():
    evs = comparar(lectura(uptime_s=500), lectura(uptime_s=3, flotador_alto=True))
    assert ("REINICIO_PLC", "aviso") in tipos(evs)
    assert ("REBALSE", "aviso") in tipos(evs)


def test_captacion_calibrada_y_reinicio_de_contador():
    c = Captacion(ml_por_pulso=50)
    assert c.actualizar(100) == (0, False)      # primera lectura: referencia
    assert c.actualizar(110) == (10, False)
    assert c.actualizar(4) == (4, True)         # el PLC se reinició
    assert c.tomar() == (14, 0.7)
    assert c.tomar() == (0, 0.0)


def test_captacion_sin_calibrar_no_informa_litros():
    c = Captacion(ml_por_pulso=None)
    c.actualizar(0)
    c.actualizar(20)
    assert c.tomar() == (20, None)
