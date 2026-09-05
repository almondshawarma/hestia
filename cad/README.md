# cad/ : 3D-printable parts

Parts we want people to remix are authored in **OpenSCAD** (parametric, so git-diffable, so one
file fits everyone's wall). Complex/learning parts can be SolidWorks, but then try to commit neutral
formats.

## Open-hardware format
**STL is not source** but a it's a mesh/"compiled binary", so you can print but not
meaningfully edit it. For every part, commit:

- the source (`.scad`, or `.step` exported from SolidWorks, STEP keeps editable solid
  geometry, but it loses SolidWorks' feature tree), and
- a printable `.stl`.

`.stl`/`.step`/`.f3d`/`.sldprt` are Git-LFS-tracked (see `.gitattributes`).

| Part                        | Source                         | Status |
|-----------------------------|--------------------------------|--------|
| `switch-flipper/`           | `toggle_flipper.scad`          | super rough, caliper-tune before printing |
| `puck-case/`                | TODO : vent + thermal-isolate BME280 from the ESP32 | TODO |

## Switch flipper
Renter-safe, mounts on the existing faceplate screws, one servo per gang, servo horn throws
the toggle, Fan+light 2-gang one plate, two servos, one ESP32-C3 (`firmware/
switch-flipper/`). **Measure the CAPITALISED params** in the `.scad` with calipers first.

## Puck case, don't skip the thermal note
The ESP32 self-heats and will bias the BME280 by 1–3 °C if they share a sealed box. The case
must **vent** and **physically offset** the sensor from the board (and the firmware should
deep-sleep between reads), kind of the enclosure's whole job.