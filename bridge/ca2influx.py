#!/usr/bin/env python3
"""ca2influx, camonitor Hestia PVs into an InfluxDB `hestia` bucket for Grafana.

The EPICS control plane (Channel Access) is "canonical" and this bridge is morehistoric, so
Hestia rides an existing InfluxDB + Grafana stack, alongside the IOCs on the Obelisk.

early scaffold: subscribes to a fixed PV list and writes each update as a point tagged by area
and device. Point it at the PVs `ioc/puck_ioc.py --list-pvs` prints.

Env: HESTIA_INFLUX_URL, HESTIA_INFLUX_TOKEN, HESTIA_INFLUX_ORG (default helios),
     HESTIA_INFLUX_BUCKET (default hestia), EPICS_CA_ADDR_LIST (point at the IOC host)
"""
from __future__ import annotations

import os

from caproto.threading.client import Context

# --- config ------------------------------------------------------------------
INFLUX_URL = os.environ.get("HESTIA_INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_TOKEN = os.environ.get("HESTIA_INFLUX_TOKEN", "")
INFLUX_ORG = os.environ.get("HESTIA_INFLUX_ORG", "helios")
INFLUX_BUCKET = os.environ.get("HESTIA_INFLUX_BUCKET", "hestia")

# PVs to archive. TODO: generate from docs/NAMING.md or the IOCs' --list-pvs.
PVS = [
    "HES:LR:BME1:TEMP",
    "HES:LR:BME1:RH",
    "HES:LR:BME1:PRES",
    "HES:LR:LUX1:LUX",
    "HES:LR:MIC1:LVL",
    "HES:RMB:BME1:TEMP",
    "HES:RMB:BME1:RH",
    "HES:RMB:BME1:PRES",
    "HES:RMB:LUX1:LUX",
    "HES:RMB:MIC1:LVL",
]


def _parse(pv_name: str) -> tuple[str, str, str]:
    """HES:LR:BME1:TEMP -> (measurement, area, device)."""
    _fac, area, device, signal = pv_name.split(":")
    return signal.lower(), area, device


def main() -> None:
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS

    influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = influx.write_api(write_options=SYNCHRONOUS)

    ctx = Context()
    pvs = ctx.get_pvs(*PVS)

    def make_cb(pv_name: str):
        measurement, area, device = _parse(pv_name)

        def cb(sub, response):
            try:
                value = float(response.data[0])
                point = (
                    Point("hestia")
                    .tag("area", area)
                    .tag("device", device)
                    .field(measurement, value)
                )
                write_api.write(bucket=INFLUX_BUCKET, record=point)
                print(f"[ca2influx] {pv_name} = {value}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[ca2influx] callback error {pv_name}: {exc!r}", flush=True)

        return cb

    # caproto holds subscriptions AND monitor callbacks WEAKLY — anything we don't keep a
    # strong reference to is garbage-collected and silently stops delivering. Keep both.
    keepalive = []
    for pv in pvs:
        cb = make_cb(pv.name)
        sub = pv.subscribe()          # returns a Subscription; register via add_callback
        sub.add_callback(cb)
        keepalive.append((sub, cb))
    main._keepalive = keepalive  # extra strong ref, defensive

    print(f"[ca2influx] archiving {len(pvs)} PVs → {INFLUX_URL} bucket={INFLUX_BUCKET}")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
