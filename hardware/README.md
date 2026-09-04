# hardware/ : KiCad

PCBs (KiCad is already the open standard; publish the project + Gerbers + BOM directly).

| Board             | Purpose                                                        | Status |
|-------------------|----------------------------------------------------------------|--------|
| `puck-carrier/`   | ESP32 dev board on headers + footprints for BME280/SCD40/LD2410/VEML7700/mic | TODO |
| `driver-board/`   | TMC2209 + terminals for the curtain/blind steppers             | TODO |

## When to spin a board
**When it replicates.** The puck carrier pays off because you build N of them, a batch of 5
from JLCPCB is like $2 each. One-off actuators stay on protoboard + printed brackets, so don't fab a
PCB for a thing you build once.

Ladder (same as `car-daq`): breadboard → soldered protoboard → **PCB when replicating** →
printed enclosure (`../cad/puck-case`, mind the BME280 thermal isolation).