// Niebla — mapa de registros Modbus TCP del PLC (servidor, puerto 502).
// Debe coincidir con registrador/niebla/mapa.py y docs/mapa_registros.md.
#pragma once

namespace mapa {

// ---------------- Registros de entrada (función 04, sólo lectura)
enum Entrada : int {
  IR_VERSION = 0,            // 100 = 1.0.0
  IR_ROL = 1,                // 0 principal, 1 secundario
  IR_UPTIME_H = 2,           // segundos desde arranque (u32, palabra alta)
  IR_UPTIME_L = 3,
  IR_VIENTO_INST = 4,        // km/h x10
  IR_VIENTO_RAFAGA = 5,      // km/h x10 (media móvil 3 s)
  IR_VIENTO_MEDIO = 6,       // km/h x10 (media 10 min)
  IR_VIENTO_DIR = 7,         // grados
  IR_VIENTO_VALIDO = 8,      // 0/1
  IR_MOTIVO = 9,             // bitmask niebla::Motivo
  IR_SEG_HABILITAR = 10,     // segundos de calma restantes
  IR_LLUVIA_H = 11,          // lluvia acumulada del pluviómetro, mm x10 (u32)
  IR_LLUVIA_L = 12,
  IR_NIVEL_MM = 13,          // nivel de estanque en mm (0xFFFF = sin dato)
  IR_FLOTADOR_ALTO = 14,     // 1 = rebalse inminente
  IR_TEMP = 15,              // °C x10 (int16)
  IR_HR = 16,                // % x10
  IR_SENSORES = 17,          // bits: 0 viento, 1 lluvia, 2 nivel, 3 T/HR, 4 enlace par
  IR_BATERIA_MV = 18,        // tensión usada por la lógica (0 = sin dato vigente)
  IR_ORDEN_APLICADA = 19,    // eco de HR_ORDEN_SEQ tras ejecutar la orden
  IR_PARAM_RECORTADO = 20,   // 1 si los últimos parámetros se recortaron
  IR_PERMISO = 21,           // 1 = selector REMOTO y parada liberada
  IR_BANCO_BASE = 30,        // bloque de 10 registros por banco
  IR_BANCO_PASO = 10,
  // offsets dentro del bloque de banco
  B_ID = 0,                  // número global de banco (1..4)
  B_ESTADO = 1,              // niebla::Estado
  B_FALLAS = 2,              // bitmask niebla::Falla
  B_FINALES = 3,             // bit0 resguardado, bit1 desplegado
  B_BALANCIN_H = 4,          // cuenta de balancín (u32)
  B_BALANCIN_L = 5,
  B_MANIOBRAS_H = 6,
  B_MANIOBRAS_L = 7,
  B_SEG_ESTADO = 8,
  B_SALIDAS = 9,             // bit0 marcha, bit1 sentido desplegar
  IR_TOTAL = 50,
};

// ---------------- Registros de retención (función 03/06/16, lectura-escritura)
enum Retencion : int {
  HR_LATIDO = 0,             // el registrador lo incrementa (sólo diagnóstico)
  HR_ORDEN_SEQ = 1,          // incrementar para emitir una orden
  HR_ORDEN_BANCO = 2,        // 1..4, 0 = todos los bancos de este PLC
  HR_ORDEN_CODIGO = 3,       // niebla::Orden
  HR_BATERIA_MV = 4,         // tensión de batería leída por el registrador
  HR_BATERIA_SEQ = 5,        // incrementar con cada dato nuevo
  HR_PARAM_RAFAGA = 10,      // km/h x10
  HR_PARAM_MEDIO = 11,       // km/h x10
  HR_PARAM_REHAB = 12,       // km/h x10
  HR_PARAM_CALMA_MIN = 13,   // minutos
  HR_PARAM_SEQ = 14,         // incrementar para aplicar 10..13
  // Bloque que el PLC principal escribe en el secundario
  HR_PAR_RAFAGA = 30,
  HR_PAR_MEDIO = 31,
  HR_PAR_DIR = 32,
  HR_PAR_VALIDO = 33,
  HR_PAR_SEQ = 34,
  HR_TOTAL = 40,
};

}  // namespace mapa
