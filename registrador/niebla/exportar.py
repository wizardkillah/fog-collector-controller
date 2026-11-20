"""Exportación de registros a CSV con metadatos y unidades."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from .db import Db, ahora

COLUMNAS_MED = [
    ("ts", "UTC ISO-8601"), ("plc", ""), ("simulado", "0/1"),
    ("viento_inst_kmh", "km/h"), ("viento_rafaga_kmh", "km/h (3 s)"), ("viento_medio_kmh", "km/h (10 min)"),
    ("viento_dir", "grados"), ("viento_valido", "0/1"), ("motivo", "bitmask"),
    ("lluvia_mm", "mm acumulados del pluviómetro"), ("nivel_mm", "mm"), ("flotador_alto", "0/1"),
    ("temp_c", "°C"), ("hr_pct", "%"), ("bateria_v", "V"), ("permiso", "0/1"), ("uptime_s", "s"),
]
COLUMNAS_BAN = [
    ("ts", "UTC ISO-8601"), ("banco", ""), ("simulado", "0/1"), ("estado", ""), ("fallas", "bitmask"),
    ("balancin", "cuenta acumulada"), ("maniobras", "cuenta acumulada"), ("pulsos_delta", "pulsos"),
    ("litros_delta", "L (vacío = sin calibrar)"),
]


def _rango(desde: date, hasta: date) -> tuple[str, str]:
    """Rango [desde, hasta] en días UTC, como cadenas comparables con `ts`."""
    return desde.isoformat(), (hasta + timedelta(days=1)).isoformat()


def csv_tabla(db: Db, tabla: str, desde: date, hasta: date, sitio: str) -> str:
    cols = COLUMNAS_MED if tabla == "mediciones" else COLUMNAS_BAN
    if tabla not in ("mediciones", "bancos"):
        raise ValueError("tabla no exportable")
    a, b = _rango(desde, hasta)
    filas = db.consulta(f"SELECT * FROM {tabla} WHERE ts >= ? AND ts < ? ORDER BY seq", (a, b))
    out = io.StringIO()
    out.write(f"# Niebla — {sitio}\n")
    out.write(f"# tabla: {tabla} | desde {desde} hasta {hasta} | generado {ahora()}\n")
    modo = "SIMULACIÓN — no son mediciones" if db.simulado else "campo"
    out.write(f"# modo: {modo}\n")
    out.write("# unidades: " + "; ".join(f"{c}={u}" for c, u in cols if u) + "\n")
    w = csv.writer(out)
    w.writerow([c for c, _ in cols])
    for f in filas:
        w.writerow(["" if f[c] is None else f[c] for c, _ in cols])
    return out.getvalue()
