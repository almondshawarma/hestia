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
            (value,) = response.data
            point = (
                Point("hestia")
                .tag("area", area)
                .tag("device", device)
                .field(measurement, float(value))
            )
            write_api.write(bucket=INFLUX_BUCKET, record=point)

        return cb

    for pv in pvs:
        pv.subscribe(make_cb(pv.name))

    print(f"[ca2influx] archiving {len(pvs)} PVs → {INFLUX_URL} bucket={INFLUX_BUCKET}")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
