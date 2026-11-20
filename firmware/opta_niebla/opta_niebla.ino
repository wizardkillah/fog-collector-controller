// Niebla — firmware del PLC de campo (Arduino Opta RS485 / Opta WiFi)
//
// Responsabilidades del PLC (y sólo del PLC):
//   * leer anemómetro, pluviómetro, nivel y T/HR por RS485 (rol principal)
//   * decidir resguardo/despliegue de cada banco (niebla_core)
//   * mover los mecanismos con tiempo máximo y finales de carrera NC
//   * contar los pulsos de los balancines de captación
//   * publicar todo por Modbus TCP para el registrador (Raspberry Pi)
//
// El PLC funciona igual si el registrador, la red o internet no están.
// Placa: "Arduino Opta" (core Arduino Mbed OS Opta Boards).
// Bibliotecas: ArduinoRS485, ArduinoModbus (Arduino), Ethernet (incluida en el core).

#include <Arduino.h>
#include <ArduinoRS485.h>
#include <ArduinoModbus.h>
#include <Ethernet.h>
#include <mbed.h>

#include "config_sitio.h"
#include "mapa_registros.h"
#include "niebla_core.h"

using namespace niebla;

// ------------------------------------------------------------------ estado global
static Parametros P;
static Envolvente ENV;
static Viento viento;
static Sitio sitio(&P);
static Banco bancos[N_BANCOS_PLC] = {Banco(&P), Banco(&P)};
static Contador balancin[N_BANCOS_PLC];

struct PinesBanco {
  int resg, desp, bal, marcha, sentido, led;
};
static const PinesBanco PINES[N_BANCOS_PLC] = {
    {PIN_FC_RESG_B1, PIN_FC_DESP_B1, PIN_BALANCIN_B1, PIN_MARCHA_B1, PIN_SENTIDO_B1, LED_D0},
    {PIN_FC_RESG_B2, PIN_FC_DESP_B2, PIN_BALANCIN_B2, PIN_MARCHA_B2, PIN_SENTIDO_B2, LED_D2},
};

static EthernetServer servidorEth(502);
static ModbusTCPServer mb;
static EthernetClient cliente;
static EthernetClient clientePar;
static ModbusTCPClient par(clientePar);

// Tiempo monotónico en segundos, inmune al desborde de millis() (49,7 días).
static uint32_t t_seg = 0;
static uint32_t ult_ms = 0, acum_ms = 0;

// Sensores lentos (rol principal)
static uint32_t lluvia_x10 = 0;
static uint16_t nivel_mm = 0xFFFF;
static int16_t temp_x10 = 0;
static uint16_t hr_x10 = 0;
static uint16_t sensores_ok = 0;

// Datos remotos
static uint16_t ult_orden_seq = 0, ult_param_seq = 0, ult_bat_seq = 0, ult_par_seq = 0, par_seq_tx = 0;
static uint32_t t_bat = 0, t_par = 0;
static bool hay_bat = false, hay_par = false;
static float bat_v = 0, par_rafaga = 0, par_medio = 0, par_dir = 0;
static bool par_valido = false;
static bool param_recortado = false;
static bool permiso = false;

static uint32_t t_ciclo = 0, t_viento = 0, t_lento = 0, t_envio = 0;

// ------------------------------------------------------------------ utilidades
static void actualizar_tiempo() {
  uint32_t ahora = millis();
  acum_ms += ahora - ult_ms;  // resta sin signo: correcta tras el desborde
  ult_ms = ahora;
  while (acum_ms >= 1000) {
    acum_ms -= 1000;
    t_seg++;
  }
}

static uint16_t x10(float v) {
  if (v < 0) v = 0;
  if (v > 6553.4f) v = 6553.4f;
  return (uint16_t)(v * 10.0f + 0.5f);
}

static void escribir_u32(int reg_alto, uint32_t v) {
  mb.inputRegisterWrite(reg_alto, (uint16_t)(v >> 16));
  mb.inputRegisterWrite(reg_alto + 1, (uint16_t)(v & 0xFFFF));
}

