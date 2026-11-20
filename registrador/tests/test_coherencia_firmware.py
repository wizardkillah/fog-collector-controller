"""El mapa de registros del firmware y el del registrador deben ser idénticos."""
import re
from pathlib import Path

from niebla import mapa

HEADER = Path(__file__).resolve().parents[2] / "firmware" / "opta_niebla" / "mapa_registros.h"


def test_mapa_identico():
    texto = HEADER.read_text(encoding="utf-8")
    pares = dict(re.findall(r"\b((?:IR|HR|B)_[A-Z0-9_]+)\s*=\s*(\d+)", texto))
    assert pares, "no se leyeron constantes del header"
    faltan = []
    for nombre, valor in pares.items():
        if nombre.startswith("HR_PAR_"):
            continue  # bloque interno entre PLC
        if hasattr(mapa, nombre):
            assert getattr(mapa, nombre) == int(valor), nombre
        elif not nombre.endswith("_L") and not nombre.endswith("_H") or nombre in ("IR_UPTIME_H", "IR_LLUVIA_H"):
            faltan.append(nombre)
    assert not faltan, faltan


def test_estados_identicos():
    h = (HEADER.parent / "niebla_core.h").read_text(encoding="utf-8")
    bloque = h[h.index("enum class Estado"):h.index("};", h.index("enum class Estado"))]
    for nombre, valor in re.findall(r"([A-Z_]+) = (\d+)", bloque):
        assert mapa.Estado[nombre] == int(valor)
