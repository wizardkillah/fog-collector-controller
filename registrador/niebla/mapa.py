"""Mapa de registros Modbus del PLC y decodificación.

Debe coincidir con firmware/opta_niebla/mapa_registros.h.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag

# ---------------------------------------------------------------- entrada (FC04)
IR_VERSION = 0
IR_ROL = 1
IR_UPTIME_H = 2
IR_VIENTO_INST = 4
IR_VIENTO_RAFAGA = 5
IR_VIENTO_MEDIO = 6
IR_VIENTO_DIR = 7
IR_VIENTO_VALIDO = 8
IR_MOTIVO = 9
IR_SEG_HABILITAR = 10
IR_LLUVIA_H = 11
IR_NIVEL_MM = 13
IR_FLOTADOR_ALTO = 14
IR_TEMP = 15
IR_HR = 16
IR_SENSORES = 17
IR_BATERIA_MV = 18
IR_ORDEN_APLICADA = 19
IR_PARAM_RECORTADO = 20
IR_PERMISO = 21
IR_BANCO_BASE = 30
IR_BANCO_PASO = 10
IR_TOTAL = 50

B_ID, B_ESTADO, B_FALLAS, B_FINALES = 0, 1, 2, 3
B_BALANCIN_H, B_MANIOBRAS_H, B_SEG_ESTADO, B_SALIDAS = 4, 6, 8, 9

# ---------------------------------------------------------------- retención (FC03/06/16)
HR_LATIDO = 0
HR_ORDEN_SEQ = 1
HR_ORDEN_BANCO = 2
HR_ORDEN_CODIGO = 3
HR_BATERIA_MV = 4
HR_BATERIA_SEQ = 5
HR_PARAM_RAFAGA = 10
HR_PARAM_MEDIO = 11
HR_PARAM_REHAB = 12
HR_PARAM_CALMA_MIN = 13
HR_PARAM_SEQ = 14
HR_TOTAL = 40

SIN_NIVEL = 0xFFFF


class Estado(IntEnum):
    INICIANDO = 0
    RESGUARDADO = 1
    DESPLEGANDO = 2
    CAPTANDO = 3
    RESGUARDANDO = 4
    FALLA = 5
    LOCAL = 6
    PAUSA = 7


class Falla(IntFlag):
    NINGUNA = 0
    TIEMPO_DESPLIEGUE = 1 << 0
    TIEMPO_RESGUARDO = 1 << 1
    FINALES_INCOHERENTES = 1 << 2
    POSICION_PERDIDA = 1 << 3


class Motivo(IntFlag):
    NINGUNO = 0
    RAFAGA = 1 << 0
    VIENTO_MEDIO = 1 << 1
    VIENTO_SIN_DATO = 1 << 2
    CALMA_INSUFICIENTE = 1 << 3
    BATERIA_BAJA = 1 << 4
    ORDEN_RESGUARDO = 1 << 5
    SIN_PERMISO = 1 << 6
    SOBRE_REHABILITACION = 1 << 7


class Orden(IntEnum):
    HABILITAR = 1
    RESGUARDAR = 2
    RECONOCER_FALLA = 3


def _u32(regs: list[int], i: int) -> int:
    return (regs[i] << 16) | regs[i + 1]


def _i16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


def nombres(flag: IntFlag) -> list[str]:
    """Nombres de los bits activos, en orden estable."""
    return [m.name for m in type(flag) if m.value and (flag & m) == m]


@dataclass
class LecturaBanco:
    banco: int
    estado: Estado
    fallas: Falla
    fc_resguardado: bool
    fc_desplegado: bool
    balancin: int
    maniobras: int
    seg_estado: int
    marcha: bool
    sentido_desplegar: bool


@dataclass
class LecturaPlc:
    version: int
    rol: int
    uptime_s: int
    viento_inst_kmh: float
    viento_rafaga_kmh: float
    viento_medio_kmh: float
    viento_dir: int
    viento_valido: bool
    motivo: Motivo
    seg_habilitar: int
    lluvia_mm: float
    nivel_mm: int | None
    flotador_alto: bool
    temp_c: float | None
    hr_pct: float | None
    sensores: int
    bateria_v: float | None
    orden_aplicada: int
    param_recortado: bool
    permiso: bool
    bancos: list[LecturaBanco] = field(default_factory=list)
    simulado: bool = False


def decodificar(regs: list[int], n_bancos: int = 2, simulado: bool = False) -> LecturaPlc:
    if len(regs) < IR_TOTAL:
        raise ValueError(f"se esperaban {IR_TOTAL} registros, llegaron {len(regs)}")
    sensores = regs[IR_SENSORES]
    thr_ok = bool(sensores & 0x08)
    bancos = []
    for i in range(n_bancos):
        b = IR_BANCO_BASE + i * IR_BANCO_PASO
        fin = regs[b + B_FINALES]
        sal = regs[b + B_SALIDAS]
        bancos.append(
            LecturaBanco(
                banco=regs[b + B_ID],
                estado=Estado(regs[b + B_ESTADO]),
                fallas=Falla(regs[b + B_FALLAS]),
                fc_resguardado=bool(fin & 1),
                fc_desplegado=bool(fin & 2),
                balancin=_u32(regs, b + B_BALANCIN_H),
                maniobras=_u32(regs, b + B_MANIOBRAS_H),
                seg_estado=regs[b + B_SEG_ESTADO],
                marcha=bool(sal & 1),
                sentido_desplegar=bool(sal & 2),
            )
        )
    nivel = regs[IR_NIVEL_MM]
    bat = regs[IR_BATERIA_MV]
    return LecturaPlc(
        version=regs[IR_VERSION],
        rol=regs[IR_ROL],
        uptime_s=_u32(regs, IR_UPTIME_H),
        viento_inst_kmh=regs[IR_VIENTO_INST] / 10,
        viento_rafaga_kmh=regs[IR_VIENTO_RAFAGA] / 10,
        viento_medio_kmh=regs[IR_VIENTO_MEDIO] / 10,
        viento_dir=regs[IR_VIENTO_DIR],
        viento_valido=bool(regs[IR_VIENTO_VALIDO]),
        motivo=Motivo(regs[IR_MOTIVO]),
        seg_habilitar=regs[IR_SEG_HABILITAR],
        lluvia_mm=_u32(regs, IR_LLUVIA_H) / 10,
        nivel_mm=None if nivel == SIN_NIVEL else nivel,
        flotador_alto=bool(regs[IR_FLOTADOR_ALTO]),
        temp_c=_i16(regs[IR_TEMP]) / 10 if thr_ok else None,
        hr_pct=regs[IR_HR] / 10 if thr_ok else None,
        sensores=sensores,
        bateria_v=bat / 1000 if bat else None,
        orden_aplicada=regs[IR_ORDEN_APLICADA],
        param_recortado=bool(regs[IR_PARAM_RECORTADO]),
        permiso=bool(regs[IR_PERMISO]),
        bancos=bancos,
        simulado=simulado,
    )


def codificar(lectura: LecturaPlc) -> list[int]:
    """Inverso de decodificar (lo usan el simulador y las pruebas)."""
    r = [0] * IR_TOTAL

    def u32(i: int, v: int) -> None:
        r[i], r[i + 1] = (v >> 16) & 0xFFFF, v & 0xFFFF

    r[IR_VERSION] = lectura.version
    r[IR_ROL] = lectura.rol
    u32(IR_UPTIME_H, lectura.uptime_s)
    r[IR_VIENTO_INST] = round(lectura.viento_inst_kmh * 10)
    r[IR_VIENTO_RAFAGA] = round(lectura.viento_rafaga_kmh * 10)
    r[IR_VIENTO_MEDIO] = round(lectura.viento_medio_kmh * 10)
    r[IR_VIENTO_DIR] = lectura.viento_dir
    r[IR_VIENTO_VALIDO] = int(lectura.viento_valido)
    r[IR_MOTIVO] = int(lectura.motivo)
    r[IR_SEG_HABILITAR] = min(lectura.seg_habilitar, 0xFFFF)
    u32(IR_LLUVIA_H, round(lectura.lluvia_mm * 10))
    r[IR_NIVEL_MM] = SIN_NIVEL if lectura.nivel_mm is None else lectura.nivel_mm
    r[IR_FLOTADOR_ALTO] = int(lectura.flotador_alto)
    r[IR_TEMP] = round((lectura.temp_c or 0) * 10) & 0xFFFF
    r[IR_HR] = round((lectura.hr_pct or 0) * 10)
    r[IR_SENSORES] = lectura.sensores
    r[IR_BATERIA_MV] = round(lectura.bateria_v * 1000) if lectura.bateria_v else 0
    r[IR_ORDEN_APLICADA] = lectura.orden_aplicada
    r[IR_PARAM_RECORTADO] = int(lectura.param_recortado)
    r[IR_PERMISO] = int(lectura.permiso)
    for i, b in enumerate(lectura.bancos):
        base = IR_BANCO_BASE + i * IR_BANCO_PASO
        r[base + B_ID] = b.banco
        r[base + B_ESTADO] = int(b.estado)
        r[base + B_FALLAS] = int(b.fallas)
        r[base + B_FINALES] = int(b.fc_resguardado) | (int(b.fc_desplegado) << 1)
        u32(base + B_BALANCIN_H, b.balancin)
        u32(base + B_MANIOBRAS_H, b.maniobras)
        r[base + B_SEG_ESTADO] = min(b.seg_estado, 0xFFFF)
        r[base + B_SALIDAS] = int(b.marcha) | (int(b.sentido_desplegar) << 1)
    return r
