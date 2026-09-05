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
import math
import os
import random
import time

from caproto.server import PVGroup, pvproperty, run

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


# NB: caproto uses the pvproperty attribute name as the PV suffix, and Channel Access
# is CASE-SENSITIVE. NAMING.md mandates uppercase suffixes, so pin `name=` explicitly,
# so don't not rely on the (lowercase) Python attribute name.
class Bme(PVGroup):
    """HES:<area>:BME<n>: — environment."""
    temp = pvproperty(value=0.0, name="TEMP", units="degC", precision=2, read_only=True)
    rh = pvproperty(value=0.0, name="RH", units="%", precision=1, read_only=True)
    pres = pvproperty(value=0.0, name="PRES", units="hPa", precision=1, read_only=True)


class Lux(PVGroup):
    """HES:<area>:LUX<n>: - illuminance."""
    lux = pvproperty(value=0.0, name="LUX", units="lx", precision=1, read_only=True)


class Mic(PVGroup):
    """HES:<area>:MIC<n>: - sound level (relative until calibrated → DBA)."""
    lvl = pvproperty(value=0.0, name="LVL", units="au", precision=0, read_only=True)


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


def _sim_value(name: str, t: float) -> float:
    """Plausible synthetic reading for a sensor, as a function of elapsed seconds."""
    if name == "temp":
        return round(21.0 + 1.5 * math.sin(t / 30) + random.uniform(-0.1, 0.1), 2)
    if name == "rh":
        return round(45.0 + 6.0 * math.sin(t / 45) + random.uniform(-0.5, 0.5), 1)
    if name == "pres":
        return round(1001.0 + 2.0 * math.sin(t / 120), 1)
    if name == "lux":
        return round(max(0.0, 300.0 + 250.0 * math.sin(t / 20)), 1)
    if name == "sound":
        return round(random.uniform(0.05, 0.9), 2)
    return 0.0


async def sim_loop(routes) -> None:
    """Drive the PVs with synthetic data, without MQTT or hardware, For local IOC/GUI testing."""
    print("[ioc] SIM mode: generating synthetic sensor data (no MQTT).", flush=True)
    t0 = time.monotonic()
    while True:
        t = time.monotonic() - t0
        for (_area, _puck, name), channel in routes.items():
            await channel.write(_sim_value(name, t))
        await asyncio.sleep(2)


def _startup_hook(loop_coro, routes):
    """Return an async startup hook that launches the given loop on the server's own loop."""
    async def hook(*_args):
        asyncio.ensure_future(loop_coro(routes))
    return hook


def main(sim: bool = False) -> None:
    routes, pvdb = build_pucks()
    # Default to loopback: caproto must advertise a real, stable IP (never 0.0.0.0), and a
    # single interface avoids the "found on multiple servers" monitor breakage. Override with
    # EPICS_CAS_INTF_ADDR_LIST for networked deployments.
    interfaces = os.environ.get("EPICS_CAS_INTF_ADDR_LIST", "").split() or ["127.0.0.1"]
    source = "SIM (synthetic)" if sim else f"MQTT {BROKER}:{MQTT_PORT}"
    print(f"[ioc] serving {len(pvdb)} PVs across {len(PUCKS)} area(s); "
          f"source={source}; CA interfaces={interfaces}.", flush=True)
    # caproto's blessed sync runner wires up the asyncio server AND the CA search responder.
    # The data loop (MQTT or sim) runs as a task on the same loop via the startup hook.
    loop_coro = sim_loop if sim else mqtt_loop
    run(pvdb, interfaces=interfaces, startup_hook=_startup_hook(loop_coro, routes))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list-pvs", action="store_true", help="print PV names and exit")
    ap.add_argument("--sim", action="store_true", help="serve synthetic data (no MQTT/hardware)")
    args = ap.parse_args()
    if args.list_pvs:
        print("\n".join(pv_table()))
    else:
        try:
            main(sim=args.sim)
        except KeyboardInterrupt:
            pass
