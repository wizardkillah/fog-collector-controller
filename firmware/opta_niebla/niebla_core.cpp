// Niebla — núcleo de control portable. Ver niebla_core.h.
#include "niebla_core.h"

namespace niebla {

float recortar(float v, float lo, float hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

static uint32_t recortar_u(uint32_t v, uint32_t lo, uint32_t hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

bool aplicar_parametros(Parametros& d, const Parametros& p, const Envolvente& env) {
  Parametros r = d;
  r.rafaga_resguardo_kmh = recortar(p.rafaga_resguardo_kmh, env.rafaga_min_kmh, env.rafaga_max_kmh);
  r.medio_resguardo_kmh = recortar(p.medio_resguardo_kmh, env.medio_min_kmh, env.medio_max_kmh);
  // La media de resguardo nunca puede superar la ráfaga de resguardo.
  if (r.medio_resguardo_kmh > r.rafaga_resguardo_kmh) r.medio_resguardo_kmh = r.rafaga_resguardo_kmh;
  float rehab_max = r.medio_resguardo_kmh - env.margen_rehab_min_kmh;
  r.medio_rehabilitar_kmh = recortar(p.medio_rehabilitar_kmh, 0.0f, rehab_max);
  r.calma_minima_s = recortar_u(p.calma_minima_s, env.calma_min_s, env.calma_max_s);
  bool recortado = r.rafaga_resguardo_kmh != p.rafaga_resguardo_kmh ||
                   r.medio_resguardo_kmh != p.medio_resguardo_kmh ||
                   r.medio_rehabilitar_kmh != p.medio_rehabilitar_kmh ||
                   r.calma_minima_s != p.calma_minima_s;
  d = r;
  return recortado;
}

// ============================================================== Viento
void Viento::reiniciar() {
  *this = Viento();
}

void Viento::muestra(float kmh, float dir, uint32_t t_s) {
  if (kmh < 0) kmh = 0;
  inst_ = kmh;
  dir_ = dir;
  t_ultima_ = t_s;
  alguna_ = true;

  ult3_[i3_] = kmh;
  i3_ = (uint8_t)((i3_ + 1) % N3);
  if (n3_ < N3) n3_++;
  float s = 0;
  for (uint8_t i = 0; i < n3_; i++) s += ult3_[i];
  rafaga_ = s / n3_;

  if (!hay_bin_) {
    hay_bin_ = true;
    t_bin_inicio_ = t_s;
  } else if (t_s - t_bin_inicio_ >= 10 && n_acum_ > 0) {
    bins_[ibin_] = acum_bin_ / n_acum_;
    ibin_ = (uint8_t)((ibin_ + 1) % NBINS);
    if (n_bins_ < NBINS) n_bins_++;
    acum_bin_ = 0;
    n_acum_ = 0;
    t_bin_inicio_ = t_s;
  }
  acum_bin_ += kmh;
  n_acum_++;
  recalcular_media();
}

void Viento::recalcular_media() {
  float s = 0;
  uint16_t n = 0;
  for (uint8_t i = 0; i < n_bins_; i++) { s += bins_[i]; n++; }
  if (n_acum_ > 0) { s += acum_bin_ / n_acum_; n++; }
  media_ = n ? s / n : 0;
}

bool Viento::valido(uint32_t t_s, uint32_t vigencia_s) const {
  return alguna_ && (t_s - t_ultima_) <= vigencia_s;
}

// ============================================================== Sitio
DecisionSitio Sitio::evaluar(const EntradasSitio& e, uint32_t t_s) {
  DecisionSitio d;
  uint16_t m = M_NINGUNO;
  bool riesgo = false;

  if (!e.viento_valido) {
    m |= M_VIENTO_SIN_DATO;
    riesgo = true;
  } else {
    if (e.rafaga_kmh >= p_->rafaga_resguardo_kmh) { m |= M_RAFAGA; riesgo = true; }
    if (e.media_kmh >= p_->medio_resguardo_kmh) { m |= M_VIENTO_MEDIO; riesgo = true; }
    if (e.media_kmh > p_->medio_rehabilitar_kmh) m |= M_SOBRE_REHABILITACION;
  }

  // Batería: sólo cuenta si el dato es reciente. Histéresis de 0,4 V.
  if (e.bateria_valida) {
    if (e.bateria_v < p_->bateria_reserva_v) bateria_baja_ = true;
    else if (e.bateria_v > p_->bateria_reserva_v + 0.4f) bateria_baja_ = false;
  }
  if (bateria_baja_) m |= M_BATERIA_BAJA;

  if (riesgo) {
    t_ultimo_riesgo_ = t_s;
    hubo_riesgo_ = true;
  }
  bool calma = !hubo_riesgo_ || (t_s - t_ultimo_riesgo_) >= p_->calma_minima_s;
  if (!calma) m |= M_CALMA_INSUFICIENTE;

  // Con batería baja se resguarda: la reserva debe alcanzar para una maniobra.
  d.exige_resguardo = riesgo || bateria_baja_;
  d.permite_desplegar = !d.exige_resguardo && calma && !(m & M_SOBRE_REHABILITACION);
  motivo_ = m;
  return d;
}

uint32_t Sitio::segundos_para_habilitar(uint32_t t_s) const {
  if (!hubo_riesgo_) return 0;
  uint32_t trans = t_s - t_ultimo_riesgo_;
  return trans >= p_->calma_minima_s ? 0 : p_->calma_minima_s - trans;
}

// ============================================================== Banco
void Banco::ir(Estado nuevo, uint32_t t_s) {
  estado_ = nuevo;
  t_estado_ = t_s;
}

bool Banco::puede_maniobrar(uint32_t t_s) const {
  return !hubo_maniobra_ || (t_s - t_ultima_maniobra_) >= p_->min_entre_maniobras_s;
}

SalidasBanco Banco::paso(const EntradasBanco& e, const DecisionSitio& d, uint32_t t_s) {
  SalidasBanco s;  // por defecto todo apagado
  if (!inicializado_) {
    inicializado_ = true;
    t_estado_ = t_s;
  }

  const bool ambos = e.fc_resguardado && e.fc_desplegado;
  if (ambos && estado_ != Estado::FALLA) {
    fallas_ |= F_FINALES_INCOHERENTES;
    ir(Estado::FALLA, t_s);
  }
  if (!e.permiso && estado_ != Estado::FALLA && estado_ != Estado::LOCAL) {
    ir(Estado::LOCAL, t_s);
  }

  // Reconocimiento: borra fallas enclavadas si la causa física ya no existe.
  if (reconocer_) {
    reconocer_ = false;
    if (!ambos) {
      fallas_ = F_NINGUNA;
      if (estado_ == Estado::FALLA) ir(Estado::INICIANDO, t_s);
    }
  }

  const bool quiere_resguardo = d.exige_resguardo || retenido;
  const bool puede_desplegar = d.permite_desplegar && !retenido &&
                               !(fallas_ & (F_TIEMPO_DESPLIEGUE | F_TIEMPO_RESGUARDO));
  const uint32_t en_estado = t_s - t_estado_;

  switch (estado_) {
    case Estado::INICIANDO:
      if (e.fc_resguardado) ir(Estado::RESGUARDADO, t_s);
      else ir(Estado::RESGUARDANDO, t_s);  // el arranque siempre busca el estado seguro
      break;

    case Estado::RESGUARDADO:
      if (!e.fc_resguardado) {
        fallas_ |= F_POSICION_PERDIDA;     // se movió sin orden: volver a asentar
        ir(Estado::RESGUARDANDO, t_s);
      } else if (puede_desplegar && puede_maniobrar(t_s)) {
        maniobras_++;
        ir(Estado::DESPLEGANDO, t_s);
      }
      break;

    case Estado::DESPLEGANDO:
      if (quiere_resguardo) {
        destino_pausa_ = Estado::RESGUARDANDO;
        ir(Estado::PAUSA, t_s);
      } else if (e.fc_desplegado) {
        t_ultima_maniobra_ = t_s;
        hubo_maniobra_ = true;
        ir(Estado::CAPTANDO, t_s);
      } else if (en_estado > p_->tiempo_max_maniobra_s) {
        fallas_ |= F_TIEMPO_DESPLIEGUE;    // intento de volver a lo seguro
        destino_pausa_ = Estado::RESGUARDANDO;
        ir(Estado::PAUSA, t_s);
      } else {
        s.marcha = true;
        s.sentido_desplegar = true;
      }
      break;

    case Estado::CAPTANDO:
      if (!e.fc_desplegado) fallas_ |= F_POSICION_PERDIDA;  // aviso, sin mover
      if (quiere_resguardo) {
        maniobras_++;
        ir(Estado::RESGUARDANDO, t_s);
      }
      break;

    case Estado::RESGUARDANDO:
      if (e.fc_resguardado) {
        t_ultima_maniobra_ = t_s;
        hubo_maniobra_ = true;
        ir(Estado::RESGUARDADO, t_s);
      } else if (en_estado > p_->tiempo_max_maniobra_s) {
        fallas_ |= F_TIEMPO_RESGUARDO;
        ir(Estado::FALLA, t_s);
      } else {
        s.marcha = true;
        s.sentido_desplegar = false;
      }
      break;

    case Estado::PAUSA:
      if (en_estado >= p_->pausa_inversion_s) ir(destino_pausa_, t_s);
      break;

    case Estado::FALLA:
      break;  // salidas apagadas hasta reconocimiento

    case Estado::LOCAL:
      if (e.permiso) ir(Estado::INICIANDO, t_s);
      break;
  }

  // Salvaguarda final: nunca empujar contra un final alcanzado.
  if (s.marcha && s.sentido_desplegar && e.fc_desplegado) s.marcha = false;
  if (s.marcha && !s.sentido_desplegar && e.fc_resguardado) s.marcha = false;
  if (!e.permiso) s.marcha = false;
  return s;
}

// ============================================================== Contador
void Contador::muestra(bool nivel, uint32_t t_ms) {
  if (nivel != ultimo_) {
    ultimo_ = nivel;
    t_cambio_ = t_ms;
    return;
  }
  if (nivel != estable_ && (t_ms - t_cambio_) >= db_ms_) {
    estable_ = nivel;
    if (estable_) cuenta_++;
  }
}

}  // namespace niebla
