#!/usr/bin/env python3

"""
Extract embedded files from a dataflash (BIN) file.
"""

import argparse
import os
import re

from pymavlink import mavutil

import util


def sanitize_filename(name: str) -> str:
    """
    Replace characters that are unsafe for filenames.
    """
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return safe_name.strip("_")


class DataflashFileExtractor:
    def __init__(self, infile: str):
        self.infile = infile

    def extract(self):
        print(f"Extracting from {self.infile}")
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=False, dialect="ardupilotmega")

        files = {}  # Map sanitized_name -> bytearray

        while (msg := mlog.recv_match(blocking=False, type="FILE")) is not None:
            name = getattr(msg, "FileName", "")
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            name = name.rstrip("\x00").strip()

            if not name:
                continue

            offset = getattr(msg, "Offset", 0)
            length = getattr(msg, "Length", 0)
            data = getattr(msg, "Data", [])

            if not isinstance(data, (bytes, bytearray)):
                data = bytes(data[:length])
            else:
                data = data[:length]

            safe_name = sanitize_filename(name)

            if safe_name not in files:
                files[safe_name] = bytearray()

            end_pos = offset + length
            if len(files[safe_name]) < end_pos:
                files[safe_name].extend(b"\x00" * (end_pos - len(files[safe_name])))

            files[safe_name][offset:end_pos] = data

        if not files:
            print("  No embedded files found.")
            return

        base_name = os.path.splitext(os.path.basename(self.infile))[0]
        out_dir = os.path.join(os.path.dirname(self.infile), f"{base_name}_extracted")

        os.makedirs(out_dir, exist_ok=True)
        print(f"  Found {len(files)} files. Writing to {out_dir}/")

        for name, data in files.items():
            out_path = os.path.join(out_dir, name)
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"    Wrote {name} ({len(data)} bytes)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-r", "--recurse", help="enter directories looking for BIN files", action="store_true")
    parser.add_argument("path", nargs="+")
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, ".BIN")
    print(f"Processing {len(files)} files")

    for file in files:
        print("-------------------")
        extractor = DataflashFileExtractor(file)
        extractor.extract()


if __name__ == "__main__":
    main()
