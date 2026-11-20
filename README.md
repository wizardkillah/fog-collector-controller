# Fog Collector Controller

**Control and logging for motorized fog-collector meshes: an Arduino Opta PLC that keeps the mesh safe from wind on its own, and a Raspberry Pi logger with a token-protected API, Modbus TCP and SQLite.**

> 🇪🇸 Reconstrucción que hice de un prototipo anterior, tras auditarlo. El sistema capta agua de la camanchaca (niebla costera) con mallas de 36 y 72 m². El firmware tiene 110 comprobaciones del núcleo con sanitizers y el registrador tiene 24 pruebas, que corren en GitHub Actions. Aún no se ha probado en campo: ver *Pendiente antes de campo*.

## Código base 1.0

Código de control y registro para los sistemas **Niebla de 36 y 72 m²**.

## Arquitectura en dos niveles

| Nivel | Equipo | Responsabilidad | Si falla… |
|---|---|---|---|
| 1. Control de campo | Arduino Opta (PLC industrial, 12–24 VDC) | Viento, lógica de resguardo, motores, finales de carrera, conteo de balancines | El mecanismo queda detenido. Los finales de carrera por hardware y la posición mecánica segura lo protegen |
| 2. Registro local | Raspberry Pi (registrador) | Base de datos, eventos, exportación CSV, panel local y órdenes | **El PLC sigue protegiendo solo.** Lo único que se pierde es el registro durante la caída |
| 3. Servicios opcionales | Nube / IA | Telemetría, alertas remotas, informes y ajuste de parámetros dentro de la envolvente | No afecta al control |

La inteligencia artificial nunca actúa sobre un relé. Como mucho puede proponer parámetros, y el PLC los recorta a la envolvente de ingeniería (`Envolvente` en `niebla_core.h`).

## Estructura

```
firmware/
  opta_niebla/
    opta_niebla.ino      sketch del PLC (entradas, salidas, RS485, Modbus TCP, watchdog)
    niebla_core.h/.cpp   lógica de seguridad portable: Viento, Sitio, Banco, Contador
    config_sitio.h       pines, IP, direcciones RS485 y parámetros [ING]
    mapa_registros.h     mapa Modbus (debe coincidir con registrador/niebla/mapa.py)
  test/
    test_core.cpp        110 comprobaciones del núcleo (make test)
    mock/                stubs para verificar la sintaxis del sketch (make sintaxis)
registrador/
  niebla/         servicio, base SQLite, eventos, API con token y exportación
  tests/                 24 pruebas (pytest): integración Modbus TCP real y coherencia con el firmware
  config.example.toml
  systemd/niebla.service   usuario sin privilegios y sistema de archivos protegido
docs/
  arquitectura.md  mapa_registros.md  pruebas_banco.md
```

## Pruebas

```bash
make -C firmware/test test        # núcleo del PLC con AddressSanitizer y UBSan
make -C firmware/test sintaxis    # sintaxis del sketch, roles principal y secundario
cd registrador && python -m pytest
```

Estado a 2026-09-28: el núcleo pasa **110/110** comprobaciones y el registrador **24/24** pruebas.

> **Pendiente antes de campo:** compilar el sketch en el Arduino IDE con el core *Arduino Mbed OS Opta Boards* y las bibliotecas `ArduinoRS485` y `ArduinoModbus`. En este entorno el acceso a los servidores de Arduino está bloqueado, así que el sketch se verificó solo contra stubs. También hay que confirmar los registros Modbus de cada sensor en su hoja de datos (`config_sitio.h`) y ejecutar el protocolo de `docs/pruebas_banco.md`.

## Puesta en marcha del registrador (Raspberry Pi OS 64 bits)

```bash
sudo useradd --system --home /var/lib/niebla --create-home niebla
sudo python3 -m venv /opt/niebla/venv
sudo /opt/niebla/venv/bin/pip install ./registrador
sudo install -d -m 750 /etc/niebla
sudo cp registrador/config.example.toml /etc/niebla/config.toml
echo "NIEBLA_TOKEN=$(openssl rand -hex 24)" | sudo tee /etc/niebla/token.env
sudo chmod 600 /etc/niebla/token.env
sudo cp registrador/systemd/niebla.service /etc/systemd/system/
sudo systemctl enable --now niebla
```

## Reglas del proyecto (lecciones del prototipo)

1. Ningún dato simulado entra en la base de campo: el modo `simulacion` usa otra base y cada fila lleva `simulado`.
2. Sin dato de viento válido no se despliega; si falta el dato, se resguarda.
3. Nada corre como root. No hay CORS abierto, ni `subprocess`, ni `eval` con datos externos.
4. Los secretos van en variables de entorno (`token.env`, modo 600). Nunca van en git ni en unidades systemd.
5. Los litros se informan solo con el balancín calibrado. Sin calibración se informan pulsos.
6. El despliegue se hace desde el repositorio con etiquetas de versión, nunca copiando y pegando desde un chat.
