// Pruebas unitarias del núcleo de control (se ejecutan en PC con g++).
//   make -C firmware/test
#include <cstdio>
#include <cstdlib>
#include "../opta_niebla/niebla_core.h"

using namespace niebla;

static int fallos = 0, total = 0;
#define CHECK(c)                                                         \
  do {                                                                   \
    total++;                                                             \
    if (!(c)) { fallos++; std::printf("  FALLA %s:%d  %s\n", __FILE__, __LINE__, #c); } \
  } while (0)

// Simulador físico mínimo de un banco: la posición avanza con el motor.
struct Mecanismo {
  float pos = 0;          // 0 = resguardado, 100 = desplegado
  float vel = 5;          // % por segundo  (20 s de carrera)
  bool atascado = false;
  bool cable_cortado_desplegado = false;
  EntradasBanco leer(bool permiso = true) const {
    EntradasBanco e;
    e.fc_resguardado = pos <= 0.0f;
    e.fc_desplegado = pos >= 100.0f || cable_cortado_desplegado;  // NC cortado = activo
    e.permiso = permiso;
    return e;
  }
  void mover(const SalidasBanco& s, float dt) {
    if (!s.marcha || atascado) return;
    pos += (s.sentido_desplegar ? vel : -vel) * dt;
    if (pos < 0) pos = 0;
    if (pos > 100) pos = 100;
  }
};

static DecisionSitio calma() { DecisionSitio d; d.exige_resguardo = false; d.permite_desplegar = true; return d; }
static DecisionSitio riesgo() { DecisionSitio d; d.exige_resguardo = true; d.permite_desplegar = false; return d; }
static DecisionSitio intermedio() { DecisionSitio d; d.exige_resguardo = false; d.permite_desplegar = false; return d; }

// Corre el banco durante 'seg' segundos a 10 Hz.
static void correr(Banco& b, Mecanismo& m, DecisionSitio d, uint32_t& t, uint32_t seg, bool permiso = true) {
  for (uint32_t i = 0; i < seg * 10; i++) {
    uint32_t ts = t + i / 10;
    SalidasBanco s = b.paso(m.leer(permiso), d, ts);
    m.mover(s, 0.1f);
  }
  t += seg;
}

static void prueba_arranque_busca_resguardo() {
  std::puts("arranque en posición intermedia -> resguarda");
  Parametros p; Banco b(&p); Mecanismo m; m.pos = 40; uint32_t t = 1000;
  correr(b, m, calma(), t, 1);
  CHECK(b.estado() == Estado::RESGUARDANDO);
  correr(b, m, calma(), t, 15);
  CHECK(m.pos == 0);
  CHECK(b.estado() == Estado::RESGUARDADO || b.estado() == Estado::DESPLEGANDO);
}

static void prueba_ciclo_normal() {
  std::puts("ciclo normal: despliega con calma, resguarda con riesgo");
  Parametros p; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, calma(), t, 30);
  CHECK(b.estado() == Estado::CAPTANDO);
  CHECK(m.pos == 100);
  correr(b, m, riesgo(), t, 30);
  CHECK(b.estado() == Estado::RESGUARDADO);
  CHECK(m.pos == 0);
  CHECK(b.maniobras() == 2);
}

static void prueba_histeresis() {
  std::puts("zona intermedia: no despliega, pero tampoco resguarda lo desplegado");
  Parametros p; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, intermedio(), t, 30);
  CHECK(b.estado() == Estado::RESGUARDADO);
  correr(b, m, calma(), t, 30);
  CHECK(b.estado() == Estado::CAPTANDO);
  correr(b, m, intermedio(), t, 30);
  CHECK(b.estado() == Estado::CAPTANDO);
}

static void prueba_inversion_con_pausa() {
  std::puts("riesgo durante despliegue: pausa antes de invertir");
  Parametros p; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, calma(), t, 5);            // a mitad de carrera
  CHECK(b.estado() == Estado::DESPLEGANDO);
  SalidasBanco s = b.paso(m.leer(), riesgo(), t);
  CHECK(b.estado() == Estado::PAUSA);
  CHECK(!s.marcha);
  correr(b, m, riesgo(), t, 1);
  CHECK(b.estado() == Estado::PAUSA);      // pausa de 2 s
  correr(b, m, riesgo(), t, 30);
  CHECK(b.estado() == Estado::RESGUARDADO);
}

