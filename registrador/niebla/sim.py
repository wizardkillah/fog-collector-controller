"""PLC simulado para desarrollo, demostraciones y pruebas.

Todo lo que produce va marcado como simulado: el servicio lo guarda en una
base separada y la API lo muestra con la etiqueta SIMULACIÓN. Nunca se usa
como respaldo silencioso cuando falla el PLC real.
"""
from __future__ import annotations

import math
import random

from . import mapa
from .config import PlcCfg


class PlcSimulado:
    def __init__(self, cfg: PlcCfg, semilla: int = 7, calma_s: int = 120, paso_s: float = 5.0):
        self.nombre = cfg.nombre
        self.bancos = list(cfg.bancos)
        self._rnd = random.Random(semilla)
        self._t = 0.0
        self._paso = paso_s
        self._calma_s = calma_s
        self._hr = [0] * mapa.HR_TOTAL
        self._ult_orden = 0
        self._riesgo_t = 0.0
        self._pos = {b: 0.0 for b in self.bancos}
        self._estado = {b: mapa.Estado.RESGUARDADO for b in self.bancos}
        self._retenido = {b: False for b in self.bancos}
        self._balancin = {b: 0 for b in self.bancos}
        self._acum_ml = {b: 0.0 for b in self.bancos}
        self._maniobras = {b: 0 for b in self.bancos}
        self._medias: list[float] = []
        self.forzar_viento: float | None = None

    # -------------------------------------------------------------- interfaz
    def leer(self) -> mapa.LecturaPlc:
        self._avanzar()
        return self._lectura

    def leer_retencion(self, direccion: int, cantidad: int) -> list[int]:
        return self._hr[direccion : direccion + cantidad]

    def escribir(self, direccion: int, valores: list[int]) -> None:
        for i, v in enumerate(valores):
            self._hr[direccion + i] = v & 0xFFFF

    def cerrar(self) -> None:
        pass

    # -------------------------------------------------------------- modelo
    def _avanzar(self) -> None:
        self._t += self._paso
        hora = (self._t / 3600) % 24
        base = 12 + 10 * math.sin(hora / 24 * 2 * math.pi)
        v = self.forzar_viento if self.forzar_viento is not None else max(0.0, self._rnd.gauss(base, 4))
        rafaga = v * 1.3
        self._medias = (self._medias + [v])[-120:]
        media = sum(self._medias) / len(self._medias)
        motivo = mapa.Motivo.NINGUNO
        riesgo = rafaga >= 45 or media >= 35
        if riesgo:
            self._riesgo_t = self._t
            motivo |= mapa.Motivo.RAFAGA if rafaga >= 45 else mapa.Motivo.VIENTO_MEDIO
        calma = (self._t - self._riesgo_t) >= self._calma_s
        if not calma:
            motivo |= mapa.Motivo.CALMA_INSUFICIENTE

        seq = self._hr[mapa.HR_ORDEN_SEQ]
        if seq != self._ult_orden:
            self._ult_orden = seq
            banco, codigo = self._hr[mapa.HR_ORDEN_BANCO], self._hr[mapa.HR_ORDEN_CODIGO]
            for b in self.bancos:
                if banco in (0, b):
                    if codigo == mapa.Orden.RESGUARDAR:
                        self._retenido[b] = True
                    elif codigo == mapa.Orden.HABILITAR:
                        self._retenido[b] = False

        niebla = hora < 10 or hora > 21
        bancos = []
        for b in self.bancos:
            desea = calma and not riesgo and not self._retenido[b]
            if riesgo or self._retenido[b]:
                if self._pos[b] > 0:
                    self._pos[b] = max(0.0, self._pos[b] - 25 * self._paso)
            elif desea:
                if self._pos[b] < 100:
                    self._pos[b] = min(100.0, self._pos[b] + 25 * self._paso)
            antes = self._estado[b]
            if self._pos[b] <= 0:
                self._estado[b] = mapa.Estado.RESGUARDADO
            elif self._pos[b] >= 100:
                self._estado[b] = mapa.Estado.CAPTANDO
            else:
                self._estado[b] = mapa.Estado.DESPLEGANDO if desea else mapa.Estado.RESGUARDANDO
            if antes != self._estado[b] and self._estado[b] in (mapa.Estado.DESPLEGANDO, mapa.Estado.RESGUARDANDO):
                self._maniobras[b] += 1
            if self._estado[b] == mapa.Estado.CAPTANDO and niebla:
                self._acum_ml[b] += self._rnd.uniform(0, 12) * self._paso / 60 * 18  # mL
                while self._acum_ml[b] >= 50:
                    self._acum_ml[b] -= 50
                    self._balancin[b] += 1
            bancos.append(
                mapa.LecturaBanco(
                    banco=b, estado=self._estado[b], fallas=mapa.Falla.NINGUNA,
                    fc_resguardado=self._pos[b] <= 0, fc_desplegado=self._pos[b] >= 100,
                    balancin=self._balancin[b], maniobras=self._maniobras[b], seg_estado=0,
                    marcha=0 < self._pos[b] < 100, sentido_desplegar=desea,
                )
            )
        bat = self._hr[mapa.HR_BATERIA_MV]
        self._lectura = mapa.LecturaPlc(
            version=100, rol=0, uptime_s=int(self._t), viento_inst_kmh=round(v, 1),
            viento_rafaga_kmh=round(rafaga, 1), viento_medio_kmh=round(media, 1), viento_dir=225,
            viento_valido=True, motivo=motivo,
            seg_habilitar=max(0, int(self._calma_s - (self._t - self._riesgo_t))),
            lluvia_mm=0.0, nivel_mm=400, flotador_alto=False,
            temp_c=12.0, hr_pct=95.0 if niebla else 70.0, sensores=0x0F,
            bateria_v=bat / 1000 if bat else None, orden_aplicada=self._ult_orden,
            param_recortado=False, permiso=True, bancos=bancos, simulado=True,
        )
