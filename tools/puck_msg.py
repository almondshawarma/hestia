#!/usr/bin/env python3
"""Flash a temporary message on a Hestia puck LCD over EPICS (Channel Access).

This writes the display's command PV (HES:<area>:LCD<n>:MSG). The puck IOC republishes it to the
puck over MQTT, and the LCD takes over for ~10s before the face returns. The puck echoes what it
is showing to HES:<area>:LCD<n>:STAT (readback uses the :VAL/:RBV convention).

Why this instead of `caput`/caproto's put CLI: that CLI runs ast.literal_eval on the value, so a
plain string ("hello matthew") is a syntax error and you'd have to write "'hello matthew'". The
caproto *library* write() takes the text directly, so this stays ergonomic.

    python tools/puck_msg.py "hello matthew"            # default target HES:LR:LCD1:MSG
    python tools/puck_msg.py --pv HES:RMB:LCD1:MSG yo   # a different puck
    python tools/puck_msg.py --clear                    # wipe the current message now

If the IOC isn't on localhost, point the client at where it advertises, e.g.
    EPICS_CA_ADDR_LIST=<obelisk-ip> python tools/puck_msg.py "hi"
"""
from __future__ import annotations

import argparse

DEFAULT_PV = "HES:LR:LCD1:MSG"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("message", nargs="*", help="text to display (extra args are space-joined)")
    ap.add_argument("--pv", default=DEFAULT_PV, help=f"target MSG PV (default {DEFAULT_PV})")
    ap.add_argument("--clear", action="store_true", help="clear the current message instead")
    args = ap.parse_args()

    text = "" if args.clear else " ".join(args.message)
    if not args.clear and not text:
        ap.error("give a message to display, or pass --clear")

    from caproto.sync.client import write  # imported here so --help works without caproto

    write(args.pv, text, notify=True)
    print(f"{args.pv} <- {text!r}")


if __name__ == "__main__":
    main()