static void prueba_atasco_despliegue() {
  std::puts("atasco en despliegue: falla enclavada y vuelta a lo seguro");
  Parametros p; p.tiempo_max_maniobra_s = 30; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, calma(), t, 2);
  m.atascado = true;
  correr(b, m, calma(), t, 35);
  CHECK(b.fallas() & F_TIEMPO_DESPLIEGUE);
  m.atascado = false;
  correr(b, m, calma(), t, 40);
  CHECK(b.estado() == Estado::RESGUARDADO);
  correr(b, m, calma(), t, 120);
  CHECK(b.estado() == Estado::RESGUARDADO);  // no reintenta sin reconocimiento
  b.reconocer_falla();
  correr(b, m, calma(), t, 30);
  CHECK(b.estado() == Estado::CAPTANDO);
}

static void prueba_atasco_resguardo() {
  std::puts("atasco al resguardar: FALLA con motor apagado");
  Parametros p; p.tiempo_max_maniobra_s = 30; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, calma(), t, 30);
  m.atascado = true;
  correr(b, m, riesgo(), t, 40);
  CHECK(b.estado() == Estado::FALLA);
  CHECK(b.fallas() & F_TIEMPO_RESGUARDO);
  SalidasBanco s = b.paso(m.leer(), riesgo(), t);
  CHECK(!s.marcha);
}

static void prueba_cable_cortado() {
  std::puts("final NC cortado estando resguardado: FALLA por finales incoherentes");
  Parametros p; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, riesgo(), t, 2);
  m.cable_cortado_desplegado = true;
  correr(b, m, calma(), t, 2);
  CHECK(b.estado() == Estado::FALLA);
  CHECK(b.fallas() & F_FINALES_INCOHERENTES);
  b.reconocer_falla();
  correr(b, m, calma(), t, 1);
  CHECK(b.estado() == Estado::FALLA);  // la causa sigue: no se puede reconocer
}

static void prueba_permiso() {
  std::puts("sin permiso (LOCAL / parada): nunca hay marcha");
  Parametros p; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, calma(), t, 5);
  for (int i = 0; i < 50; i++) {
    SalidasBanco s = b.paso(m.leer(false), calma(), t + i);
    CHECK(!s.marcha);
  }
  CHECK(b.estado() == Estado::LOCAL);
  t += 50;
  correr(b, m, riesgo(), t, 30);
  CHECK(b.estado() == Estado::RESGUARDADO);
}

static void prueba_retencion() {
  std::puts("retención remota: resguarda aunque haya calma");
  Parametros p; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, calma(), t, 30);
  b.retenido = true;
  correr(b, m, calma(), t, 30);
  CHECK(b.estado() == Estado::RESGUARDADO);
  b.retenido = false;
  correr(b, m, calma(), t, 90);
  CHECK(b.estado() == Estado::CAPTANDO);
}

static void prueba_min_entre_maniobras() {
  std::puts("tiempo mínimo entre maniobras");
  Parametros p; p.min_entre_maniobras_s = 60; Banco b(&p); Mecanismo m; uint32_t t = 1000;
  correr(b, m, calma(), t, 30);
  correr(b, m, riesgo(), t, 25);
  CHECK(b.estado() == Estado::RESGUARDADO);
  correr(b, m, calma(), t, 20);
  CHECK(b.estado() == Estado::RESGUARDADO);   // aún dentro de los 60 s
  correr(b, m, calma(), t, 60);
  CHECK(b.estado() == Estado::CAPTANDO);
}

