#!/usr/bin/env python3
"""Hestia puck IOC : bridges MQTT puck telemetry to EPICS Channel Access.

This is the EPICS layer for environmental pucks (one soft IOC per device class).

    field:    ESP32/ESPHome  →  MQTT  hestia/<area>/puck<n>/sensor/<name>/state
    control:  this IOC        →  Channel Access  HES:<AREA>:<DEVICE><n>:<SIGNAL>

A puck is a multi-sensor node, so each reading fans out to the right *device*:
    temp/rh/pres -> BME<n>:{TEMP,RH,PRES}
    lux          -> LUX<n>:LUX
    sound        -> MIC<n>:LVL     (relative loudness until calibrated to dBA)

An ESP32 can't run an IOC, so the IOC runs here (Docker on the Obelisk) and subscribes to the
broker. Channel Access is location-transparent, so this can later move to a per-room Pi with
no client changes.

Usage
-----
    pip install -r requirements.txt
    python puck_ioc.py --list-pvs          # print the PV table and exit
    HESTIA_MQTT=100.64.10.118 python puck_ioc.py
"""
from __future__ import annotations

import argparse
import asyncio
import os

from caproto.asyncio.server import Context
from caproto.server import PVGroup, pvproperty

# --- configuration -----------------------------------------------------------
PREFIX = "HES"
BROKER = os.environ.get("HESTIA_MQTT", "127.0.0.1")
MQTT_PORT = int(os.environ.get("HESTIA_MQTT_PORT", "1883"))

# area code -> number of pucks in that area (see docs/NAMING.md)
PUCKS: dict[str, int] = {
    "LR": 1,
    # "KI": 1,
    # "RMA": 1,
}

# ESPHome sensor <name>  ->  (device code, PVGroup attr). The attr's units/precision
# are defined on the device PVGroups below.
SENSOR_MAP = {
    "temp": ("BME", "temp"),
    "rh": ("BME", "rh"),
    "pres": ("BME", "pres"),
    "lux": ("LUX", "lux"),
    "sound": ("MIC", "lvl"),
}


class Bme(PVGroup):
    """HES:<area>:BME<n>: — environment."""
    temp = pvproperty(value=0.0, units="degC", precision=2, read_only=True)
    rh = pvproperty(value=0.0, units="%", precision=1, read_only=True)
    pres = pvproperty(value=0.0, units="hPa", precision=1, read_only=True)


class Lux(PVGroup):
    """HES:<area>:LUX<n>: — illuminance."""
    lux = pvproperty(value=0.0, units="lx", precision=1, read_only=True)


class Mic(PVGroup):
    """HES:<area>:MIC<n>: — sound level (relative until calibrated → DBA)."""
    lvl = pvproperty(value=0.0, units="au", precision=0, read_only=True)


DEVICE_CLASSES = {"BME": Bme, "LUX": Lux, "MIC": Mic}


def build_pucks() -> tuple[dict, dict]:
    """Instantiate device PVGroups per puck.

    Returns (routes, pvdb) where routes maps (area_lc, "puck<n>", esphome_name) -> ChannelData.
    """
    routes: dict = {}
    pvdb: dict = {}
    for area, count in PUCKS.items():
        for n in range(1, count + 1):
            # one PVGroup per device on this puck
            groups = {
                dev: cls(prefix=f"{PREFIX}:{area}:{dev}{n}:")
                for dev, cls in DEVICE_CLASSES.items()
            }
            for group in groups.values():
                pvdb.update(group.pvdb)
            for name, (dev, attr) in SENSOR_MAP.items():
                routes[(area.lower(), f"puck{n}", name)] = getattr(groups[dev], attr)
    return routes, pvdb


def pv_table() -> list[str]:
    names = []
    for area, count in PUCKS.items():
        for n in range(1, count + 1):
            for name, (dev, attr) in SENSOR_MAP.items():
                names.append(f"{PREFIX}:{area}:{dev}{n}:{attr.upper()}")
    return names


async def mqtt_loop(routes: dict) -> None:
    """Subscribe to hestia/# and push each reading into the matching PV."""
    try:
        import aiomqtt
    except ImportError:
        raise SystemExit(
            "aiomqtt not installed. `pip install -r requirements.txt`. "
            "(The IOC still serves PVs at defaults without it.)"
        )

    while True:  # reconnect forever
        try:
            async with aiomqtt.Client(hostname=BROKER, port=MQTT_PORT) as client:
                await client.subscribe("hestia/#")
                print(f"[mqtt] connected {BROKER}:{MQTT_PORT}, subscribed hestia/#")
                async for msg in client.messages:
                    # topic: hestia/<area>/puck<n>/sensor/<name>/state
                    parts = str(msg.topic).split("/")
                    if len(parts) != 6 or parts[3] != "sensor" or parts[5] != "state":
                        continue
                    key = (parts[1].lower(), parts[2].lower(), parts[4])
                    channel = routes.get(key)
                    if channel is None:
                        continue
                    try:
                        value = float(msg.payload.decode())
                    except ValueError:
                        continue
                    await channel.write(value)
        except Exception as exc:  # noqa: BLE001 (keep the IOC alive across broker restarts)
            print(f"[mqtt] disconnected ({exc!r}); retrying in 5s")
            await asyncio.sleep(5)


async def main() -> None:
    routes, pvdb = build_pucks()
    ctx = Context(pvdb)
    print(f"[ioc] serving {len(pvdb)} PVs across {len(PUCKS)} area(s). Broker {BROKER}:{MQTT_PORT}.")
    await asyncio.gather(ctx.run(), mqtt_loop(routes))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list-pvs", action="store_true", help="print PV names and exit")
    args = ap.parse_args()
    if args.list_pvs:
        print("\n".join(pv_table()))
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
