// Niebla — configuración por sitio y por PLC.
// Editar antes de cargar el firmware. Todo valor marcado [ING] debe salir de la
// ingeniería del sitio (cálculo estructural y prueba del mecanismo).
#pragma once
#include <stdint.h>

// ---------------- Rol del PLC
// 36 m²: un PLC principal (bancos 1-2).
// 72 m²: PLC principal (bancos 1-2, sensores RS485) + PLC secundario (bancos 3-4).
#define ROL_PRINCIPAL 0
#define ROL_SECUNDARIO 1
#ifndef ROL_PLC
#define ROL_PLC ROL_PRINCIPAL
#endif

static const uint8_t N_BANCOS_PLC = 2;
static const uint8_t PRIMER_BANCO = (ROL_PLC == ROL_PRINCIPAL) ? 1 : 3;

// ---------------- Red (Ethernet del tablero, sin salida a internet)
#define IP_PRINCIPAL 192, 168, 50, 10
#define IP_SECUNDARIO 192, 168, 50, 11
#define IP_MASCARA 255, 255, 255, 0
#define IP_PUERTA 192, 168, 50, 1
static const bool HAY_SECUNDARIO = false;  // true en 72 m²

// ---------------- Bus RS485 de campo (sólo PLC principal), 9600 8N1
static const uint32_t RS485_BAUD = 9600;
static const uint8_t ADDR_VIENTO = 1;      // anemómetro y veleta
static const uint8_t ADDR_PLUVIO = 2;      // pluviómetro de balancín RS485
static const uint8_t ADDR_NIVEL = 3;       // transmisor de nivel del estanque
static const uint8_t ADDR_THR = 4;         // temperatura y humedad
// Registros de cada equipo: CONFIRMAR con la hoja de datos del modelo comprado.
static const uint16_t REG_VIENTO_VEL = 0x0000;   // m/s x10
static const uint16_t REG_VIENTO_DIR = 0x0001;   // grados
static const uint16_t REG_PLUVIO_ACUM = 0x0000;  // mm x10 (u16)
static const uint16_t REG_NIVEL_MM = 0x0004;     // mm
static const uint16_t REG_THR_HR = 0x0000;       // % x10
static const uint16_t REG_THR_T = 0x0001;        // °C x10 (int16)

// ---------------- Entradas del Opta (I1..I8 = A0..A7)
// Finales de carrera NC: el contacto abierto (o el cable cortado) se lee como "alcanzado".
#define PIN_FC_RESG_B1 A0
#define PIN_FC_DESP_B1 A1
#define PIN_FC_RESG_B2 A2
#define PIN_FC_DESP_B2 A3
#define PIN_BALANCIN_B1 A4
#define PIN_BALANCIN_B2 A5
#define PIN_FLOTADOR A6      // NC: abierto = nivel alto
#define PIN_PERMISO A7       // cadena: selector REMOTO + parada liberada (24 V = permiso)

// ---------------- Salidas (relés D0..D3)
// Cada banco usa MARCHA y SENTIDO hacia un módulo inversor con enclavamiento
// eléctrico y finales de carrera cableados también en serie (límite por hardware).
#define PIN_MARCHA_B1 D0
#define PIN_SENTIDO_B1 D1
#define PIN_MARCHA_B2 D2
#define PIN_SENTIDO_B2 D3

// ---------------- Tiempos del ciclo
static const uint32_t CICLO_MS = 50;             // lógica a 20 Hz
static const uint32_t SONDEO_VIENTO_MS = 1000;   // 1 Hz
static const uint32_t SONDEO_LENTO_MS = 10000;   // lluvia, nivel, T/HR
static const uint32_t ENVIO_PAR_MS = 2000;       // principal -> secundario
static const uint32_t WATCHDOG_MS = 8000;

// ---------------- Parámetros iniciales [ING]
// Se cargan al arranque; el registrador puede ajustarlos dentro de la envolvente.
static const float P_RAFAGA_KMH = 45.0f;
static const float P_MEDIO_KMH = 35.0f;
static const float P_REHAB_KMH = 25.0f;
static const uint32_t P_CALMA_S = 1800;
static const uint32_t P_MANIOBRA_MAX_S = 90;     // [ING] medido en banco + 30 %
static const float P_BATERIA_RESERVA_V = 12.4f;
