from conftest import TOKEN, cfg_prueba

from niebla.api import crear_app
from niebla.config import PlcCfg
from niebla.db import Db
from niebla.servicio import Servicio
from niebla.sim import PlcSimulado

AUT = {"Authorization": f"Bearer {TOKEN}"}


def cliente():
    srv = Servicio(cfg_prueba(), [PlcSimulado(PlcCfg("principal", "-", 502, [1, 2]))],
                   Db(":memory:", simulado=True), registro_s=0)
    srv.paso(0)
    srv.paso(1)
    return crear_app(srv, TOKEN).test_client(), srv


def test_sin_token_401():
    c, _ = cliente()
    assert c.get("/api/estado").status_code == 401
    assert c.get("/api/estado", headers={"Authorization": "Bearer malo"}).status_code == 401
    assert c.get("/salud").status_code == 200


def test_estado_indica_simulacion_y_no_tiene_cors():
    c, _ = cliente()
    r = c.get("/api/estado", headers=AUT)
    assert r.status_code == 200
    assert r.json["simulacion"] is True
    assert "Access-Control-Allow-Origin" not in r.headers
    assert r.json["plcs"]["principal"]["lectura"]["bancos"][0]["estado"] == "RESGUARDADO"


def test_orden_validada():
    c, srv = cliente()
    assert c.post("/api/orden", json={"banco": 1, "orden": "RESGUARDAR"}, headers=AUT).status_code == 202
    assert c.post("/api/orden", json={"banco": 1, "orden": "rm -rf"}, headers=AUT).status_code == 400
    assert c.post("/api/orden", json={"banco": "1; import os", "orden": "HABILITAR"}, headers=AUT).status_code == 400
    assert c.post("/api/orden", json={"banco": 9, "orden": "HABILITAR"}, headers=AUT).status_code == 400
    assert c.post("/api/orden", data="x" * 10000, headers=AUT).status_code in (400, 413)
    srv.paso(2)
    assert srv.db.consulta("SELECT COUNT(*) n FROM ordenes")[0]["n"] == 1


def test_exportar_csv_marca_simulacion():
    c, _ = cliente()
    r = c.get("/api/exportar/bancos.csv", headers=AUT)
    assert r.status_code == 200
    texto = r.data.decode()
    assert "SIMULACIÓN" in texto
    assert texto.splitlines()[4].startswith("ts,banco,simulado")
    assert c.get("/api/exportar/eventos.csv", headers=AUT).status_code == 404
    assert c.get("/api/exportar/bancos.csv?desde=2026-13-01", headers=AUT).status_code == 400
