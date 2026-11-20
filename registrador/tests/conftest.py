import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from niebla import mapa  # noqa: E402
from niebla.config import ApiCfg, BancoCfg, Config, EnergiaCfg, PlcCfg  # noqa: E402

TOKEN = "t" * 32


def cfg_prueba(modo="simulacion", ml=50.0):
    return Config(
        nombre="Prueba", modo=modo, intervalo_s=5, base_datos=Path(":memory:"),
        plcs=[PlcCfg("principal", "127.0.0.1", 502, [1, 2])],
        bancos={1: BancoCfg(1, 18, ml), 2: BancoCfg(2, 18, None)},
        energia=EnergiaCfg(), api=ApiCfg(True, "127.0.0.1", 8080, TOKEN),
    )


def lectura(**kw):
    bancos = kw.pop("bancos", None) or [
        mapa.LecturaBanco(1, mapa.Estado.RESGUARDADO, mapa.Falla.NINGUNA, True, False, 0, 0, 10, False, False),
        mapa.LecturaBanco(2, mapa.Estado.RESGUARDADO, mapa.Falla.NINGUNA, True, False, 0, 0, 10, False, False),
    ]
    base = dict(version=100, rol=0, uptime_s=100, viento_inst_kmh=10.0, viento_rafaga_kmh=12.0,
                viento_medio_kmh=9.5, viento_dir=225, viento_valido=True, motivo=mapa.Motivo.NINGUNO,
                seg_habilitar=0, lluvia_mm=1.2, nivel_mm=450, flotador_alto=False, temp_c=-1.5,
                hr_pct=97.0, sensores=0x0F, bateria_v=13.1, orden_aplicada=0, param_recortado=False,
                permiso=True, bancos=bancos, simulado=False)
    base.update(kw)
    return mapa.LecturaPlc(**base)


@pytest.fixture
def cfg():
    return cfg_prueba()
