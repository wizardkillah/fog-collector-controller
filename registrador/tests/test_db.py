import pytest
from conftest import lectura

from niebla.db import Db


def test_no_mezcla_modos(tmp_path):
    ruta = tmp_path / "n.db"
    Db(ruta, simulado=False).cerrar()
    with pytest.raises(RuntimeError):
        Db(ruta, simulado=True)


def test_captacion_diaria_null_sin_calibrar():
    db = Db(":memory:", simulado=False)
    l = lectura()
    db.banco(l.bancos[0], 10, 0.5)
    db.banco(l.bancos[0], 4, 0.2)
    db.banco(l.bancos[1], 7, None)
    filas = {f["banco"]: f for f in db.captacion_diaria(1)}
    assert filas[1]["litros"] == 0.7 and filas[1]["pulsos"] == 14
    assert filas[2]["litros"] is None and filas[2]["pulsos"] == 7


def test_ordenes_se_confirman_por_eco():
    db = Db(":memory:", simulado=False)
    db.orden("api", "principal", 1, "RESGUARDAR", 5)
    assert db.confirmar_ordenes("principal", 4) == 0
    assert db.confirmar_ordenes("principal", 5) == 1
    assert db.consulta("SELECT confirmada FROM ordenes")[0]["confirmada"] == 1
