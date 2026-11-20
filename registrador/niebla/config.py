"""Configuración del registrador (archivo TOML)."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PlcCfg:
    nombre: str
    host: str
    puerto: int = 502
    bancos: list[int] = field(default_factory=lambda: [1, 2])


@dataclass
class BancoCfg:
    id: int
    area_m2: float = 18.0
    ml_por_pulso: float | None = None  # None = balancín sin calibrar (no se informan litros)


@dataclass
class EnergiaCfg:
    habilitada: bool = False
    puerto: str = "/dev/ttyUSB0"
    direccion: int = 1


@dataclass
class ApiCfg:
    habilitada: bool = True
    host: str = "127.0.0.1"
    puerto: int = 8080
    token: str | None = None


@dataclass
class Config:
    nombre: str
    modo: str  # "campo" o "simulacion"
    intervalo_s: float
    base_datos: Path
    plcs: list[PlcCfg]
    bancos: dict[int, BancoCfg]
    energia: EnergiaCfg
    api: ApiCfg

    @property
    def simulacion(self) -> bool:
        return self.modo == "simulacion"


def cargar(ruta: str | Path) -> Config:
    with open(ruta, "rb") as f:
        d = tomllib.load(f)
    sitio = d.get("sitio", {})
    modo = sitio.get("modo", "campo")
    if modo not in ("campo", "simulacion"):
        raise ValueError("sitio.modo debe ser 'campo' o 'simulacion'")
    plcs = [PlcCfg(**p) for p in d.get("plc", [])]
    if not plcs:
        raise ValueError("se requiere al menos un [[plc]]")
    bancos = {b["id"]: BancoCfg(**b) for b in d.get("banco", [])}
    for p in plcs:
        for b in p.bancos:
            bancos.setdefault(b, BancoCfg(id=b))
    api = ApiCfg(**d.get("api", {}))
    api.token = os.environ.get("NIEBLA_TOKEN") or api.token
    if api.habilitada and not api.token:
        raise ValueError("la API requiere un token: defina NIEBLA_TOKEN")
    if api.habilitada and api.token and len(api.token) < 24:
        raise ValueError("el token de la API debe tener al menos 24 caracteres")
    base = Path(sitio.get("base_datos", "/var/lib/niebla/niebla.db"))
    if modo == "simulacion" and "simulacion" not in base.name:
        # Los datos simulados nunca se mezclan con la base de producción.
        base = base.with_name(base.stem + "_simulacion" + base.suffix)
    return Config(
        nombre=sitio.get("nombre", "Niebla"),
        modo=modo,
        intervalo_s=float(sitio.get("intervalo_s", 5)),
        base_datos=base,
        plcs=plcs,
        bancos=bancos,
        energia=EnergiaCfg(**d.get("energia", {})),
        api=api,
    )