static bool fc_alcanzado(int pin) { return digitalRead(pin) == LOW; }  // NC abierto = alcanzado

// ------------------------------------------------------------------ RS485 (rol principal)
static void leer_viento() {
  long vel = ModbusRTUClient.holdingRegisterRead(ADDR_VIENTO, REG_VIENTO_VEL);
  long dir = ModbusRTUClient.holdingRegisterRead(ADDR_VIENTO, REG_VIENTO_DIR);
  if (vel >= 0) {
    float kmh = (vel / 10.0f) * 3.6f;  // m/s x10 -> km/h
    viento.muestra(kmh, dir >= 0 ? (float)dir : viento.direccion(), t_seg);
  }
  // Si falla la lectura no se inventa un valor: la vigencia caduca y el sitio resguarda.
}

static void leer_lentos() {
  long v;
  sensores_ok &= (uint16_t)~0x0E;
  v = ModbusRTUClient.holdingRegisterRead(ADDR_PLUVIO, REG_PLUVIO_ACUM);
  if (v >= 0) { lluvia_x10 = (uint32_t)v; sensores_ok |= 0x02; }
  v = ModbusRTUClient.holdingRegisterRead(ADDR_NIVEL, REG_NIVEL_MM);
  if (v >= 0) { nivel_mm = (uint16_t)v; sensores_ok |= 0x04; } else nivel_mm = 0xFFFF;
  long hr = ModbusRTUClient.holdingRegisterRead(ADDR_THR, REG_THR_HR);
  long t = ModbusRTUClient.holdingRegisterRead(ADDR_THR, REG_THR_T);
  if (hr >= 0 && t >= 0) { hr_x10 = (uint16_t)hr; temp_x10 = (int16_t)(uint16_t)t; sensores_ok |= 0x08; }
}

// Principal -> secundario: el secundario resguarda si este dato envejece.
static void enviar_a_secundario() {
  static const IPAddress ip_sec(IP_SECUNDARIO);
  if (!par.connected()) {
    par.stop();
    if (!par.begin(ip_sec, 502)) return;
  }
  bool valido = viento.valido(t_seg, P.viento_vigencia_s);
  par_seq_tx++;
  par.beginTransmission(HOLDING_REGISTERS, mapa::HR_PAR_RAFAGA, 5);
  par.write(x10(viento.rafaga()));
  par.write(x10(viento.media()));
  par.write((uint16_t)viento.direccion());
  par.write(valido ? 1 : 0);
  par.write(par_seq_tx);
  if (!par.endTransmission()) par.stop();
}

