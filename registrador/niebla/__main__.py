"""Uso:
    python -m niebla servicio -c /etc/niebla/config.toml
    python -m niebla exportar -c config.toml --tabla bancos --desde 2026-10-01 --hasta 2026-10-31 -o salida.csv
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from datetime import date

from . import config as cfgmod
from .db import Db
from .exportar import csv_tabla


def _plcs(cfg):
    if cfg.simulacion:
        from .sim import PlcSimulado
        return [PlcSimulado(p, paso_s=cfg.intervalo_s) for p in cfg.plcs]
    from .plc import ModbusPlc
    return [ModbusPlc(p) for p in cfg.plcs]


def cmd_servicio(a) -> int:
    from .servicio import Servicio

    cfg = cfgmod.cargar(a.config)
    db = Db(cfg.base_datos, simulado=cfg.simulacion)
    lector = None
    if cfg.energia.habilitada:
        from .energia import lector_epever
        lector = lector_epever(cfg.energia)
    srv = Servicio(cfg, _plcs(cfg), db, registro_s=a.registro_s, lector_bateria=lector)
    signal.signal(signal.SIGTERM, lambda *_: srv.detener())
    if cfg.api.habilitada:
        from werkzeug.serving import make_server
        from .api import crear_app
        http = make_server(cfg.api.host, cfg.api.puerto, crear_app(srv, cfg.api.token), threaded=True)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        logging.info("API en http://%s:%s", cfg.api.host, cfg.api.puerto)
    try:
        srv.correr()
    except KeyboardInterrupt:
        srv.detener()
    return 0


def cmd_exportar(a) -> int:
    cfg = cfgmod.cargar(a.config)
    db = Db(cfg.base_datos, simulado=cfg.simulacion)
    texto = csv_tabla(db, a.tabla, date.fromisoformat(a.desde), date.fromisoformat(a.hasta), cfg.nombre)
    if a.salida == "-":
        sys.stdout.write(texto)
    else:
        with open(a.salida, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="niebla")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("servicio")
    s.add_argument("-c", "--config", required=True)
    s.add_argument("--registro-s", type=float, default=60.0, help="periodo de registro en base de datos")
    s.set_defaults(fn=cmd_servicio)
    e = sub.add_parser("exportar")
    e.add_argument("-c", "--config", required=True)
    e.add_argument("--tabla", choices=["mediciones", "bancos"], default="bancos")
    e.add_argument("--desde", required=True)
    e.add_argument("--hasta", required=True)
    e.add_argument("-o", "--salida", default="-")
    e.set_defaults(fn=cmd_exportar)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
