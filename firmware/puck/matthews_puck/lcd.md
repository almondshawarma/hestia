# LCD module — how it works, and what we did

Local-only notes on the HD44780 character LCD wired to the bench puck. **The LCD itself is
not part of the shared Hestia repo** (see `hardware_pinout.csv`), so this file and
`firmware/puck/lcd-test.yaml` are kept separate from the committed `puck.yaml`/`puck-bench.yaml`.

## Hardware

16x2 HD44780-compatible character LCD, wired **parallel / 4-bit mode** (not an I2C backpack).
Wiring, from `hardware_pinout.csv`:

| LCD pin | ESP32 pin | Note |
|---|---|---|
| RS | GPIO33 | moved off GPIO12 — that's an ESP32 boot-strapping pin (flash voltage select); using it risked intermittent boot failures |
| E | GPIO13 | |
| D4–D7 | GPIO14 / 27 / 26 / 25 | 4-bit mode, D0–D3 unused/not connected |
| RW | GND | tied low permanently — write-only, no ESPHome pin needed |
| V0 | potentiometer wiper | contrast |
| VDD / BL+ | 5V (VIN) | |

## Software: ESPHome `lcd_gpio` display component

Config lives in `firmware/puck/lcd-test.yaml`. Key facts about the component
(`esphome/components/lcd_base` + `lcd_gpio`, read directly from the installed ESPHome package
at `~/Library/Application Support/pipx/venvs/esphome/lib/python3.14/site-packages/esphome/components/`
since the docs in my head were stale/wrong — see "gotchas" below):

- `display: platform: lcd_gpio` + `dimensions: 16x2` + `rs_pin`/`enable_pin`/`data_pins`.
- **Every refresh cycle, `LCDDisplay::update()` calls `clear()` (blanks the whole char buffer to
  spaces) THEN runs your `lambda:` THEN pushes the buffer to the physical display.** So you never
  need to manually clear — anything you don't re-print each cycle just disappears. This is why
  switching from a 2-row message back to a 1-row one needed no extra code.
- `update_interval:` controls how often the lambda re-runs (currently 5s).

## No Unicode — CGRAM custom characters (this is the whole trick)

The HD44780 ROM font is ASCII-only (plus some ROM-variant extras). It cannot render kaomoji,
CJK, or any Unicode symbol directly. What it *does* have: **8 programmable character slots**
(CGRAM, positions 0–7), each a 5-column x 8-row pixel bitmap, that behave like extra characters
`\x00`–`\x07` once loaded.

Declare them directly in YAML — no lambda needed for the glyphs themselves:

```yaml
user_characters:
  - position: 1        # 0-7
    data: [0b00100, 0b00100, 0b01110, 0b11111, 0b10001, 0b10001, 0b10001, 0b11111]
```

Each of the 8 ints is one pixel-row, 5 bits wide (bit 4 = leftmost column ... bit 0 = rightmost).
Design by sketching an 8x5 grid by hand.

**Gotcha — avoid CGRAM slot 0 in printed strings.** `it.print()` takes a `const char *`, and
`\x00` is the C-string null terminator — a string literal with a slot-0 reference embedded
truncates right there. Slots 1–7 are safe to embed directly in `print()`. We used slots 1–5 or
1–6 across the three faces below, never slot 0.

**Loading timing:** `user_characters:` is only pushed to CGRAM once, inside `setup()` (i.e. at
boot). It is **not** re-applied every refresh cycle. This matters for the future plan below.

Printing: `it.print(col, row, "literal text with \x01\x02 for custom slots");` — mix stock ASCII
and custom-glyph byte codes freely in the same string.

Centering an N-character string on the 16-column display: start column = `(16 - N) / 2`
(integer division).

## What we actually built, in order

1. First attempt called `id(lcd).create_char(pos, array)` from an `on_boot:` lambda. **Wrong
   API** — compile failed: `class esphome::lcd_gpio::GPIOLCDDisplay has no member named
   'create_char'`. Rather than guess again, found the real API by grepping the installed
   ESPHome package source directly. The class only exposes `loadchar(location, charmap[])`
   (imperative) and the YAML `user_characters:` key (declarative, boot-time-only) — no
   `create_char` exists at all in this version.
2. Iterated through three faces, each needing hand-drawn glyphs:
   - `凸(⊙▂⊙✖ )` — 4 custom glyphs (凸 ⊙ ▂ ✖), later followed by a second row `哈曼 ben dan`
     (2 more glyphs for 哈/曼 — explicitly caveated as illegible stylized blocks, since 5x8
     genuinely cannot render real CJK strokes; real CJK dot-matrix fonts need ~12x12+).
   - `ᕙ(⇀o↼‶)ᕗ` — 5 custom glyphs (ᕙ ⇀ ↼ ‶ ᕗ), centered on row 0, row 1 left blank.
   - `(●´⌓`●)` — only 3 custom glyphs needed (● ´ ⌓), since `(`, `)`, `` ` ``, and `o` are
     already in the stock ASCII ROM.
