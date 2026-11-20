// Niebla — núcleo de control portable (sin dependencias de Arduino)
//
// Este archivo contiene TODA la lógica de seguridad y control de los bancos.
// Se compila igual en el Arduino Opta y en un PC (pruebas unitarias con g++),
// por lo que no usa memoria dinámica, ni String, ni millis(): el tiempo entra
// como argumento en cada llamada.
//
// Principios (ver docs/arquitectura.md):
//   1. El estado seguro es RESGUARDADO. Sin datos de viento válidos no se despliega.
//   2. La seguridad vive en el PLC, no en el registrador ni en la nube.
//   3. Toda maniobra tiene tiempo máximo; los finales de carrera son NC.
//   4. Después de un resguardo se exige un periodo de calma antes de volver a desplegar.
//   5. Ningún parámetro remoto puede salir de la envolvente de ingeniería.
#pragma once
#include <stdint.h>

namespace niebla {

// ---------------------------------------------------------------- constantes
static const uint8_t MAX_BANCOS = 2;          // bancos por PLC (4 relés = 2 bancos)
static const uint16_t VERSION_FIRMWARE = 100; // 1.0.0

// Envolvente de ingeniería: los parámetros escritos por el registrador se
// recortan a estos límites. Deben fijarse con el cálculo estructural del sitio.
struct Envolvente {
  float rafaga_min_kmh = 20.0f, rafaga_max_kmh = 60.0f;
  float medio_min_kmh = 15.0f, medio_max_kmh = 50.0f;
  float margen_rehab_min_kmh = 5.0f;          // rehabilitar <= medio - margen
  uint32_t calma_min_s = 600, calma_max_s = 7200;
};

struct Parametros {
  float rafaga_resguardo_kmh = 45.0f;   // ráfaga 3 s que ordena resguardo inmediato
  float medio_resguardo_kmh = 35.0f;    // media 10 min que ordena resguardo
  float medio_rehabilitar_kmh = 25.0f;  // media 10 min máxima para volver a desplegar
  uint32_t calma_minima_s = 1800;       // tiempo sin riesgo antes de desplegar
  uint32_t viento_vigencia_s = 10;      // dato de viento más antiguo = inválido
  uint32_t tiempo_max_maniobra_s = 90;  // desde la ingeniería del mecanismo
  uint32_t min_entre_maniobras_s = 60;  // protege motor y mecanismo
  uint32_t pausa_inversion_s = 2;       // motor detenido antes de invertir sentido
  float bateria_reserva_v = 12.4f;      // bajo este valor se resguarda y se bloquea
  uint32_t bateria_vigencia_s = 300;    // dato de batería más antiguo = se ignora
};

// ---------------------------------------------------------------- enumeraciones
enum class Estado : uint8_t {
  INICIANDO = 0,
  RESGUARDADO = 1,
  DESPLEGANDO = 2,
  CAPTANDO = 3,
  RESGUARDANDO = 4,
  FALLA = 5,
  LOCAL = 6,     // sin permiso de maniobra (selector LOCAL o parada de emergencia)
  PAUSA = 7,     // motor detenido antes de invertir sentido
};

enum Falla : uint16_t {
  F_NINGUNA = 0,
  F_TIEMPO_DESPLIEGUE = 1u << 0,
  F_TIEMPO_RESGUARDO = 1u << 1,
  F_FINALES_INCOHERENTES = 1u << 2,   // ambos finales activos (o cable cortado)
  F_POSICION_PERDIDA = 1u << 3,       // aviso: dejó el final sin orden
};

// Motivos por los que el sitio no permite desplegar (bitmask, se publica).
enum Motivo : uint16_t {
  M_NINGUNO = 0,
  M_RAFAGA = 1u << 0,
  M_VIENTO_MEDIO = 1u << 1,
  M_VIENTO_SIN_DATO = 1u << 2,
  M_CALMA_INSUFICIENTE = 1u << 3,
  M_BATERIA_BAJA = 1u << 4,
  M_ORDEN_RESGUARDO = 1u << 5,        // retención remota o local por banco
  M_SIN_PERMISO = 1u << 6,
  M_SOBRE_REHABILITACION = 1u << 7,   // media sobre el umbral de rehabilitación
};

// Resultado de la evaluación del sitio. Dos umbrales distintos dan histéresis:
// un banco desplegado sólo se resguarda con riesgo, y uno resguardado sólo se
// despliega con calma sostenida.
struct DecisionSitio {
  bool exige_resguardo = true;
  bool permite_desplegar = false;
};

enum class Orden : uint8_t { NINGUNA = 0, HABILITAR = 1, RESGUARDAR = 2, RECONOCER_FALLA = 3 };

// ---------------------------------------------------------------- viento
// Recibe muestras de velocidad (idealmente 1 Hz) y calcula:
//   - ráfaga: media móvil de 3 s (criterio OMM)
//   - media: promedio de hasta 10 min en contenedores de 10 s
class Viento {
 public:
  void muestra(float kmh, float direccion_grados, uint32_t t_s);
  bool valido(uint32_t t_s, uint32_t vigencia_s) const;
  float rafaga() const { return rafaga_; }
  float media() const { return media_; }
  float instantaneo() const { return inst_; }
  float direccion() const { return dir_; }
  // Minutos de historia usados por la media (0..10).
  uint8_t minutos_historia() const { return (uint8_t)(n_bins_ / 6); }
  void reiniciar();

