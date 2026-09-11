#!/usr/bin/env python3
"""Hestia puck IOC : bridges MQTT puck telemetry to EPICS Channel Access.

This is the EPICS layer for environmental pucks (one soft IOC per device class).

    field:    ESP32/ESPHome  →  MQTT  hestia/<area>/puck<n>/sensor/<name>/state
    control:  this IOC        →  Channel Access  HES:<AREA>:<DEVICE><n>:<SIGNAL>

A puck is a multi-sensor node, so each reading fans out to the right *device* (EPICS names by
function, not by board, one ESP32 hosts several logical devices):
    temp/rh/pres -> BME<n>:{TEMP,RH,PRES}
    lux          -> LUX<n>:LUX
    sound        -> MIC<n>:LVL     (relative loudness until calibrated to dBA)

The bridge is bidirectional for pucks with a display: writing LCD<n>:MSG (a string PV) is
republished to MQTT hestia/<area>/puck<n>/msg for the puck to flash on-screen, and the puck's
echo on .../msg/state feeds LCD<n>:STAT (readback). See docs/NAMING.md.

An ESP32 can't run an IOC, so the IOC runs here (Docker on the Obelisk) and subscribes to the
broker. Channel Access is location-transparent, so this can later move to a per-room Pi with
no client changes.

Usage
-----
    pip install -r requirements.txt
    python puck_ioc.py --list-pvs          # print the PV table and exit
    HESTIA_MQTT=<broker-host> python puck_ioc.py
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import random
import re
import threading
import time

from caproto import ChannelType
from caproto.server import PVGroup, pvproperty, run

# --- configuration -----------------------------------------------------------
PREFIX = "HES"
BROKER = os.environ.get("HESTIA_MQTT", "127.0.0.1")
MQTT_PORT = int(os.environ.get("HESTIA_MQTT_PORT", "1883"))

# area code -> number of pucks in that area (see docs/NAMING.md)
PUCKS: dict[str, int] = {
    "LR": 1,       # kept for local --sim / GUI dev
    "RMB": 1,      # bedroom B is first real puck
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
    """HES:<area>:BME<n>: is environment."""
    temp = pvproperty(value=0.0, name="TEMP", units="degC", precision=2, read_only=True)
    rh = pvproperty(value=0.0, name="RH", units="%", precision=1, read_only=True)
    pres = pvproperty(value=0.0, name="PRES", units="hPa", precision=1, read_only=True)


class Lux(PVGroup):
    """HES:<area>:LUX<n>: - illuminance."""
    lux = pvproperty(value=0.0, name="LUX", units="lx", precision=1, read_only=True)


class Mic(PVGroup):
    """HES:<area>:MIC<n>: - sound level (relative until calibrated → DBA)."""
    lvl = pvproperty(value=0.0, name="LVL", units="au", precision=0, read_only=True)


class _MqttOut:
    """Shared handle to the live aiomqtt client, so outbound PVs (LCD:MSG) can publish.

    mqtt_loop() owns the connection and sets/clears `.client` as it connects/drops; a putter
    just calls `await _MqttOut.publish(...)` and gets a clear error when the broker is down.
    """
    client = None  # set by mqtt_loop() while connected, else None

    @classmethod
    async def publish(cls, topic: str, payload: str) -> None:
        c = cls.client
        if c is None:
            raise RuntimeError("MQTT not connected")
        await c.publish(topic, payload)


def _as_text(value) -> str:
    """Normalize a caproto channel value (str / [str] / bytes / [int char codes]) to plain text."""
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        if all(isinstance(c, int) for c in value):      # char-array of code points
            return bytes(value).decode("latin-1", "ignore").rstrip("\x00")
        value = value[0]                                 # e.g. ["hi there"] from a STRING scalar
    if isinstance(value, (bytes, bytearray)):
        return value.decode("latin-1", "ignore").rstrip("\x00")
    return str(value)


class Lcd(PVGroup):
    """HES:<area>:LCD<n>: - character display. Write MSG to flash text on-screen; STAT reads
    back what the puck reports it is actually showing (the :VAL/:RBV convention, string form).

    MSG is the *command*: its putter republishes the text to the MQTT topic the puck's ESPHome
    firmware subscribes to (hestia/<AREA>/puck<n>/msg). An ESP32 can't speak Channel Access, so
    MQTT stays the last hop to the device but the operator-facing surface is a PV.
    """
    # ChannelType.STRING -> a real EPICS DBR_STRING (40-char cap, fine for the 32-char display),
    # so caget/caput and the putter see clean text, not a char-code array. (dtype=str and
    # report_as_string both leave it a char waveform that caget renders as [104 101 ...].)
    msg = pvproperty(value="", name="MSG", dtype=ChannelType.STRING,
                     doc="flash text on the LCD for ~10s (empty clears)")
    stat = pvproperty(value="", name="STAT", dtype=ChannelType.STRING, read_only=True,
                      doc="text the puck reports it is showing (readback; IDLE when cleared)")

    # set per-instance in build_pucks(): the exact topic the firmware's on_message subscribes to.
    msg_topic: str = ""

    @msg.putter
    async def msg(self, instance, value):
        if not self.msg_topic:
            return value
        text = _as_text(value)
        try:
            await _MqttOut.publish(self.msg_topic, text)
            print(f"[lcd] {self.msg_topic} <- {text!r}", flush=True)
        except Exception as exc:  # noqa: BLE001 (a caput shouldn't crash the IOC if the broker is down)
            print(f"[lcd] publish to {self.msg_topic} failed ({exc!r}); is MQTT up?", flush=True)
        return value


DEVICE_CLASSES = {"BME": Bme, "LUX": Lux, "MIC": Mic, "LCD": Lcd}


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
            # LCD: outbound command topic + inbound readback route. The publish topic's area
            # segment must match the firmware's topic_prefix EXACTLY (MQTT is case-sensitive)
            # firmware uses the uppercase area code, so use `area` here, not `area.lower()`.
            lcd = groups.get("LCD")
            if lcd is not None:
                lcd.msg_topic = f"hestia/{area}/puck{n}/msg"
                routes[(area.lower(), f"puck{n}", "msg")] = lcd.stat  # hestia/<area>/puck<n>/msg/state echo
    return routes, pvdb


def pv_table() -> list[str]:
    names = []
    for area, count in PUCKS.items():
        for n in range(1, count + 1):
            for name, (dev, attr) in SENSOR_MAP.items():
                names.append(f"{PREFIX}:{area}:{dev}{n}:{attr.upper()}")
            names.append(f"{PREFIX}:{area}:LCD{n}:MSG")   # write: flash text on the display
            names.append(f"{PREFIX}:{area}:LCD{n}:STAT")  # read:  what the puck reports it shows
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
                _MqttOut.client = client  # let LCD:MSG putters publish while we're connected
                await client.subscribe("hestia/#")
                print(f"[mqtt] connected {BROKER}:{MQTT_PORT}, subscribed hestia/#")
                async for msg in client.messages:
                    parts = str(msg.topic).split("/")
                    # LCD readback echo: hestia/<area>/puck<n>/msg/state -> LCD:STAT (free-form string)
                    if len(parts) == 5 and parts[3] == "msg" and parts[4] == "state":
                        channel = routes.get((parts[1].lower(), parts[2].lower(), "msg"))
                        if channel is not None:
                            await channel.write(msg.payload.decode(errors="ignore"))
                        continue
                    # sensor telemetry: hestia/<area>/puck<n>/sensor/<name>/state -> float PV
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
            _MqttOut.client = None  # stop LCD putters from publishing to a dead client
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
            if name not in SENSOR_MAP:
                continue  # skip non-sensor routes (e.g. the LCD:STAT string readback)
            await channel.write(_sim_value(name, t))
        await asyncio.sleep(2)


# --- serial bridge: a USB-attached ESP32 (bench firmware) → EPICS, no network needed ---
# This is the "IOC per device" pattern where the device speaks serial (cf. EPICS StreamDevice).
_VERBOSE_RE = re.compile(r"'(?P<name>\w+)'\s*>>\s*(?P<val>-?\d+(?:\.\d+)?)")


def _parse_serial_line(line: str) -> list[tuple[str, float]]:
    """Extract (esphome_name, value) pairs from an ESPHome serial line.

    Two accepted formats:
      structured (preferred): "PUCK temp=21.00 rh=45.5 pres=1001.2 lux=300.0 sound=0.12"
      ESPHome VERBOSE log:     "[V][sensor:125]: 'temp' >> 21.0 degC"
    """
    out: list[tuple[str, float]] = []
    if "PUCK " in line:
        for tok in line.split("PUCK ", 1)[1].split():
            key, sep, val = tok.partition("=")
            if sep:
                try:
                    fv = float(val)
                except ValueError:
                    continue
                if fv == fv:  # skip NaN (sensor not ready yet)
                    out.append((key, fv))
        if out:
            return out
    m = _VERBOSE_RE.search(line)
    if m:
        out.append((m.group("name"), float(m.group("val"))))
    return out


def _serial_reader(port: str, routes: dict, loop: asyncio.AbstractEventLoop) -> None:
    """Blocking serial read loop (runs in a thread); marshals PV writes onto the CA loop."""
    try:
        import serial  # pyserial
    except ImportError:
        print("[serial] pyserial not installed → run: pip install pyserial", flush=True)
        return
    area = next(iter(PUCKS)).lower()  # map the serial device to the first configured puck
    while True:  # survive unplug/replug
        try:
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = 115200
            ser.timeout = 1
            ser.dtr = False  # keep GPIO0 high so the reset-on-open boots the app, not the bootloader
            ser.rts = False
            ser.open()
            print(f"[serial] reading {port} @115200 → HES:{area.upper()}:* PVs", flush=True)
            while True:
                raw = ser.readline()
                if not raw:
                    continue
                for name, val in _parse_serial_line(raw.decode(errors="ignore").strip()):
                    channel = routes.get((area, "puck1", name))
                    if channel is not None:
                        asyncio.run_coroutine_threadsafe(channel.write(val), loop)
        except Exception as exc:  # noqa: BLE001
            print(f"[serial] {port} error ({exc!r}); retrying in 3s", flush=True)
            time.sleep(3)


def _serial_startup_hook(port: str, routes: dict):
    async def hook(*_args):
        loop = asyncio.get_event_loop()
        threading.Thread(target=_serial_reader, args=(port, routes, loop), daemon=True).start()
    return hook


def _startup_hook(loop_coro, routes):
    """Return an async startup hook that launches the given loop on the server's own loop."""
    async def hook(*_args):
        asyncio.ensure_future(loop_coro(routes))
    return hook