3. Workflow for every change (this is the reliable loop — use it for future edits):
   - `esphome config firmware/puck/lcd-test.yaml` — schema validation only. Does **not** catch
     lambda/C++ mistakes (the `create_char` typo passed this step clean).
   - `esphome compile firmware/puck/lcd-test.yaml` — actually compiles the C++, catches real
     API errors. Always run this before flashing.
   - Free the serial port first if `ioc/puck_ioc.py --serial` is running against the same
     `/dev/cu.usbserial-0001` — only one process can hold it.
   - `esphome upload firmware/puck/lcd-test.yaml --device /dev/cu.usbserial-0001` — flashes
     *and* hard-resets the board via the RTS control line. This turned out to be the only
     reliable way to force a real ESP32 reset on this bench setup: unplugging/replugging the
     USB-serial adapter did **not** reset the chip (it's powered from a separate rail, so only
     the data connection bounced, not the MCU itself).

## Temporary messages over EPICS

Flashing text on the LCD is a **PV write**, not a raw MQTT publish — the whole point of Hestia is
that devices are spoken for as process variables. The puck IOC (`ioc/puck_ioc.py`) serves the LCD
as its own logical device (peer to `BME1`/`MIC1` on the same ESP32 — EPICS names by *function*,
not by board):

- `HES:LR:LCD1:MSG`  : **write** the text to display (a string PV).
- `HES:LR:LCD1:STAT` : **read** back what the puck reports it is showing (`IDLE` when cleared).

Data flow: `caput MSG` → IOC's `Lcd.msg` putter republishes to MQTT `hestia/LR/puck1/msg` → this
firmware's `on_message` latches it and takes over the LCD for ~10s (row 0 = first 16 chars, row 1
= next 16), then the face returns. Re-write to refresh the hold; write an empty string to clear.
The firmware echoes what's on screen to `hestia/LR/puck1/msg/state`, which the IOC routes back to
`STAT` — the `:VAL`/`:RBV` "never trust a command without the readback" convention (`docs/NAMING.md`).
This override sits **above** the `SHUT UP!!!` loud-noise flash, so a pushed message wins even in a
loud room. Firmware side: `g_msg` / `g_msg_until` globals, `mqtt: on_message:` (+ the `mqtt_client`
id used to publish the echo), a 500ms expiry interval, and a block at the top of the display lambda.

Sending (an ESP32 can't speak Channel Access, so MQTT stays the last hop to the device, but you
never touch it directly):

```
python tools/puck_msg.py "hello matthew"      # ergonomic helper (uses the caproto library)
python tools/puck_msg.py --clear              # wipe it now
caput HES:LR:LCD1:MSG "hello matthew"         # if you have EPICS base
caget HES:LR:LCD1:STAT                        # readback: what's actually showing
```

Note: caproto's *put CLI* (`python -m caproto.commandline.put`) runs `ast.literal_eval` on the
value, so a plain string errors — you'd have to write `"'hello matthew'"`. `tools/puck_msg.py`
uses the caproto *library* `write()` instead, which takes the text directly. Point the client at
the IOC with `EPICS_CA_ADDR_LIST` if it isn't on localhost.

This needs one firmware flash to land the subscribe + echo (OTA from a machine on the puck's router
LAN, or serial). After that it's pure PV writes, so no reflash ever again.

## Future plan: sensor-reactive "tamagotchi" face

Goal (from Matthew): drive the LCD's expression from the puck's own live environment readings
(temp/RH/pressure/lux/sound — see `puck.yaml`/`puck-bench.yaml`) so the face's mood reacts to
the room in real time.

**Recommendation: do this entirely on-device in ESPHome, not through the IOC/MQTT/Channel
Access round-trip.** The sensors and the LCD live on the same ESP32 — there's no reason to
leave the chip, and looping through the network path would add latency and a second point of
failure for something that's fundamentally a local reflex.

Concretely, when picking this back up:

- Merge the `display:` block here into a firmware that also has the `sensor:` definitions
  (copy from `puck-bench.yaml`), giving each sensor an explicit `id:` (already done there:
  `s_temp`, `s_rh`, `s_pres`, `s_lux`, `s_sound`) so the display lambda can read
  `id(s_temp).state` etc.
- **`user_characters:` won't work for a multi-mood face** — it only loads once at boot (see
  above). Swapping expressions at runtime means calling the imperative `id(lcd).loadchar(pos,
  array)` from a lambda, triggered when the mood actually changes (e.g. in an `on_value` sensor
  trigger, or by comparing against the last-drawn mood each update cycle).
- Only 8 CGRAM slots exist **total**, shared across every mood. A face with several expressions
  will need to reuse the same slot numbers and reload them with `loadchar()` per mood-change,
  not try to keep every glyph for every mood resident at once.
- Reload CGRAM only on an actual mood change, not every `update_interval` tick — `loadchar()` is
  several GPIO writes per glyph row; doing it every cycle would be wasteful and could cause
  visible flicker for no benefit, since the glyph bitmap doesn't need to move, only which glyphs
  are loaded.
- Rough mood mapping to start from: too hot/humid -> a "sweating/distressed" variant; dark room
  -> a sleepy face; a sound spike -> a startled face. Thresholds TBD against real bench data
  once this is picked up.

Not yet implemented — `lcd-test.yaml` currently just prints a fixed face, no sensor logic.
