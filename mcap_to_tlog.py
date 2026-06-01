#!/usr/bin/env python3

"""
Convert MCAP files containing MAVLink messages to tlog files readable by pymavlink.

We only look at the "mavlink/out" channel, this seems to contain everything we need.
"""

import argparse
import json
import struct

from mcap.reader import make_reader
from pymavlink.dialects.v20 import ardupilotmega as mavlink

import util


def convert_json_to_pymavlink(msg_class, msg_data):
    """
    Convert JSON values to pymavlink-compatible values.

    -- Map 'mavtype' key to 'type' (special case for pymavlink).
    -- If a field is a dictionary containing a 'type' key (common in enum objects), extract the raw 'type' value.
    -- If the target field type is 'char', encodes string values to UTF-8 bytes.
    -- If a string contains a bitwise-OR combination (e.g., 'A|B'), split and resolve each constant against the
       pymavlink dialect to compute the combined integer mask.
    -- If a string is a named enum constant, resolve it to its integer value.
    -- If a string is empty (''), default value to 0.

    Args:
        msg_class: The pymavlink message class (e.g., MAVLink_heartbeat_message).
        msg_data (dict): The dictionary of field values extracted from the MCAP JSON payload.

    Returns:
        dict: A dictionary of resolved keyword arguments ready to be passed to msg_class().
    """
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
                    result = 0
                    for p in parts:
                        enum_v = getattr(mavlink, p, None)
                        if enum_v is not None:
                            result |= enum_v
                    v = result
                else:
                    enum_v = getattr(mavlink, v, None)
                    if enum_v is not None:
                        v = enum_v
                    elif v == "":
                        v = 0

        kwargs[k] = v

    return kwargs


def mcap_to_tlog(mcap_file: str, msg_types: list | None = None):
    output_filename = util.get_outfile_name(mcap_file, ext=".tlog")
    print(f"Reading {mcap_file}")
    print(f"Writing {output_filename}")

    msg_count = 0

    with open(mcap_file, "rb") as f_in, open(output_filename, "wb") as f_out:
        reader = make_reader(f_in)
        mav = mavlink.MAVLink(None)

        for schema, channel, message in reader.iter_messages(topics=["mavlink/out"]):
            # tlog header is 8 bytes, Big Endian unsigned long long, microseconds
            timestamp_us = int(message.log_time / 1000)

            data = json.loads(message.data)
            header = data["header"]
            msg_data = data["message"]
            msg_type = msg_data.pop("type")

            if msg_types is not None and msg_type not in msg_types:
                continue

            sys_id = header.get("system_id", 1)
            comp_id = header.get("component_id", 1)
            seq = header.get("sequence", 0)

            msg_class = getattr(mavlink, f"MAVLink_{msg_type.lower()}_message", None)
            if msg_class:
                kwargs = convert_json_to_pymavlink(msg_class, msg_data)

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
                f_out.write(msg_buf)

                msg_count += 1

    print(f"Converted {msg_count} messages")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories")
    parser.add_argument("--types", default=None, help="comma separated list of MAVLink message types")
    args = parser.parse_args()
    msg_types = args.types.split(",") if args.types else None
    files = util.expand_path(args.paths, args.recurse, ".mcap")

    for file in files:
        mcap_to_tlog(file, msg_types)


if __name__ == "__main__":
    main()
