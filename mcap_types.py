#!/usr/bin/env python3

"""
Read messages from mcap files and report on the message types found.

Consider just the messages on the "mavlink/out" channel.
"""

import json
from argparse import ArgumentParser

from mcap.reader import make_reader

import util


def rate_str(count, tn, t0) -> str:
    if t0 >= tn:
        return " N/A"
    else:
        rate = round(count / (tn - t0))
        if rate > 1000:
            # Some messages all come at once
            return "HIGH"
        else:
            return f"{rate:4d}"


class TypeFinder:
    def __init__(self, filename: str):
        self.filename = filename

    def read(self):
        msg_count = {}  # Count
        msg_t0 = {}  # First timestamp
        msg_tn = {}  # Last timestamp

        # Don't crash reading a corrupt file
        try:
            with open(self.filename, "rb") as f:
                reader = make_reader(f)
                for schema, channel, message in reader.iter_messages(topics=["mavlink/out"]):
                    data = json.loads(message.data)
                    msg_data = data.get("message", {})
                    msg_type = msg_data.get("type")

                    msg_time_sec = message.log_time / 1e9

                    if msg_type not in msg_count:
                        msg_count[msg_type] = 1
                        msg_tn[msg_type] = msg_t0[msg_type] = msg_time_sec
                    else:
                        msg_count[msg_type] += 1
                        msg_tn[msg_type] = msg_time_sec

        except Exception as e:
            print(f'CRASH WITH ERROR "{e}", SHOWING PARTIAL RESULTS')

        print("TYPE                                  COUNT  RATE")

        for msg_type, count in sorted(msg_count.items()):
            rate = rate_str(count, msg_tn[msg_type], msg_t0[msg_type])
            print(f"{msg_type:35}  {count:6d}  {rate}")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for mcap files")
    parser.add_argument("path", nargs="+")
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, [".mcap"])
    print(f"Processing {len(files)} files")

    for file in files:
        print("-------------------")
        print(f"Reading {file}")
        scanner = TypeFinder(file)
        scanner.read()


if __name__ == "__main__":
    main()