 private:
  static const uint8_t N3 = 3;
  static const uint8_t NBINS = 60;  // 60 x 10 s = 10 min
  float ult3_[N3] = {0, 0, 0};
  uint8_t i3_ = 0, n3_ = 0;
  float bins_[NBINS] = {0};
  uint8_t ibin_ = 0, n_bins_ = 0;
  float acum_bin_ = 0;
  uint16_t n_acum_ = 0;
  uint32_t t_bin_inicio_ = 0;
  bool hay_bin_ = false;
  uint32_t t_ultima_ = 0;
  bool alguna_ = false;
  float rafaga_ = 0, media_ = 0, inst_ = 0, dir_ = 0;
  void recalcular_media();
};

// ---------------------------------------------------------------- sitio
// Decide si el sitio permite desplegar. Es la misma lógica para el PLC
// principal (viento medido) y el secundario (viento recibido del principal).
struct EntradasSitio {
  bool viento_valido;
  float rafaga_kmh;
  float media_kmh;
  bool bateria_valida;
  float bateria_v;
};

class Sitio {
 public:
  explicit Sitio(const Parametros* p) : p_(p) {}
  DecisionSitio evaluar(const EntradasSitio& e, uint32_t t_s);
  uint16_t motivo() const { return motivo_; }
  uint32_t segundos_para_habilitar(uint32_t t_s) const;
  void reiniciar(uint32_t t_s) { t_ultimo_riesgo_ = t_s; hubo_riesgo_ = true; }

 private:
  const Parametros* p_;
  uint32_t t_ultimo_riesgo_ = 0;
  bool hubo_riesgo_ = true;  // al arrancar se exige calma completa
  uint16_t motivo_ = M_CALMA_INSUFICIENTE;
  bool bateria_baja_ = false;
};

// ---------------------------------------------------------------- banco
struct EntradasBanco {
  bool fc_resguardado;   // true = final de carrera alcanzado (ya invertido NC)
  bool fc_desplegado;
  bool permiso;          // selector en REMOTO y parada de emergencia no pulsada
};

struct SalidasBanco {
  bool marcha = false;
  bool sentido_desplegar = false;  // false = sentido resguardar (reposo seguro)
};

class Banco {
 public:
  explicit Banco(const Parametros* p) : p_(p) {}
  // Se llama en cada ciclo (típicamente 20 Hz). Devuelve las salidas a aplicar.
  SalidasBanco paso(const EntradasBanco& e, const DecisionSitio& d, uint32_t t_s);
  void reconocer_falla() { reconocer_ = true; }
  Estado estado() const { return estado_; }
  uint16_t fallas() const { return fallas_; }
  uint32_t maniobras() const { return maniobras_; }
  uint32_t segundos_en_estado(uint32_t t_s) const { return t_s - t_estado_; }
  // Retención por orden remota/local (RESGUARDAR/HABILITAR).
  bool retenido = false;

 private:
  const Parametros* p_;
  Estado estado_ = Estado::INICIANDO;
  Estado destino_pausa_ = Estado::RESGUARDANDO;
  uint16_t fallas_ = F_NINGUNA;
  uint32_t t_estado_ = 0;
  uint32_t t_ultima_maniobra_ = 0;
  bool hubo_maniobra_ = false;
  bool reconocer_ = false;
  uint32_t maniobras_ = 0;
  bool inicializado_ = false;
  void ir(Estado nuevo, uint32_t t_s);
  bool puede_maniobrar(uint32_t t_s) const;
};

// ---------------------------------------------------------------- contador
// Contador de pulsos con antirrebote (balancín de captación). Se alimenta con
// el nivel lógico leído en cada ciclo; cuenta flancos de subida estables.
class Contador {
 public:
  explicit Contador(uint32_t antirrebote_ms = 50) : db_ms_(antirrebote_ms) {}
  void muestra(bool nivel, uint32_t t_ms);
  uint32_t cuenta() const { return cuenta_; }

 private:
  uint32_t db_ms_;
  bool estable_ = false, ultimo_ = false;
  uint32_t t_cambio_ = 0;
  uint32_t cuenta_ = 0;
};

// ---------------------------------------------------------------- utilidades
float recortar(float v, float lo, float hi);
// Aplica parámetros propuestos dentro de la envolvente. Devuelve true si
// hubo que recortar algún valor.
bool aplicar_parametros(Parametros& destino, const Parametros& propuesto, const Envolvente& env);

}  // namespace niebla
