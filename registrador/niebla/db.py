"""Base de datos local (SQLite, modo WAL).

Reglas de diseño:
  * cada fila lleva `simulado` (0/1) y marca de tiempo UTC ISO-8601;
  * las tablas usan `seq` creciente: sirve de cursor para sincronizar o exportar;
  * los litros sólo se registran si el balancín del banco está calibrado.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import mapa

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mediciones (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  plc TEXT NOT NULL,
  simulado INTEGER NOT NULL,
  viento_inst_kmh REAL, viento_rafaga_kmh REAL, viento_medio_kmh REAL,
  viento_dir INTEGER, viento_valido INTEGER NOT NULL,
  motivo INTEGER NOT NULL,
  lluvia_mm REAL, nivel_mm INTEGER, flotador_alto INTEGER,
  temp_c REAL, hr_pct REAL, bateria_v REAL,
  permiso INTEGER, uptime_s INTEGER
);
CREATE TABLE IF NOT EXISTS bancos (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  banco INTEGER NOT NULL,
  simulado INTEGER NOT NULL,
  estado TEXT NOT NULL,
  fallas INTEGER NOT NULL,
  balancin INTEGER NOT NULL,
  maniobras INTEGER NOT NULL,
  pulsos_delta INTEGER NOT NULL,
  litros_delta REAL             -- NULL si el balancín no está calibrado
);
CREATE TABLE IF NOT EXISTS eventos (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  tipo TEXT NOT NULL,
  severidad TEXT NOT NULL CHECK (severidad IN ('info','aviso','critico')),
  banco INTEGER,
  detalle TEXT NOT NULL,
  simulado INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ordenes (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  origen TEXT NOT NULL,
  plc TEXT NOT NULL,
  banco INTEGER NOT NULL,
  orden TEXT NOT NULL,
  plc_seq INTEGER,
  confirmada INTEGER NOT NULL DEFAULT 0,
  ts_confirmada TEXT
);
CREATE INDEX IF NOT EXISTS ix_med_ts ON mediciones(ts);
CREATE INDEX IF NOT EXISTS ix_ban_ts ON bancos(ts, banco);
CREATE INDEX IF NOT EXISTS ix_eve_ts ON eventos(ts);
"""


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Db:
    def __init__(self, ruta: Path | str, simulado: bool):
        if str(ruta) != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.simulado = int(simulado)
        self._lock = threading.Lock()
        self._c = sqlite3.connect(str(ruta), check_same_thread=False)
        self._c.row_factory = sqlite3.Row
        self._c.execute("PRAGMA journal_mode=WAL")
        self._c.execute("PRAGMA synchronous=NORMAL")
        self._c.executescript(ESQUEMA)
        fila = self._c.execute("SELECT valor FROM meta WHERE clave='modo'").fetchone()
        modo = "simulacion" if simulado else "campo"
        if fila is None:
            self._c.execute("INSERT INTO meta VALUES ('modo', ?)", (modo,))
            self._c.execute("INSERT INTO meta VALUES ('creada', ?)", (ahora(),))
        elif fila["valor"] != modo:
            raise RuntimeError(f"la base es de modo '{fila['valor']}' y el servicio corre en '{modo}'")
        self._c.commit()

    # -------------------------------------------------------------- escritura
    def medicion(self, plc: str, l: mapa.LecturaPlc, ts: str | None = None) -> None:
        with self._lock:
            self._c.execute(
                """INSERT INTO mediciones (ts, plc, simulado, viento_inst_kmh, viento_rafaga_kmh,
                   viento_medio_kmh, viento_dir, viento_valido, motivo, lluvia_mm, nivel_mm,
                   flotador_alto, temp_c, hr_pct, bateria_v, permiso, uptime_s)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ts or ahora(), plc, self.simulado, l.viento_inst_kmh, l.viento_rafaga_kmh,
                 l.viento_medio_kmh, l.viento_dir, int(l.viento_valido), int(l.motivo), l.lluvia_mm,
                 l.nivel_mm, int(l.flotador_alto), l.temp_c, l.hr_pct, l.bateria_v, int(l.permiso),
                 l.uptime_s),
            )
            self._c.commit()

    def banco(self, b: mapa.LecturaBanco, pulsos: int, litros: float | None, ts: str | None = None) -> None:
        with self._lock:
            self._c.execute(
                """INSERT INTO bancos (ts, banco, simulado, estado, fallas, balancin, maniobras,
                   pulsos_delta, litros_delta) VALUES (?,?,?,?,?,?,?,?,?)""",
                (ts or ahora(), b.banco, self.simulado, b.estado.name, int(b.fallas), b.balancin,
                 b.maniobras, pulsos, litros),
            )
            self._c.commit()

    def evento(self, tipo: str, severidad: str, detalle: str, banco: int | None = None, ts: str | None = None) -> None:
        with self._lock:
            self._c.execute(
                "INSERT INTO eventos (ts, tipo, severidad, banco, detalle, simulado) VALUES (?,?,?,?,?,?)",
                (ts or ahora(), tipo, severidad, banco, detalle, self.simulado),
            )
            self._c.commit()

    def orden(self, origen: str, plc: str, banco: int, orden: str, plc_seq: int | None) -> int:
        with self._lock:
            cur = self._c.execute(
                "INSERT INTO ordenes (ts, origen, plc, banco, orden, plc_seq) VALUES (?,?,?,?,?,?)",
                (ahora(), origen, plc, banco, orden, plc_seq),
            )
            self._c.commit()
            return int(cur.lastrowid)

    def confirmar_ordenes(self, plc: str, eco_seq: int) -> int:
        with self._lock:
            cur = self._c.execute(
                "UPDATE ordenes SET confirmada=1, ts_confirmada=? WHERE plc=? AND plc_seq=? AND confirmada=0",
                (ahora(), plc, eco_seq),
            )
            self._c.commit()
            return cur.rowcount

    # -------------------------------------------------------------- lectura
    def consulta(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._c.execute(sql, args).fetchall()]

    def eventos(self, limite: int = 50) -> list[dict]:
        return self.consulta("SELECT * FROM eventos ORDER BY seq DESC LIMIT ?", (limite,))

    def captacion_diaria(self, dias: int = 7) -> list[dict]:
        """Litros por día (hora local del equipo) y banco. NULL = sin calibrar."""
        return self.consulta(
            """SELECT date(ts, 'localtime') AS dia, banco,
                      SUM(pulsos_delta) AS pulsos,
                      CASE WHEN COUNT(litros_delta) = COUNT(*) THEN ROUND(SUM(litros_delta), 2) END AS litros
               FROM bancos WHERE ts >= datetime('now', ?)
               GROUP BY dia, banco ORDER BY dia, banco""",
            (f"-{int(dias)} days",),
        )

    def cerrar(self) -> None:
        with self._lock:
            self._c.close()
