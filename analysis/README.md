# analysis/

Notebooks + scripts that turn captured data into nice plots for reports or anything else!

## Conventions
- Raw captures under `analysis/data/raw/` (gitignored, KEEP LOCAL; commit only small
  processed outputs or sample data). Each capture folder carries a `capture.json` with
  provenance, so include timestamp, device, conditions, calibration coefficients used, etc.
- One notebook per concept (mirrors `docs/THEORY.md`): `humidifier_step_response.ipynb`,
  `radiation_counting_stats.ipynb`, `dimming_perception.ipynb`, ...
- Notebooks should ideally be **re-runnable** from committed data/samples so every figure is
  reproducible on a whim.
- Plots use the shared themes (`../visualization/`)

## Capture provenance (why it matters)
Log conditions at capture time: `{ "pv": "HES:LR:BME1:RH", "start": "...", "setpoint": 45,
"notes": "door closed, humidifier knob at med" }`.
