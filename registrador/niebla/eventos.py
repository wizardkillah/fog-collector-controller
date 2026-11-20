"""Detección de eventos por comparación de lecturas consecutivas y cálculo de captación."""
from __future__ import annotations

from dataclasses import dataclass

from . import mapa


@dataclass
class Evento:
    tipo: str
    severidad: str  # info | aviso | critico
    detalle: str
    banco: int | None = None


_SEVERIDAD_ESTADO = {
    mapa.Estado.FALLA: "critico",
    mapa.Estado.LOCAL: "aviso",
    mapa.Estado.RESGUARDANDO: "aviso",
}


def comparar(prev: mapa.LecturaPlc | None, act: mapa.LecturaPlc) -> list[Evento]:
    ev: list[Evento] = []
    if prev is None:
        ev.append(Evento("ENLACE", "info", f"primera lectura del PLC (firmware {act.version})"))
        return ev

    if act.uptime_s < prev.uptime_s:
        ev.append(Evento("REINICIO_PLC", "aviso", f"el PLC se reinició (uptime {act.uptime_s} s)"))

    nuevos = act.motivo & ~prev.motivo
    if nuevos & mapa.Motivo.VIENTO_SIN_DATO:
        ev.append(Evento("SENSOR_VIENTO", "critico", "sin datos de viento: los bancos se resguardan"))
    if nuevos & mapa.Motivo.RAFAGA:
        ev.append(Evento("VIENTO", "aviso", f"ráfaga {act.viento_rafaga_kmh:.1f} km/h sobre el umbral"))
    if nuevos & mapa.Motivo.VIENTO_MEDIO:
        ev.append(Evento("VIENTO", "aviso", f"media 10 min {act.viento_medio_kmh:.1f} km/h sobre el umbral"))
    if nuevos & mapa.Motivo.BATERIA_BAJA:
        ev.append(Evento("ENERGIA", "aviso", f"batería bajo reserva ({act.bateria_v} V)"))
    if nuevos & mapa.Motivo.SIN_PERMISO:
        ev.append(Evento("PERMISO", "aviso", "selector en LOCAL o parada de emergencia activa"))
    if (prev.motivo & mapa.Motivo.VIENTO_SIN_DATO) and not (act.motivo & mapa.Motivo.VIENTO_SIN_DATO):
        ev.append(Evento("SENSOR_VIENTO", "info", "datos de viento restablecidos"))

    if act.flotador_alto and not prev.flotador_alto:
        ev.append(Evento("REBALSE", "aviso", "flotador de nivel alto activo"))
    if act.param_recortado and not prev.param_recortado:
        ev.append(Evento("PARAMETROS", "aviso", "parámetros recortados a la envolvente de ingeniería"))

    previos = {b.banco: b for b in prev.bancos}
    for b in act.bancos:
        p = previos.get(b.banco)
        if p is None:
            continue
        if b.estado != p.estado:
            motivo = ", ".join(mapa.nombres(act.motivo)) or "sin motivo"
            ev.append(Evento("ESTADO", _SEVERIDAD_ESTADO.get(b.estado, "info"),
                             f"{p.estado.name} → {b.estado.name} ({motivo})", b.banco))
        nuevas = b.fallas & ~p.fallas
        if nuevas:
            sev = "aviso" if nuevas == mapa.Falla.POSICION_PERDIDA else "critico"
            ev.append(Evento("FALLA", sev, "falla: " + ", ".join(mapa.nombres(nuevas)), b.banco))
        if p.fallas and not b.fallas:
            ev.append(Evento("FALLA", "info", "fallas reconocidas", b.banco))
    return ev


class Captacion:
    """Convierte la cuenta del balancín en pulsos y litros entre lecturas."""

    def __init__(self, ml_por_pulso: float | None):
        self.ml = ml_por_pulso
        self._ultimo: int | None = None
        self.pendiente_pulsos = 0

    def actualizar(self, cuenta: int) -> tuple[int, bool]:
        """Devuelve (pulsos nuevos, hubo_reinicio_del_contador)."""
        if self._ultimo is None:
            self._ultimo = cuenta
            return 0, False
        reinicio = cuenta < self._ultimo
        delta = cuenta if reinicio else cuenta - self._ultimo
        self._ultimo = cuenta
        self.pendiente_pulsos += delta
        return delta, reinicio

    def tomar(self) -> tuple[int, float | None]:
        """Pulsos acumulados desde el último registro y sus litros (None sin calibración)."""
        p, self.pendiente_pulsos = self.pendiente_pulsos, 0
        return p, (round(p * self.ml / 1000, 3) if self.ml else None)