static void prueba_sitio() {
  std::puts("sitio: umbrales, calma mínima, dato inválido y batería");
  Parametros p; p.calma_minima_s = 600; Sitio s(&p);
  EntradasSitio e{true, 10, 8, false, 0};
  DecisionSitio d = s.evaluar(e, 0);
  CHECK(d.exige_resguardo == false);
  CHECK(d.permite_desplegar == false);            // al arranque se exige calma
  CHECK(s.motivo() & M_CALMA_INSUFICIENTE);
  d = s.evaluar(e, 600);
  CHECK(d.permite_desplegar);
  e.rafaga_kmh = 50;
  d = s.evaluar(e, 700);
  CHECK(d.exige_resguardo && (s.motivo() & M_RAFAGA));
  e.rafaga_kmh = 10;
  d = s.evaluar(e, 800);
  CHECK(!d.exige_resguardo && !d.permite_desplegar);
  CHECK(s.segundos_para_habilitar(800) == 500);
  d = s.evaluar(e, 1300);
  CHECK(d.permite_desplegar);
  e.media_kmh = 30;                                // entre rehabilitación y resguardo
  d = s.evaluar(e, 1400);
  CHECK(!d.exige_resguardo && !d.permite_desplegar);
  CHECK(s.motivo() & M_SOBRE_REHABILITACION);
  e.media_kmh = 8; e.viento_valido = false;
  d = s.evaluar(e, 1500);
  CHECK(d.exige_resguardo && (s.motivo() & M_VIENTO_SIN_DATO));
  e.viento_valido = true; e.bateria_valida = true; e.bateria_v = 12.0f;
  d = s.evaluar(e, 3000);
  CHECK(d.exige_resguardo && (s.motivo() & M_BATERIA_BAJA));
  e.bateria_v = 12.6f;                             // dentro de la histéresis
  d = s.evaluar(e, 3001);
  CHECK(d.exige_resguardo);
  e.bateria_v = 13.0f;
  d = s.evaluar(e, 3002);
  CHECK(!d.exige_resguardo);
}

static void prueba_viento() {
  std::puts("viento: ráfaga 3 s, media 10 min y vigencia");
  Viento v;
  for (uint32_t t = 0; t < 600; t++) v.muestra(10, 225, t);
  CHECK(v.rafaga() > 9.9f && v.rafaga() < 10.1f);
  CHECK(v.media() > 9.9f && v.media() < 10.1f);
  v.muestra(70, 225, 600);
  v.muestra(70, 225, 601);
  v.muestra(70, 225, 602);
  CHECK(v.rafaga() > 69.0f);
  CHECK(v.media() < 12.0f);                         // una ráfaga no mueve la media
  CHECK(v.valido(610, 10));
  CHECK(!v.valido(620, 10));
  for (uint32_t t = 603; t < 1300; t++) v.muestra(40, 225, t);
  CHECK(v.media() > 39.0f && v.media() < 41.0f);
}

static void prueba_contador() {
  std::puts("contador de balancín con antirrebote");
  Contador c(50);
  uint32_t t = 0;
  for (int pulso = 0; pulso < 5; pulso++) {
    for (int i = 0; i < 5; i++) { c.muestra(i % 2 == 0, t); t += 5; }  // rebote
    for (int i = 0; i < 20; i++) { c.muestra(true, t); t += 5; }
    for (int i = 0; i < 20; i++) { c.muestra(false, t); t += 5; }
  }
  CHECK(c.cuenta() == 5);
}

static void prueba_envolvente() {
  std::puts("parámetros remotos recortados a la envolvente");
  Parametros actual, prop; Envolvente env;
  prop.rafaga_resguardo_kmh = 120; prop.medio_resguardo_kmh = 90;
  prop.medio_rehabilitar_kmh = 80; prop.calma_minima_s = 5;
  bool rec = aplicar_parametros(actual, prop, env);
  CHECK(rec);
  CHECK(actual.rafaga_resguardo_kmh == env.rafaga_max_kmh);
  CHECK(actual.medio_resguardo_kmh == env.medio_max_kmh);
  CHECK(actual.medio_rehabilitar_kmh <= actual.medio_resguardo_kmh - env.margen_rehab_min_kmh);
  CHECK(actual.calma_minima_s == env.calma_min_s);
}

int main() {
  prueba_arranque_busca_resguardo();
  prueba_ciclo_normal();
  prueba_histeresis();
  prueba_inversion_con_pausa();
  prueba_atasco_despliegue();
  prueba_atasco_resguardo();
  prueba_cable_cortado();
  prueba_permiso();
  prueba_retencion();
  prueba_min_entre_maniobras();
  prueba_sitio();
  prueba_viento();
  prueba_contador();
  prueba_envolvente();
  std::printf("\n%d comprobaciones, %d fallas\n", total, fallos);
  return fallos ? EXIT_FAILURE : EXIT_SUCCESS;
}
