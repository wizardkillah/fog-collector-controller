# Protocolo de pruebas de banco y aceptación

Cada prueba se registra con fecha, responsable, resultado (Aprobada/Rechazada) y evidencia (foto, CSV o registro de eventos).

## A. Pruebas de fábrica (FAT, en taller y antes del traslado)

| N.º | Prueba | Procedimiento | Criterio de aceptación |
|---|---|---|---|
| A1 | Arranque seguro | Energizar con el banco a media carrera | Resguarda sin intervención y registra el evento ESTADO |
| A2 | Ciclo completo | Viento simulado bajo el umbral durante la calma mínima reducida a 10 min | Despliega, llega al final de carrera y queda en CAPTANDO |
| A3 | Ráfaga | Inyectar una ráfaga ≥ R | Pasa a RESGUARDANDO en ≤ 1 s. Se mide el tiempo total de resguardo |
| A4 | Sensor de viento desconectado | Desconectar el RS485 del anemómetro | Resguarda en ≤ 11 s y registra un evento crítico SENSOR_VIENTO |
| A5 | Atasco | Bloquear el mecanismo durante el despliegue | Tras el tiempo máximo registra la falla TIEMPO_DESPLIEGUE y vuelve a resguardado. No reintenta sin reconocimiento |
| A6 | Cable de final cortado | Abrir el cable del final de desplegado estando resguardado | FALLA FINALES_INCOHERENTES con motor apagado |
| A7 | Parada de emergencia | Pulsarla durante una maniobra | El motor se detiene por hardware y el PLC pasa a LOCAL |
| A8 | Caída del registrador | Apagar la Raspberry Pi con un banco desplegado y aplicar una ráfaga | El PLC resguarda igual |
| A9 | Caída del enlace (72 m²) | Desconectar la Ethernet del PLC secundario | Los bancos 3 y 4 resguardan en ≤ 11 s |
| A10 | Watchdog | Forzar el bloqueo del lazo (firmware de prueba) | El PLC se reinicia en ≤ 8 s y arranca en estado seguro |
| A11 | Energía | Batería bajo la reserva (fuente regulable) | Resguarda y no despliega hasta superar la reserva en 0,4 V |
| A12 | Órdenes | RESGUARDAR, HABILITAR y RECONOCER_FALLA desde la API | Cada orden queda confirmada por eco en la tabla `ordenes` |
| A13 | Seguridad de la API | Pedir sin token, con token erróneo y con una orden inválida | Responde 401, 401 y 400 respectivamente |

## B. Calibración del balancín de captación (por banco)

1. Nivelar el balancín y fijarlo al canalón.
2. Verter 2,000 L con una probeta clase B a un caudal de 0,5 a 1 L/min (bajo caudal, representativo de niebla).
3. Registrar los pulsos, repetir 3 veces y calcular `ml_por_pulso = 2000 / pulsos_promedio`.
4. Aceptar si la dispersión entre repeticiones es ≤ 3 %. Anotar el valor en `config.toml`.
5. Verificar con un volumen distinto (1,000 L): el error debe ser ≤ 5 %.
6. Recalibrar cada seis meses o después de cualquier intervención.

## C. Pruebas en sitio (SAT, aceptación funcional)

| N.º | Prueba | Criterio |
|---|---|---|
| C1 | Prueba hidráulica de conducción | Sin pérdidas visibles con el canalón lleno durante 30 min |
| C2 | Sensores | Viento, dirección, lluvia, nivel y T/HR plausibles y con marca de tiempo |
| C3 | Protección | A3, A4 y A7 repetidas en sitio |
| C4 | Exportación | CSV con metadatos, unidades y modo "campo" |
| C5 | Capacitación | Acta firmada: operación manual, rescate, limpieza y lectura de eventos |

La aceptación **no** incluye un volumen mínimo de agua. El rendimiento se establece con la campaña de medición contratada aparte.
