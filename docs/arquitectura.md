# Arquitectura de control Niebla

## Lógica de resguardo (PLC)

```
                 ráfaga 3 s ≥ R   o   media 10 min ≥ M   o   sin dato de viento   o   batería < reserva
CAPTANDO ──────────────────────────────────────────────────────────────────────────────────────────► RESGUARDANDO ──► RESGUARDADO
    ▲                                                                                                                      │
    └──────────── DESPLEGANDO ◄──── sin riesgo durante la calma mínima  Y  media 10 min ≤ H  Y  banco no retenido ─────────┘
```

| Parámetro | Valor inicial | Envolvente | Origen |
|---|---|---|---|
| R: ráfaga de resguardo | 45 km/h | 20–60 km/h | **[ING]** Cálculo estructural del banco y del mecanismo según NCh432 |
| M: media de resguardo | 35 km/h | 15–50 km/h, ≤ R | [ING] |
| H: media para rehabilitar | 25 km/h | ≤ M − 5 km/h | Histéresis |
| Calma mínima | 30 min | 10–120 min | Evita ciclos de apertura y cierre en días de viento racheado |
| Vigencia del dato de viento | 10 s | fija | Un dato viejo cuenta como ausencia de dato |
| Tiempo máximo de maniobra | 90 s | fijo por sitio | [ING] Carrera medida en banco + 30 % |
| Tiempo mínimo entre maniobras | 60 s | fijo | Protege el motor |
| Pausa antes de invertir el giro | 2 s | fija | Protege el reductor |
| Reserva de batería | 12,4 V | fija por sitio | Asegura energía para un resguardo |

Los valores iniciales son **provisorios**. Los reemplaza la ingeniería del sitio antes de la puesta en marcha.

## Seguridad por capas

1. **Mecánica:** posición resguardada estable sin energía, rescate manual y elementos fusibles para viento extremo.
2. **Eléctrica:** parada de emergencia que corta la potencia del motor, finales de carrera en serie con el sentido de giro (límite por hardware) e inversor con enclavamiento.
3. **PLC:** estados, tiempos máximos, finales NC (el corte de un cable se detecta como incoherencia), watchdog de 8 s y arranque hacia el estado seguro.
4. **Registrador:** registro, eventos y órdenes validadas. No es necesario para la seguridad.

## Configuraciones

| | 36 m² | 72 m² |
|---|---|---|
| Bancos de 18 m² | 2 | 4 |
| PLC | 1 Opta (principal) | 2 Opta (principal y secundario) |
| Bus RS485 de sensores | En el principal | En el principal. El secundario recibe el viento por Ethernet cada 2 s y resguarda si deja de recibirlo |
| Registrador | 1 Raspberry Pi | 1 Raspberry Pi |

## Entradas y salidas por PLC

| E/S | Opta | Uso |
|---|---|---|
| I1 / I2 | A0 / A1 | Finales de carrera NC del banco 1: resguardado y desplegado |
| I3 / I4 | A2 / A3 | Finales de carrera NC del banco 2: resguardado y desplegado |
| I5 / I6 | A4 / A5 | Balancín de captación de los bancos 1 y 2 (contacto reed) |
| I7 | A6 | Flotador de nivel alto (NC) |
| I8 | A7 | Permiso: selector REMOTO + parada de emergencia liberada |
| R1 / R2 | D0 / D1 | Banco 1: marcha y sentido |
| R3 / R4 | D2 / D3 | Banco 2: marcha y sentido |
| RS485 | A(+)/B(−) | Anemómetro y veleta (1), pluviómetro (2), nivel (3), T/HR (4). 9600 8N1 |
| Ethernet | RJ45 | Modbus TCP hacia el registrador y hacia el PLC secundario |
