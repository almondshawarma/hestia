#!/usr/bin/env python3
"""Hestia : a light live-PV monitor GUI (Tkinter + caproto, pure Python, zero extra deps).

Test the whole EPICS stack on your laptop, offline:
    pip install caproto
    python ioc/puck_ioc.py --sim      # terminal 1: serve synthetic PVs on localhost
    python gui/hestia_gui.py          # terminal 2: watch them update live

Channel Access is location-transparent, so this also works against the real IOC on the
Obelisk : just set EPICS_CA_ADDR_LIST to its reachable IP before launching.

"""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

# Look on localhost by default (matches `puck_ioc.py --sim`). Override via env for a remote IOC.
os.environ.setdefault("EPICS_CA_ADDR_LIST", "127.0.0.1")
os.environ.setdefault("EPICS_CA_AUTO_ADDR_LIST", "no")

from caproto.threading.client import Context  # noqa: E402  (env must be set first)

# ── brand tokens: local override first, committed default otherwise ────────────
import brand_default as _bd  # noqa: E402
try:
    import brand as _b  # noqa: E402  your private Helios skin (gitignored)
    _PALETTE = {**_bd.PALETTE, **getattr(_b, "PALETTE", {})}
    _FONTS = {**_bd.FONTS, **getattr(_b, "FONTS", {})}
    BRAND_SRC = "brand.py"
except ImportError:
    _PALETTE, _FONTS, BRAND_SRC = _bd.PALETTE, _bd.FONTS, "brand_default.py"


def _mix(a: str, b: str, t: float) -> str:
    """Blend two #rrggbb colours (t=0 → a, t=1 → b)."""
    a, b = a.lstrip("#"), b.lstrip("#")
    ch = [int(a[i:i + 2], 16) + (int(b[i:i + 2], 16) - int(a[i:i + 2], 16)) * t for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(round(c) for c in ch)


# role → concrete UI colours (surface/edge/dim derived from the roles so brand files stay minimal)
BG = _PALETTE["bg"]
INK = _PALETTE["ink"]
ACCENT = _PALETTE["accent"]
MUTED = _PALETTE["muted"]
FLOW = _PALETTE["flow"]
CARD = _mix(BG, INK, 0.06)   # slightly lifted surface
EDGE = _mix(BG, INK, 0.16)   # hairline border
DIM = _mix(BG, INK, 0.32)    # faint PV-name text

# (PV name, label, units, decimals)
PVS = [
    ("HES:LR:BME1:TEMP", "Temperature", "°C", 1),
    ("HES:LR:BME1:RH", "Humidity", "%", 1),
    ("HES:LR:BME1:PRES", "Pressure", "hPa", 1),
    ("HES:LR:LUX1:LUX", "Illuminance", "lx", 0),
    ("HES:LR:MIC1:LVL", "Sound", "rel", 2),
]


def _fam(root: tk.Tk, *candidates: str) -> str:
    """First installed family from the candidates (cross-platform), else a Tk default."""
    try:
        installed = set(tkfont.families(root))
    except tk.TclError:
        installed = set()
    for c in candidates:
        if c and c in installed:
            return c
    return candidates[-1] if candidates else "Courier"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.tiles: dict = {}
        self.decimals = {pv: d for pv, _, _, d in PVS}

        # brand choice first, then cross-platform fallbacks (macOS / Windows / Linux)
        mono = _fam(root, _FONTS.get("mono", ""),
                    "IBM Plex Mono", "Menlo", "Consolas", "DejaVu Sans Mono", "Courier New")
        disp = _fam(root, _FONTS.get("display", ""), "Playfair Display", "Georgia", mono)
        f_head = tkfont.Font(family=disp, size=15, weight="bold")
        f_lbl = tkfont.Font(family=mono, size=10)
        f_val = tkfont.Font(family=mono, size=30, weight="bold")
        f_unit = tkfont.Font(family=mono, size=12)
        f_pv = tkfont.Font(family=mono, size=8)

        root.title("Hestia — Control Room")
        root.configure(bg=BG)

        tk.Label(root, text="LIVING ROOM PUCK", fg=ACCENT, bg=BG, font=f_head)\
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

        self.status = tk.Label(root, text=f"connecting…",
                               fg=MUTED, bg=BG, font=f_lbl)
        self.status.grid(row=2, column=0, columnspan=len(PVS), sticky="w", padx=16, pady=(2, 12))

        self._connect()
        self.root.after(150, self._drain)

    def _connect(self) -> None:
        # NB: caproto's THREADING-client monitors don't deliver on Windows (the sync client
        # behind caget/camonitor is fine). Reads work on both, so we POLL over the persistent
        # connections on a background thread instead of subscribing to push updates.
        self.ctx = Context()
        self.pvs = self.ctx.get_pvs(*[p for p, _, _, _ in PVS])
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self) -> None:
        for pv in self.pvs:
            try:
                pv.wait_for_connection(timeout=5)
            except Exception:
                pass
        while True:
            for pv in self.pvs:
                try:
                    self.q.put((pv.name, float(pv.read(timeout=2).data[0])))
                except Exception:
                    pass
            time.sleep(1.0)

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
                    dot.config(fg=FLOW)
        except queue.Empty:
            pass
        if got:
            self.status.config(text="live · receiving updates", fg=FLOW)
        self.root.after(150, self._drain)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
