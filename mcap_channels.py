#!/usr/bin/env python3

"""
Open an mcap file and report on the contents.
"""

import sys
from collections import Counter

from mcap.reader import make_reader


def count_mcap_messages(file_path):
    message_counts = Counter()

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

        print(f"--- Message Counts for: {file_path} ---")
        if not message_counts:
            print("No messages found in the file.")

        for topic, count in message_counts.most_common():
            print(f"{count:5d} | {topic}")

    except Exception as e:
        print(f"Error reading MCAP file: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python count_mcap.py <path_to_file.mcap>")
    else:
        count_mcap_messages(sys.argv[1])
