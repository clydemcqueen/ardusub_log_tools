#!/usr/bin/env python3

"""
Convert MCAP files containing MAVLink messages to tlog files readable by pymavlink.
"""

import argparse
import json
import struct

from mcap.reader import make_reader
from pymavlink.dialects.v20 import ardupilotmega as mavlink

import util


def get_resolved_kwargs(msg_class, msg_data):
    kwargs = {}
    for k, v in msg_data.items():
        if k == "mavtype":
            k = "type"

        if isinstance(v, dict) and "type" in v:
            v = v["type"]

        expected_type = None
        if hasattr(msg_class, "fieldnames") and k in msg_class.fieldnames:
            idx = msg_class.fieldnames.index(k)
            expected_type = msg_class.fieldtypes[idx]

        if isinstance(v, str):
            if expected_type == "char":
                v = v.encode("utf-8")
            else:
                if "|" in v:
                    parts = [p.strip() for p in v.split("|")]
                    res = 0
                    for p in parts:
                        enum_v = getattr(mavlink, p, None)
                        if enum_v is not None:
                            res |= enum_v
                    v = res
                else:
                    enum_v = getattr(mavlink, v, None)
                    if enum_v is not None:
                        v = enum_v
                    elif v == "":
                        v = 0

        kwargs[k] = v

    return kwargs


def mcap_to_tlog(mcap_file: str):
    output_filename = util.get_outfile_name(mcap_file, ext=".tlog")
    print(f"Reading {mcap_file}")
    print(f"Writing {output_filename}")

    msg_count = 0
    seen_messages = set()

    try:
        with open(mcap_file, "rb") as f_in, open(output_filename, "wb") as f_out:
            reader = make_reader(f_in)
            mav = mavlink.MAVLink(None)

            for schema, channel, message in reader.iter_messages():
                # tlog header is 8 bytes, Big Endian unsigned long long, microseconds
                timestamp_us = int(message.log_time / 1000)

                try:
                    data = json.loads(message.data)
                except Exception:
                    continue

                if not isinstance(data, dict) or "message" not in data or "header" not in data:
                    # print(f"reject {channel.topic}")
                    # We reject channels that don't containe full MAVLink messages. These fall into 2 buckets:
                    # 1. Other logs, services/wifi-manager
                    # 2. Duplicated unrolled fields, like mavlink/1/194/HEARTBEAT/autopilot
                    continue

                header = data["header"]
                msg_data = data["message"]
                if "type" not in msg_data:
                    continue

                msg_type = msg_data.pop("type")

                # Deduplication
                sys_id = header.get("system_id", 1)
                comp_id = header.get("component_id", 1)
                seq = header.get("sequence", 0)
                msg_id = header.get("message_id", 0)

                msg_tuple = (timestamp_us, sys_id, comp_id, seq, msg_id)
                if msg_tuple in seen_messages:
                    continue
                seen_messages.add(msg_tuple)

                # To prevent unbounded memory growth, limit seen_messages size
                if len(seen_messages) > 10000:
                    seen_messages.clear()
                    seen_messages.add(msg_tuple)

                msg_class = getattr(mavlink, f"MAVLink_{msg_type.lower()}_message", None)
                if msg_class:
                    kwargs = get_resolved_kwargs(msg_class, msg_data)

                    try:
                        msg = msg_class(**kwargs)

                        mav.srcSystem = sys_id
                        mav.srcComponent = comp_id

                        # pack handles the header generation
                        packed_bytes = msg.pack(mav)

                        # Fix sequence number to match original log
                        msg_buf = bytearray(packed_bytes)
                        # In MAVLink v2, seq is byte 4. In v1, it's byte 2.
                        # pymavlink pack() creates MAVLink v2 by default since we import from v20
                        if msg_buf[0] == 253:  # MAVLink v2
                            msg_buf[4] = seq
                        elif msg_buf[0] == 254:  # MAVLink v1
                            msg_buf[2] = seq

                        tlog_header = struct.pack(">Q", timestamp_us)
                        f_out.write(tlog_header)
                        f_out.write(packed_bytes)

                        msg_count += 1
                    except Exception as e:
                        print(f"Caught exception {e}")
                        pass

        print(f"Converted {msg_count} messages.")
    except Exception as e:
        print(f"Error processing {mcap_file}: {e}")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories to read")
    parser.add_argument(
        "-r",
        "--recurse",
        action="store_true",
        help="enter directories looking for mcap files",
    )
    args = parser.parse_args()

    files = util.expand_path(args.paths, args.recurse, ".mcap")

    if not files:
        print("No .mcap files found.")
        return

    for file in files:
        mcap_to_tlog(file)


if __name__ == "__main__":
    main()
