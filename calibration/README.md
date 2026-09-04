# calibration/

Every channel gets three things: a **zero/reference**, a **scale**, and its **noise/statistics**.
Same discipline as `car-daq` (IMU calibration, CAN scaling). Store per-device coefficients
here (git them; keep site-specific secrets in `calibration_local.py`, which is gitignored).

## Sensors

- **BME280 temperature**: subtract the steady-state **self-heating offset** (measure vs a
  reference thermometer once the enclosure has settled); put it in the ESPHome `offset:` filter.
- **Humidity**: two-point salt calibration (saturated NaCl ≈ 75 % RH, MgCl₂ ≈ 33 %) is the
  real way, but one-point vs a good hygrometer is the lazy way.
- **Pressure**: offset to local station pressure (nearest METAR or WIP balcony node).
- **SCD40 CO₂**: forced recalibration outdoors (~420 ppm) or leave ASC on. The baseline is
  the whole ballgame; CO₂ sensors drift.
- **PM2.5**: co-locate two units to cross-check; apply **humidity correction** (particles
  swell when damp and read high).
- **Sound (mic → dBA)**: calibrate against any SPL meter and apply A-weighting, else it's a
  relative loudness index, not real dBA.
- **Geiger**: establish the background baseline over **days**, and respect **Poisson**: at
  20 cpm a 1-min count is 20 ± √20 (±22 %). To resolve a 5 % change you need ~400 counts
  (~20 min integration). Minute-resolution "deviations" are mostly counting noise. A bare tube
  is an area monitor, not a real instrument, so use a scintillator for muon-flux work.

## Actuators

- **Globe PWM** : find the **on-threshold duty** (LEDs flicker below it), apply a perceptual
  **gamma ≈ 2.2** (raw duty is linear in output, your eye is logarithmic), run PWM at a few
  kHz to kill flicker/banding. Eventually, fit duty→lux against the room's VEML7700 for a real
  "set N lux" loop?
- **Curtain / blind (motion axes)** : **home** to a hard stop (or TMC2209 StallGuard /
  endstop) to define zero, count steps end-to-end for steps-per-percent, measure and
  compensate **backlash**, tune the StallGuard threshold to catch a jam but not normal drag.
  The Venetian's two slat hard-stops are probably pretty natural tilt limits.
  