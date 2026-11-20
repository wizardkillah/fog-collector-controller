# Mapa de registros Modbus TCP (PLC Opta, puerto 502)

Generado desde `registrador/niebla/mapa.py`. Debe coincidir con `firmware/opta_niebla/mapa_registros.h`.

## Registros de entrada (función 04)

| Dir. | Nombre | Descripción |
|---|---|---|
| 0 | `IR_VERSION` | Versión de firmware (100 = 1.0.0) |
| 1 | `IR_ROL` | 0 principal, 1 secundario |
| 2 | `IR_UPTIME_H` | Segundos desde arranque (u32, 2 registros) |
| 4 | `IR_VIENTO_INST` | Viento instantáneo, km/h ×10 |
| 5 | `IR_VIENTO_RAFAGA` | Ráfaga 3 s, km/h ×10 |
| 6 | `IR_VIENTO_MEDIO` | Media 10 min, km/h ×10 |
| 7 | `IR_VIENTO_DIR` | Dirección, grados |
| 8 | `IR_VIENTO_VALIDO` | 1 = dato vigente |
| 9 | `IR_MOTIVO` | Motivos de resguardo (bitmask) |
| 10 | `IR_SEG_HABILITAR` | Segundos de calma restantes |
| 11 | `IR_LLUVIA_H` | Lluvia acumulada, mm ×10 (u32) |
| 13 | `IR_NIVEL_MM` | Nivel de estanque en mm (65535 = sin dato) |
| 14 | `IR_FLOTADOR_ALTO` | 1 = nivel alto |
| 15 | `IR_TEMP` | °C ×10 (con signo) |
| 16 | `IR_HR` | % ×10 |
| 17 | `IR_SENSORES` | Bits: 0 viento, 1 lluvia, 2 nivel, 3 T/HR, 4 enlace par |
| 18 | `IR_BATERIA_MV` | Tensión usada por la lógica (0 = sin dato) |
| 19 | `IR_ORDEN_APLICADA` | Eco de la última orden ejecutada |
| 20 | `IR_PARAM_RECORTADO` | 1 = parámetros recortados a la envolvente |
| 21 | `IR_PERMISO` | 1 = REMOTO y parada liberada |
| 30 | `IR_BANCO_BASE` | Inicio del bloque de bancos (10 registros por banco) |

### Bloque por banco (dirección = 30 + 10 × índice local + desplazamiento)

| Desp. | Campo |
|---|---|
| 0 | Número global de banco |
| 1 | Estado: 0 INICIANDO, 1 RESGUARDADO, 2 DESPLEGANDO, 3 CAPTANDO, 4 RESGUARDANDO, 5 FALLA, 6 LOCAL, 7 PAUSA |
| 2 | Fallas: 1 tiempo despliegue, 2 tiempo resguardo, 4 finales incoherentes, 8 posición perdida |
| 3 | Finales: bit0 resguardado, bit1 desplegado |
| 4–5 | Cuenta del balancín (u32) |
| 6–7 | Maniobras (u32) |
| 8 | Segundos en el estado |
| 9 | Salidas: bit0 marcha, bit1 sentido desplegar |

## Registros de retención (funciones 03, 06 y 16)

| Dir. | Nombre | Descripción |
|---|---|---|
| 0 | `HR_LATIDO` | Contador del registrador (diagnóstico) |
| 1 | `HR_ORDEN_SEQ` | Incrementar para emitir una orden |
| 2 | `HR_ORDEN_BANCO` | 1–4 (0 = todos) |
| 3 | `HR_ORDEN_CODIGO` | 1 HABILITAR, 2 RESGUARDAR, 3 RECONOCER_FALLA |
| 4 | `HR_BATERIA_MV` | Tensión de batería (mV) |
| 5 | `HR_BATERIA_SEQ` | Incrementar con cada dato |
| 10 | `HR_PARAM_RAFAGA` | Ráfaga de resguardo, km/h ×10 |
| 11 | `HR_PARAM_MEDIO` | Media de resguardo, km/h ×10 |
| 12 | `HR_PARAM_REHAB` | Media de rehabilitación, km/h ×10 |
| 13 | `HR_PARAM_CALMA_MIN` | Calma mínima, minutos |
| 14 | `HR_PARAM_SEQ` | Incrementar para aplicar los parámetros |
| 30–34 | `HR_PAR_*` | Bloque que escribe el PLC principal en el secundario: ráfaga, media, dirección, validez, secuencia |

## Motivos (IR 9)

| Bit | Motivo |
|---|---|
| 1 | RAFAGA |
| 2 | VIENTO_MEDIO |
| 4 | VIENTO_SIN_DATO |
| 8 | CALMA_INSUFICIENTE |
| 16 | BATERIA_BAJA |
| 32 | ORDEN_RESGUARDO |
| 64 | SIN_PERMISO |
| 128 | SOBRE_REHABILITACION |