// ------------------------------------------------------------------ entradas remotas
static void procesar_retencion() {
  // Órdenes (se ejecutan una vez por cada nuevo número de secuencia)
  uint16_t seq = (uint16_t)mb.holdingRegisterRead(mapa::HR_ORDEN_SEQ);
  if (seq != ult_orden_seq) {
    ult_orden_seq = seq;
    uint16_t banco = (uint16_t)mb.holdingRegisterRead(mapa::HR_ORDEN_BANCO);
    Orden o = (Orden)mb.holdingRegisterRead(mapa::HR_ORDEN_CODIGO);
    for (uint8_t i = 0; i < N_BANCOS_PLC; i++) {
      if (banco != 0 && banco != PRIMER_BANCO + i) continue;
      if (o == Orden::RESGUARDAR) bancos[i].retenido = true;
      else if (o == Orden::HABILITAR) bancos[i].retenido = false;
      else if (o == Orden::RECONOCER_FALLA) bancos[i].reconocer_falla();
    }
    mb.inputRegisterWrite(mapa::IR_ORDEN_APLICADA, seq);
  }

  // Parámetros (0 = mantener el valor actual)
  seq = (uint16_t)mb.holdingRegisterRead(mapa::HR_PARAM_SEQ);
  if (seq != ult_param_seq) {
    ult_param_seq = seq;
    Parametros prop = P;
    long r = mb.holdingRegisterRead(mapa::HR_PARAM_RAFAGA);
    long m = mb.holdingRegisterRead(mapa::HR_PARAM_MEDIO);
    long h = mb.holdingRegisterRead(mapa::HR_PARAM_REHAB);
    long c = mb.holdingRegisterRead(mapa::HR_PARAM_CALMA_MIN);
    if (r > 0) prop.rafaga_resguardo_kmh = r / 10.0f;
    if (m > 0) prop.medio_resguardo_kmh = m / 10.0f;
    if (h > 0) prop.medio_rehabilitar_kmh = h / 10.0f;
    if (c > 0) prop.calma_minima_s = (uint32_t)c * 60;
    param_recortado = aplicar_parametros(P, prop, ENV);
  }

  // Batería (dato del registrador; si envejece se ignora)
  seq = (uint16_t)mb.holdingRegisterRead(mapa::HR_BATERIA_SEQ);
  if (seq != ult_bat_seq) {
    ult_bat_seq = seq;
    bat_v = mb.holdingRegisterRead(mapa::HR_BATERIA_MV) / 1000.0f;
    t_bat = t_seg;
    hay_bat = true;
  }

  // Viento recibido del principal (rol secundario)
  if (ROL_PLC == ROL_SECUNDARIO) {
    seq = (uint16_t)mb.holdingRegisterRead(mapa::HR_PAR_SEQ);
    if (seq != ult_par_seq) {
      ult_par_seq = seq;
      par_rafaga = mb.holdingRegisterRead(mapa::HR_PAR_RAFAGA) / 10.0f;
      par_medio = mb.holdingRegisterRead(mapa::HR_PAR_MEDIO) / 10.0f;
      par_dir = (float)mb.holdingRegisterRead(mapa::HR_PAR_DIR);
      par_valido = mb.holdingRegisterRead(mapa::HR_PAR_VALIDO) == 1;
      t_par = t_seg;
      hay_par = true;
    }
  }
}

// ------------------------------------------------------------------ control
static void aplicar_salidas(uint8_t i, const SalidasBanco& s) {
  const PinesBanco& p = PINES[i];
  if (!s.marcha) {
    digitalWrite(p.marcha, LOW);           // primero se corta la marcha
    digitalWrite(p.sentido, s.sentido_desplegar ? HIGH : LOW);
  } else {
    digitalWrite(p.sentido, s.sentido_desplegar ? HIGH : LOW);
    digitalWrite(p.marcha, HIGH);
  }
  digitalWrite(p.led, s.marcha ? HIGH : LOW);
}

static EntradasSitio entradas_sitio() {
  EntradasSitio e;
  if (ROL_PLC == ROL_PRINCIPAL) {
    e.viento_valido = viento.valido(t_seg, P.viento_vigencia_s);
    e.rafaga_kmh = viento.rafaga();
    e.media_kmh = viento.media();
  } else {
    e.viento_valido = hay_par && par_valido && (t_seg - t_par) <= P.viento_vigencia_s;
    e.rafaga_kmh = par_rafaga;
    e.media_kmh = par_medio;
  }
  e.bateria_valida = hay_bat && (t_seg - t_bat) <= P.bateria_vigencia_s;
  e.bateria_v = bat_v;
  return e;
}

static void controlar() {
  EntradasSitio es = entradas_sitio();
  DecisionSitio d = sitio.evaluar(es, t_seg);
  permiso = digitalRead(PIN_PERMISO) == HIGH;
  for (uint8_t i = 0; i < N_BANCOS_PLC; i++) {
    EntradasBanco e;
    e.fc_resguardado = fc_alcanzado(PINES[i].resg);
    e.fc_desplegado = fc_alcanzado(PINES[i].desp);
    e.permiso = permiso;
    aplicar_salidas(i, bancos[i].paso(e, d, t_seg));
  }
}

