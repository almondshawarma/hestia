# gui/ : light live-PV monitor

`hestia_gui.py` : a Tkinter + caproto control-room panel ((pure Python, no extra deps beyond
caproto). Watches the puck PVs over Channel Access and updates live.

## Test the whole EPICS stack on your laptop (offline, no hardware/router)

Two terminals (PowerShell on Windows):

```powershell
python ioc\puck_ioc.py --sim      # 1: serve synthetic PVs on localhost (127.0.0.1)
python gui\hestia_gui.py          # 2: watch them tick
```

`--sim` drives the PVs with synthetic data (no MQTT), so you can exercise IOC → Channel
Access → GUI with nothing but `pip install caproto`.

## Point it at the real IOC (Obelisk) instead

Channel Access is location-transparent, so the same GUI works against the deployed IOC:

```powershell
$env:EPICS_CA_ADDR_LIST = "<obelisk-CA-reachable-ip>"; python gui\hestia_gui.py
```

(The Obelisk IOC currently binds loopback only; expose it over Tailscale via a CA gateway
when you want remote access — see docs/DEPLOYMENT.md.)

## Notes / next

- Read-only for now (the puck is all sensors), when actuators are ready (lights, curtains),
  add `caput` controls, an entry + button that writes the `:VAL` setpoint.
- For the eventual apartment floor-plan "control room," graduate to **Phoebus** or **PyDM** (?), and
this stays the quick dev/monitor panel.
- caproto holds subscriptions/callbacks weakly, the GUI keeps strong refs in `self._subs`.
