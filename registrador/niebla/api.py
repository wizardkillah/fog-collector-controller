"""Panel y API local del registrador (Flask).

Seguridad por defecto:
  * todas las rutas /api exigen `Authorization: Bearer <token>`;
  * sin CORS: sólo el propio panel puede llamar a la API desde un navegador;
  * las órdenes son una lista cerrada, se validan y se encolan al servicio
    (nunca se ejecuta código ni se abre el PLC desde aquí);
  * el servicio no corre como root (ver systemd/niebla.service).
"""
from __future__ import annotations

import hmac
from dataclasses import asdict
from datetime import date, timedelta

from flask import Flask, Response, abort, jsonify, request

from . import mapa
from .exportar import csv_tabla
from .servicio import Servicio

ORDENES = {"HABILITAR": mapa.Orden.HABILITAR, "RESGUARDAR": mapa.Orden.RESGUARDAR,
           "RECONOCER_FALLA": mapa.Orden.RECONOCER_FALLA}


def _lectura_json(l: mapa.LecturaPlc) -> dict:
    d = asdict(l)
    d["motivo"] = mapa.nombres(l.motivo)
    for b, bd in zip(l.bancos, d["bancos"]):
        bd["estado"] = b.estado.name
        bd["fallas"] = mapa.nombres(b.fallas)
    return d


def crear_app(servicio: Servicio, token: str) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024
    token_b = token.encode()

    @app.before_request
    def autenticar():
        if request.path == "/salud":
            return None
        cab = request.headers.get("Authorization", "")
        if not cab.startswith("Bearer ") or not hmac.compare_digest(cab[7:].encode(), token_b):
            abort(401)
        return None

    @app.after_request
    def cabeceras(resp: Response):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Frame-Options"] = "DENY"
        return resp

    @app.get("/salud")
    def salud():
        return jsonify(ok=True, modo=servicio.cfg.modo)

    @app.get("/api/estado")
    def estado():
        return jsonify(
            sitio=servicio.cfg.nombre,
            modo=servicio.cfg.modo,
            simulacion=servicio.cfg.simulacion,
            plcs={n: {"enlace": servicio.enlace_ok.get(n, False),
                      "lectura": _lectura_json(l)} for n, l in servicio.ultimo.items()},
        )

    @app.get("/api/eventos")
    def eventos():
        limite = min(max(request.args.get("limite", 50, type=int), 1), 500)
        return jsonify(servicio.db.eventos(limite))

    @app.get("/api/captacion")
    def captacion():
        dias = min(max(request.args.get("dias", 7, type=int), 1), 366)
        return jsonify(servicio.db.captacion_diaria(dias))

    @app.get("/api/exportar/<tabla>.csv")
    def exportar(tabla: str):
        if tabla not in ("mediciones", "bancos"):
            abort(404)
        try:
            hasta = date.fromisoformat(request.args.get("hasta", date.today().isoformat()))
            desde = date.fromisoformat(request.args.get("desde", (hasta - timedelta(days=7)).isoformat()))
        except ValueError:
            abort(400)
        if desde > hasta or (hasta - desde).days > 366:
            abort(400)
        cuerpo = csv_tabla(servicio.db, tabla, desde, hasta, servicio.cfg.nombre)
        return Response(cuerpo, mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="niebla_{tabla}_{desde}_{hasta}.csv"'})

    @app.post("/api/orden")
    def orden():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            abort(400)
        nombre = datos.get("orden")
        banco = datos.get("banco")
        if nombre not in ORDENES or not isinstance(banco, int) or isinstance(banco, bool):
            abort(400)
        try:
            servicio.encolar_orden(banco, ORDENES[nombre], origen="api")
        except ValueError:
            abort(400)
        return jsonify(aceptada=True, banco=banco, orden=nombre,
                       nota="El PLC la aplica sólo si es segura; confirmar en /api/eventos"), 202

    return app