static void publicar() {
  mb.inputRegisterWrite(mapa::IR_VERSION, VERSION_FIRMWARE);
  mb.inputRegisterWrite(mapa::IR_ROL, ROL_PLC);
  escribir_u32(mapa::IR_UPTIME_H, t_seg);
  EntradasSitio es = entradas_sitio();
  float inst = (ROL_PLC == ROL_PRINCIPAL) ? viento.instantaneo() : es.rafaga_kmh;
  float dir = (ROL_PLC == ROL_PRINCIPAL) ? viento.direccion() : par_dir;
  mb.inputRegisterWrite(mapa::IR_VIENTO_INST, x10(inst));
  mb.inputRegisterWrite(mapa::IR_VIENTO_RAFAGA, x10(es.rafaga_kmh));
  mb.inputRegisterWrite(mapa::IR_VIENTO_MEDIO, x10(es.media_kmh));
  mb.inputRegisterWrite(mapa::IR_VIENTO_DIR, (uint16_t)dir);
  mb.inputRegisterWrite(mapa::IR_VIENTO_VALIDO, es.viento_valido ? 1 : 0);
  uint16_t motivo = sitio.motivo() | (permiso ? 0 : M_SIN_PERMISO);
  mb.inputRegisterWrite(mapa::IR_MOTIVO, motivo);
  uint32_t seg = sitio.segundos_para_habilitar(t_seg);
  mb.inputRegisterWrite(mapa::IR_SEG_HABILITAR, (uint16_t)(seg > 65535 ? 65535 : seg));
  escribir_u32(mapa::IR_LLUVIA_H, lluvia_x10);
  mb.inputRegisterWrite(mapa::IR_NIVEL_MM, nivel_mm);
  mb.inputRegisterWrite(mapa::IR_FLOTADOR_ALTO, fc_alcanzado(PIN_FLOTADOR) ? 1 : 0);
  mb.inputRegisterWrite(mapa::IR_TEMP, (uint16_t)temp_x10);
  mb.inputRegisterWrite(mapa::IR_HR, hr_x10);
  uint16_t sens = sensores_ok & (uint16_t)~0x11;
  if (es.viento_valido) sens |= (ROL_PLC == ROL_PRINCIPAL) ? 0x01 : 0x10;
  mb.inputRegisterWrite(mapa::IR_SENSORES, sens);
  mb.inputRegisterWrite(mapa::IR_BATERIA_MV, es.bateria_valida ? (uint16_t)(bat_v * 1000.0f) : 0);
  mb.inputRegisterWrite(mapa::IR_PARAM_RECORTADO, param_recortado ? 1 : 0);
  mb.inputRegisterWrite(mapa::IR_PERMISO, permiso ? 1 : 0);

  for (uint8_t i = 0; i < N_BANCOS_PLC; i++) {
    int b = mapa::IR_BANCO_BASE + i * mapa::IR_BANCO_PASO;
    const Banco& k = bancos[i];
    mb.inputRegisterWrite(b + mapa::B_ID, PRIMER_BANCO + i);
    mb.inputRegisterWrite(b + mapa::B_ESTADO, (uint16_t)k.estado());
    mb.inputRegisterWrite(b + mapa::B_FALLAS, k.fallas());
    uint16_t fin = (fc_alcanzado(PINES[i].resg) ? 1 : 0) | (fc_alcanzado(PINES[i].desp) ? 2 : 0);
    mb.inputRegisterWrite(b + mapa::B_FINALES, fin);
    escribir_u32(b + mapa::B_BALANCIN_H, balancin[i].cuenta());
    escribir_u32(b + mapa::B_MANIOBRAS_H, k.maniobras());
    uint32_t se = k.segundos_en_estado(t_seg);
    mb.inputRegisterWrite(b + mapa::B_SEG_ESTADO, (uint16_t)(se > 65535 ? 65535 : se));
    uint16_t sal = (digitalRead(PINES[i].marcha) == HIGH ? 1 : 0) | (digitalRead(PINES[i].sentido) == HIGH ? 2 : 0);
    mb.inputRegisterWrite(b + mapa::B_SALIDAS, sal);
  }
}