def main(sim: bool = False, serial_port: str | None = None) -> None:
    routes, pvdb = build_pucks()
    # Default to loopback: caproto must advertise a real, stable IP (never 0.0.0.0), and a
    # single interface avoids the "found on multiple servers" monitor breakage. Override with
    # EPICS_CAS_INTF_ADDR_LIST for networked deployments.
    interfaces = os.environ.get("EPICS_CAS_INTF_ADDR_LIST", "").split() or ["127.0.0.1"]
    if serial_port:
        source, hook = f"SERIAL {serial_port}", _serial_startup_hook(serial_port, routes)
    elif sim:
        source, hook = "SIM (synthetic)", _startup_hook(sim_loop, routes)
    else:
        source, hook = f"MQTT {BROKER}:{MQTT_PORT}", _startup_hook(mqtt_loop, routes)
    print(f"[ioc] serving {len(pvdb)} PVs across {len(PUCKS)} area(s); "
          f"source={source}; CA interfaces={interfaces}.", flush=True)
    # caproto's blessed sync runner wires up the asyncio server AND the CA search responder.
    # The data loop (MQTT / sim / serial) is started as a task/thread by the startup hook.
    run(pvdb, interfaces=interfaces, startup_hook=hook)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list-pvs", action="store_true", help="print PV names and exit")
    ap.add_argument("--sim", action="store_true", help="serve synthetic data (no MQTT/hardware)")
    ap.add_argument("--serial", metavar="PORT", help="read a USB-attached puck (e.g. COM5) instead of MQTT")
    args = ap.parse_args()
    if args.list_pvs:
        print("\n".join(pv_table()))
    else:
        try:
            main(sim=args.sim, serial_port=args.serial)
        except KeyboardInterrupt:
            pass
