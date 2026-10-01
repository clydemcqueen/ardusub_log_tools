#!/usr/bin/env python3
"""
Log filtering utilities for tlog (MAVLink telemetry) and BIN (Dataflash) files.
"""

from __future__ import annotations

import struct

from pymavlink import mavutil

from ardusub_log_tools.core import util


def filter_tlog(reader, msg_types=None, sysid=None, compid=None, max_msgs=500000, verbose=False):
    """
    Filter messages and write them to a new tlog file (<base>_asl_filtered.tlog).
    """
    output_filename = util.get_outfile_name(reader.name, suffix="_filtered", ext=".tlog")
    if verbose:
        print(f"Writing {output_filename}")

    with open(output_filename, "wb") as outfile:
        msg_count = 0
        kept_count = 0

        for msg in reader:
            msg_count += 1

            # Stop if we've hit the message limit
            if kept_count >= max_msgs:
                if verbose:
                    print(f"Wrote {kept_count} messages, stopping")
                break

            # Filter by sysid and compid
            if sysid is not None and sysid != msg.get_srcSystem():
                continue
            if compid is not None and compid != msg.get_srcComponent():
                continue

            # Filter by message type
            if msg_types is not None and msg.get_type() not in msg_types:
                continue

            # Reconstruct the tlog header (8 bytes, Big Endian unsigned long long, microseconds)
            header = struct.pack(">Q", int(msg._timestamp * 1_000_000))
            outfile.write(header)
            outfile.write(msg.get_msgbuf())
            kept_count += 1

    if verbose:
        print(f"Filtered {msg_count} messages -> {kept_count} kept in {output_filename}")
    return output_filename


def filter_bin(
    input_file, output_file, keep_types=None, exclude_types=None, start_time=None, stop_time=None, verbose=False
):
    """
    Read Dataflash (BIN) file, filter messages, and write new BIN file with kept messages.
    Always preserves FMT messages to ensure file remains valid.
    """
    if verbose:
        print(f"Reading {input_file}")
        print(f"Writing {output_file}")

    mlog = mavutil.mavlink_connection(input_file, robust_parsing=False, dialect="ardupilotmega")

    # Ensure FMT is always kept
    if keep_types is not None and "FMT" not in keep_types:
        keep_types.append("FMT")

    msg_count = 0
    kept_count = 0

    with open(output_file, "wb") as outfile:
        while True:
            msg = mlog.recv_match(blocking=False)
            if msg is None:
                break

            msg_count += 1
            msg_type = msg.get_type()
            timestamp = getattr(msg, "_timestamp", 0.0)

            # Always keep FMT messages
            if msg_type == "FMT":
                outfile.write(msg.get_msgbuf())
                kept_count += 1
                continue

            # Filter by time
            if start_time is not None and timestamp < start_time:
                continue
            if stop_time is not None and timestamp > stop_time:
                continue

            # Filter by type
            if keep_types is not None and msg_type not in keep_types:
                continue
            if exclude_types is not None and msg_type in exclude_types:
                continue

            outfile.write(msg.get_msgbuf())
            kept_count += 1

    if verbose:
        print(f"Read {msg_count} messages, kept {kept_count}")
    return output_file
