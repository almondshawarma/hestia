# Hestia

A project between roommates, firstly forest of home-built IoT lights, sensors, blinds,
switches, etc., spoken for by **EPICS**, the control system that runs particle accelerators,
light sources, and ITER! Every device becomes a **process variable**. This is part of a
[homelab project](https://github.com/almondshawarma/homelab).

## Motivation

Two goals at once! First, control a real apartment (mine and my roommates') with something
better than vendor apps that each phone home to a different cloud, and secondly, the
reason for EPICS specifically, to **learn part of the actual control-system stack used in nuclear,
accelerator, and fusion facilities** by operating one first at apartment scale: PV naming, the
motor record, Channel Access, Phoebus operator screens, the archiver, alarms, sequencing.

## What's here

- `firmware/` : ESPHome configs, one dir per node type. Field devices (ESP32) speak MQTT.
- `ioc/` : caproto **soft IOCs**, the EPICS layer. One per device class and each bridges MQTT
  telemetry into Channel Access PVs.
- `bridge/` : `ca2influx` , camonitor PVs into an InfluxDB `hestia` bucket for Grafana.
- `cad/` : 3D-printable parts (parametric OpenSCAD), e.g. the non-intrusive toggle-switch flipper.
- `hardware/` : KiCad, the puck-carrier PCB and driver boards.
- `calibration/` : per-device calibration recipes + stored coefficients.
- `deploy/` : docker-compose for the MQTT broker + IOCs on the Obelisk.

## Architecture (one line per layer)

**Field** (ESP32 / ESPHome) → **field bus** (MQTT) → **control** (caproto IOCs → Channel
Access PVs) → **services** (ca2influx → InfluxDB/Grafana, alarms → Telegram) →
**interface** (Phoebus OPI, Grafana, and a thin `hestia` MCP domain so Helios AI and Claude
can query/command the flat). See `docs/ARCHITECTURE.md` (once written!).

An ESP32 **cannot** run an EPICS IOC, as it's the *device*. The IOCs run centrally (Docker on
the Obelisk). Because Channel Access is location-transparent, an IOC can later move to a
per-room Pi with **zero client changes**.

## Status / Next steps

- **Now:** one environmental puck (ESP32 + BME280) → MQTT → `ioc/puck_ioc.py` →
  `camonitor HES:LR:BME1:TEMP`, meant to test the whole chain end-to-end.
- **Next:** `ca2influx` → Grafana, a humidifier closed loop (RH → smart plug), globe-light
  PWM dimming, the toggle-switch flippers, curtain + blind-tilt motion axes.
- **Later:** Phoebus apartment OPI, access-security (`.acf`) per-room scoping, the `hestia`
  MCP domain, Hyperion consumes apartment anomalies.

## See also

- [homelab](https://github.com/almondshawarma/homelab) : the server side (InfluxDB / Grafana / MCP / Telegram / Hyperion).
- `car-daq`, `ionosphere-daq` : instruments (may be integrated here soon!), same sensor→feature→store pipeline.
- **EPICS** (epics-controls.org), **caproto** (pure-Python CA), **Phoebus/CS-Studio**,
  **ESPHome** (declarative ESP32 firmware).

## License

Software: **MIT** · Hardware: **CERN-OHL-S** · Docs: **CC-BY-SA** 
