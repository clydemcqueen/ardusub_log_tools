#!/usr/bin/env python3

"""
Compare a QGC-generated tlog to an mcap file.

Split this into 2 steps:
1. Run `mcap_to_tlog.py blueos.mcap` to convert mcap to tlog
2. Run `macp_tlog_diff.py qgc.tlog blueos.tlog` to compare the 2 tlog files

Known differences:

Span:
-- QGC creates a log file on launch and closes it on exit
-- blueos-recorder creates an mcap file when the vehicle arms and closes it when the vehicle disarms

Timestamps:
-- QGC uses the topside clock
-- blueos-recorder uses the Pi clock
-- blueos-recorder _might_ receive the message sooner than QGC? TODO verify

MAVLink2 extended fields are missing: https://github.com/bluerobotics/mavlink-server/issues/213

To work around the mavlink-server bug, we can force pymavlink to stay in v1.0 mode. The v1.0 parser will truncate the
messages to their v1.0 length, and we compare just the v1.0 fields.

TODO there are still some differences that I haven't tracked down
"""

import argparse
import difflib
import sys

from pymavlink import mavutil

# Force pymavlink to stay in MAVLink 1.0 (v1.0) mode when reading logs
mavutil.mavfile.auto_mavlink_version = lambda *args, **kwargs: None


def msg_to_string(msg):
    """Produce a canonical string version of the message that we can use difflib."""

    d = msg.to_dict()
    d.pop("mavpackettype", None)

    # Normalize float values of -0.0 to 0.0
    for k, v in d.items():
        if isinstance(v, float) and v == 0.0:
            d[k] = 0.0

    # Sort keys
    fields = ", ".join(f"{k}={d[k]}" for k in sorted(d.keys()))

    sys_id = msg.get_srcSystem()
    comp_id = msg.get_srcComponent()
    seq = msg.get_header().seq
    msg_type = msg.get_type()

    return f"[{sys_id:03d}:{comp_id:03d}] SEQ:{seq:03d} {msg_type} {{{fields}}}\n"


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("qgc", help="QGC-generated tlog")
    parser.add_argument("blueos", help="mcap_to_tlog.py generated tlog)")
    parser.add_argument("--types", default=None, help="comma separated list of message types to diff")
    parser.add_argument("-o", "--output", default="diff.patch", help="output file")
    args = parser.parse_args()

    if args.types:
        types = args.types.split(",")
    else:
        types = None

    # Assume that the QGC-generated tlog file fully covers the mcap file
    print(f"Reading {args.blueos} to establish time bounds...")
    blueos_mlog = mavutil.mavlink_connection(args.blueos, dialect="ardupilotmega")
    blueos_lines = []
    first_ts = None
    last_ts = None
    while True:
        msg = blueos_mlog.recv_match(blocking=False, type=types)
        if msg is None:
            break

        ts = getattr(msg, "_timestamp", 0.0)
        if first_ts is None:
            first_ts = ts
        last_ts = ts
        blueos_lines.append(msg_to_string(msg))

    if first_ts is None:
        print("Error: BlueOS tlog has no messages.")
        sys.exit(1)

    print(f"Time bounds established: {first_ts:.3f} to {last_ts:.3f}")

    print(f"Reading {args.qgc}...")
    qgc_mlog = mavutil.mavlink_connection(args.qgc, dialect="ardupilotmega")
    qgc_lines = []
    while True:
        msg = qgc_mlog.recv_match(blocking=False, type=types)
        if msg is None:
            break

        ts = getattr(msg, "_timestamp", 0.0)
        # Allow a tiny margin of error (0.01s) for timestamp alignment
        if first_ts - 0.01 <= ts <= last_ts + 0.01:
            qgc_lines.append(msg_to_string(msg))

    print("Generating diff...")
    diff = difflib.unified_diff(qgc_lines, blueos_lines, fromfile=args.qgc, tofile=args.blueos, n=3)

    print(f"Writing diff to {args.output}...")
    with open(args.output, "w", encoding="utf-8") as outfile:
        outfile.writelines(diff)


if __name__ == "__main__":
    main()
