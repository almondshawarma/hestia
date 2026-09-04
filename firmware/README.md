# firmware/ : field devices (ESP32 / ESPHome)

Declarative ESP32 firmware, with one directory per node type. Devices speak **MQTT** (the Hestia
field bus), but they do **not** run EPICS, the IOCs in `../ioc/` turn their MQTT topics into
Channel Access PVs.

| Dir              | Node                                   | Status |
|------------------|----------------------------------------|--------|
| `puck/`          | ESP32 + BME280 environment puck        | ✅ Rung 0 |
| `switch-flipper/`| ESP32-C3 + servos over a toggle plate  | TODO (needs `cad/switch-flipper`) |
| `globe/`         | ESP32 + MOSFET PWM on a LV LED string  | TODO |
| `curtain-blind/` | ESP32 + TMC2209 stepper axes           | TODO |
| `common/`        | shared ESPHome packages                | — |

## Why ESPHome
YAML instead of C++ (sorry jait). OTA updates (flash once over USB, then wirelessly). This means same firmware
layer across every ESP32 variant we use and nothing learned is throwaway!

## First flash
```bash
pipx install esphome
cp firmware/puck/secrets.example.yaml firmware/puck/secrets.yaml   # then edit
esphome run firmware/puck/puck.yaml                                 # USB first time, OTA after
```

`secrets.yaml` and ESPHome's `.esphome/` build cache are gitignored.
