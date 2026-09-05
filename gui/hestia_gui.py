#!/usr/bin/env python3
"""Hestia : a light live-PV monitor GUI (Tkinter + caproto, pure Python, zero extra deps).

Test the whole EPICS stack on your laptop, offline:
    pip install caproto
    python ioc/puck_ioc.py --sim      # terminal 1: serve synthetic PVs on localhost
    python gui/hestia_gui.py          # terminal 2: watch them update live

Channel Access is location-transparent, so this also works against the real IOC on the
Obelisk, just set EPICS_CA_ADDR_LIST to its reachable IP before launching.
"""
from __future__ import annotations

import os
import queue
import tkinter as tk
from tkinter import font as tkfont

# Look on localhost by default (matches `puck_ioc.py --sim`). Override via env for a remote IOC.
os.environ.setdefault("EPICS_CA_ADDR_LIST", "127.0.0.1")
os.environ.setdefault("EPICS_CA_AUTO_ADDR_LIST", "no")

from caproto.threading.client import Context  # noqa: E402  (env must be set first)

# (PV name, label, units, decimals)
PVS = [
    ("HES:LR:BME1:TEMP", "Temperature", "°C", 1),
    ("HES:LR:BME1:RH", "Humidity", "%", 1),
    ("HES:LR:BME1:PRES", "Pressure", "hPa", 1),
    ("HES:LR:LUX1:LUX", "Illuminance", "lx", 0),
    ("HES:LR:MIC1:LVL", "Sound", "rel", 2),
]

# control-room palette
BG = "#0b0f14"; CARD = "#121a24"; EDGE = "#22303f"
INK = "#e6ecf5"; MUTED = "#7c8ba0"; DIM = "#3d4c5e"; ACCENT = "#4da3ff"; OK = "#38c07f"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.tiles: dict = {}
        self.decimals = {pv: d for pv, _, _, d in PVS}

        root.title("Hestia — Control Room")
        root.configure(bg=BG)
        f_head = tkfont.Font(family="Consolas", size=12, weight="bold")
        f_lbl = tkfont.Font(family="Consolas", size=10)
        f_val = tkfont.Font(family="Consolas", size=30, weight="bold")
        f_unit = tkfont.Font(family="Consolas", size=12)
        f_pv = tkfont.Font(family="Consolas", size=8)

        tk.Label(root, text="HESTIA · LIVING ROOM PUCK", fg=ACCENT, bg=BG, font=f_head)\
            .grid(row=0, column=0, columnspan=len(PVS), sticky="w", padx=16, pady=(14, 8))

        for i, (pv, name, units, _dec) in enumerate(PVS):
            card = tk.Frame(root, bg=CARD, highlightthickness=1, highlightbackground=EDGE)
            card.grid(row=1, column=i, padx=8, pady=8, ipadx=8, ipady=10, sticky="nsew")
            dot = tk.Label(card, text="●", fg=MUTED, bg=CARD, font=f_lbl)
            dot.pack(anchor="w", padx=10)
            tk.Label(card, text=name, fg=MUTED, bg=CARD, font=f_lbl).pack(anchor="w", padx=10)
            val = tk.Label(card, text="—", fg=INK, bg=CARD, font=f_val)
            val.pack(anchor="w", padx=10)
            tk.Label(card, text=units, fg=MUTED, bg=CARD, font=f_unit).pack(anchor="w", padx=10)
            tk.Label(card, text=pv, fg=DIM, bg=CARD, font=f_pv).pack(anchor="w", padx=10, pady=(6, 0))
            self.tiles[pv] = (val, dot)

        self.status = tk.Label(root, text="connecting…", fg=MUTED, bg=BG, font=f_lbl)
        self.status.grid(row=2, column=0, columnspan=len(PVS), sticky="w", padx=16, pady=(2, 12))

        self._connect()
        self.root.after(150, self._drain)

    def _connect(self) -> None:
        self.ctx = Context()
        pvobjs = self.ctx.get_pvs(*[p for p, _, _, _ in PVS])
        self._subs = []  # keep STRONG refs : caproto holds subscriptions/callbacks weakly
        for pv in pvobjs:
            sub = pv.subscribe()
            sub.add_callback(self._make_cb(pv.name))
            self._subs.append(sub)

    def _make_cb(self, name: str):
        def cb(sub, response):
            try:
                self.q.put((name, float(response.data[0])))
            except Exception:
                pass
        return cb

    def _drain(self) -> None:
        got = False
        try:
            while True:
                name, value = self.q.get_nowait()
                got = True
                tile = self.tiles.get(name)
                if tile:
                    val_lbl, dot = tile
                    val_lbl.config(text=f"{value:.{self.decimals.get(name, 1)}f}")
                    dot.config(fg=OK)
        except queue.Empty:
            pass
        if got:
            self.status.config(text="live · receiving updates", fg=OK)
        self.root.after(150, self._drain)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
