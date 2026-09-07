# ioc/ : the EPICS layer

Caproto **soft IOCs**, one per device class. Each subscribes to the MQTT field bus and serves
**Channel Access** PVs named per `../docs/NAMING.md`. Pure-Python: no EPICS base build.

| File          | Device class          | PVs                                  | Status |
|---------------|-----------------------|--------------------------------------|--------|
| `puck_ioc.py` | environmental pucks   | `HES:<AREA>:BME<n>:{TEMP,RH,PRES}`   | ✅ v0 |
| `light_ioc.py`| lamps / globes        | `…:{PWR,BRT}` (+ RBV)                | TODO |
| `motor_ioc.py`| curtain / blind tilt  | `…:{VAL,RBV,MOVN,HOMED}`             | TODO |

## Run
```bash
pip install -r requirements.txt
python puck_ioc.py --list-pvs                 # sanity-check the namespace
HESTIA_MQTT=<broker-host> python puck_ioc.py  # serve
```

## Verify from another shell (EPICS clients, or caproto's)
```bash
caproto-get HES:LR:BME1:TEMP        # or:  caget  (if EPICS base installed)
caproto-monitor HES:LR:BME1:TEMP
```

## Design notes
- **One IOC per device class**, mirroring Helios's "one thin server per domain" rule.
- Actuator IOCs will expose the **VAL (setpoint) / RBV (readback)** pair and publish the
  setpoint back to MQTT for the ESP32 to act on, but don't trust a command without the readback.
- v0 uses a **static** puck list (`PUCKS` dict). A later version can create PVs on MQTT
  discovery. Actuator writes will map PV `caput` → MQTT publish → ESPHome.
- Authorization is **not** done here, it's Channel Access access-security (`.acf`,
  see `deploy/`). Keep IOCs about devices, not permissions.