static void atender_modbus() {
  if (!cliente || !cliente.connected()) {
    EthernetClient nuevo = servidorEth.available();
    if (nuevo) {
      cliente = nuevo;
      mb.accept(cliente);
    }
  }
  mb.poll();
}

// ------------------------------------------------------------------ setup / loop
void setup() {
  // Salidas: nivel bajo ANTES de configurarlas (evita pulsos al arrancar).
  for (uint8_t i = 0; i < N_BANCOS_PLC; i++) {
    digitalWrite(PINES[i].marcha, LOW);
    digitalWrite(PINES[i].sentido, LOW);
    pinMode(PINES[i].marcha, OUTPUT);
    pinMode(PINES[i].sentido, OUTPUT);
    pinMode(PINES[i].led, OUTPUT);
    pinMode(PINES[i].resg, INPUT);
    pinMode(PINES[i].desp, INPUT);
    pinMode(PINES[i].bal, INPUT);
  }
  pinMode(PIN_FLOTADOR, INPUT);
  pinMode(PIN_PERMISO, INPUT);

  P.rafaga_resguardo_kmh = P_RAFAGA_KMH;
  P.medio_resguardo_kmh = P_MEDIO_KMH;
  P.medio_rehabilitar_kmh = P_REHAB_KMH;
  P.calma_minima_s = P_CALMA_S;
  P.tiempo_max_maniobra_s = P_MANIOBRA_MAX_S;
  P.bateria_reserva_v = P_BATERIA_RESERVA_V;
  Parametros inicial = P;
  aplicar_parametros(P, inicial, ENV);  // la configuración también respeta la envolvente

  IPAddress ip = (ROL_PLC == ROL_PRINCIPAL) ? IPAddress(IP_PRINCIPAL) : IPAddress(IP_SECUNDARIO);
  IPAddress puerta(IP_PUERTA), mascara(IP_MASCARA);
  Ethernet.begin(ip, puerta, puerta, mascara);
  servidorEth.begin();
  mb.begin();
  mb.configureInputRegisters(0, mapa::IR_TOTAL);
  mb.configureHoldingRegisters(0, mapa::HR_TOTAL);

  if (ROL_PLC == ROL_PRINCIPAL) {
    // Tiempos de guarda RS485 según la norma de Modbus RTU (3,5 caracteres).
    const float t_bit = 1.0f / RS485_BAUD;
    const int guarda_us = (int)(t_bit * 10 * 3.5f * 1e6f);
    RS485.setDelays(guarda_us, guarda_us);
    ModbusRTUClient.begin(RS485_BAUD, SERIAL_8N1);
    ModbusRTUClient.setTimeout(200);
    par.setTimeout(300);
  }

  ult_ms = millis();
  mbed::Watchdog::get_instance().start(WATCHDOG_MS);
}

void loop() {
  mbed::Watchdog::get_instance().kick();
  actualizar_tiempo();
  atender_modbus();

  const uint32_t ahora = millis();
  for (uint8_t i = 0; i < N_BANCOS_PLC; i++) balancin[i].muestra(digitalRead(PINES[i].bal) == HIGH, ahora);

  if (ROL_PLC == ROL_PRINCIPAL) {
    if (ahora - t_viento >= SONDEO_VIENTO_MS) { t_viento = ahora; leer_viento(); }
    if (ahora - t_lento >= SONDEO_LENTO_MS) { t_lento = ahora; leer_lentos(); }
    if (HAY_SECUNDARIO && ahora - t_envio >= ENVIO_PAR_MS) { t_envio = ahora; enviar_a_secundario(); }
  }

  if (ahora - t_ciclo >= CICLO_MS) {
    t_ciclo = ahora;
    procesar_retencion();
    controlar();
    publicar();
  }
}
