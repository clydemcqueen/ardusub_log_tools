#!/usr/bin/env python3

"""
Open an mcap file and report on the contents.
"""

import argparse
import json
import os
from collections import Counter

from mcap.reader import make_reader

import util


def count_mcap_messages(file_path, extract=False):
    message_counts = Counter()
    extract_files = {}

    try:
        # Open the MCAP file in binary read mode
        with open(file_path, "rb") as f:
            reader = make_reader(f)

            # iter_messages() returns a tuple of (schema, channel, message)
            for schema, channel, message in reader.iter_messages():
                # Use the topic name as the primary identifier (e.g., "/mavlink/system_time")
                identifier = channel.topic

                # If a Foxglove/Zenoh schema is attached, append it for more context
                if schema and schema.name:
                    identifier = f"{channel.topic} ({schema.name})"

                message_counts[identifier] += 1

                is_service_log = channel.topic.startswith("services/") and channel.topic.endswith("/log")
                is_sys_info = channel.topic.startswith("system_information/")

                if extract and (is_service_log or is_sys_info):
                    parts = channel.topic.split("/")
                    if len(parts) >= 2:
                        service_name = parts[1]
                        if service_name not in extract_files:
                            base_name = os.path.splitext(os.path.basename(file_path))[0]
                            dir_name = os.path.dirname(file_path)
                            out_path = os.path.join(dir_name, f"{base_name}_{service_name}.txt")
                            extract_files[service_name] = open(out_path, "w", encoding="utf-8")
                            print(f"Extracting {channel.topic} to {out_path}")

                        f_out = extract_files[service_name]
                        try:
                            data = json.loads(message.data.decode("utf-8"))
                            text = data.get("message", json.dumps(data))
                        except Exception:
                            text = message.data.decode("utf-8", errors="replace")

                        f_out.write(text + "\n")

        print(f"--- Message Counts for: {file_path} ---")
        if not message_counts:
            print("No messages found in the file.")

        for topic, count in message_counts.most_common():
            print(f"{count:5d} | {topic}")

    except Exception as e:
        print(f"Error reading MCAP file: {e}")
    finally:
        for f_out in extract_files.values():
            f_out.close()


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories")
    parser.add_argument("--extract", action="store_true", help="Extract services/*/log channels into text files")
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, ".mcap")

    for file in files:
        count_mcap_messages(file, extract=args.extract)


if __name__ == "__main__":
    main()
