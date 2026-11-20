from conftest import lectura

from niebla import mapa


def test_ida_y_vuelta():
    l = lectura(uptime_s=70000, lluvia_mm=6553.9, nivel_mm=None)
    l.bancos[0].balancin = 123456
    l.bancos[1].maniobras = 70001
    r = mapa.codificar(l)
    assert len(r) == mapa.IR_TOTAL
    assert all(0 <= v <= 0xFFFF for v in r)
    d = mapa.decodificar(r)
    assert d.uptime_s == 70000
    assert d.lluvia_mm == 6553.9
    assert d.nivel_mm is None
    assert d.temp_c == -1.5
    assert d.bancos[0].balancin == 123456
    assert d.bancos[1].maniobras == 70001
    assert d.bancos[0].estado is mapa.Estado.RESGUARDADO


def test_sin_thr_no_inventa_valores():
    r = mapa.codificar(lectura(sensores=0x07))
    d = mapa.decodificar(r)
    assert d.temp_c is None and d.hr_pct is None


def test_nombres_bits():
    m = mapa.Motivo.RAFAGA | mapa.Motivo.CALMA_INSUFICIENTE
    assert mapa.nombres(m) == ["RAFAGA", "CALMA_INSUFICIENTE"]
