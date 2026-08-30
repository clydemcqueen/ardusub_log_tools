#!/usr/bin/env python3

"""
Extract extension log messages from an MCAP file and write each extension's logs to a text file.
"""

import argparse
import json
from collections import defaultdict

from mcap.reader import make_reader

import util

EXTENSION_LOG_PREFIX = "extensions/logs/"


def dump_extension_logs(mcap_file: str, verbose: bool = False) -> dict[str, int]:
    """
    Extract extension logs from an MCAP file.
    Writes output files with the pattern: <path>/<basename>_<extension_name>.txt
    Returns a dictionary mapping extension name to message count.
    """
    out_files = {}
    counts = defaultdict(int)

    try:
        with open(mcap_file, "rb") as f:
            reader = make_reader(f)

            # Check if summary has channels indexed
            topics = None
            summary = reader.get_summary()
            if summary and summary.channels:
                ext_topics = [c.topic for c in summary.channels.values() if c.topic.startswith(EXTENSION_LOG_PREFIX)]
                if not ext_topics:
                    print(f"No extension logs found in {mcap_file}")
                    return {}
                topics = ext_topics

            iter_kwargs = {"topics": topics} if topics is not None else {}

            for schema, channel, message in reader.iter_messages(**iter_kwargs):
                if not channel.topic.startswith(EXTENSION_LOG_PREFIX):
                    continue

                ext_name = channel.topic[len(EXTENSION_LOG_PREFIX) :]

                if ext_name not in out_files:
                    out_path = util.get_outfile_name(mcap_file, suffix=f"_{ext_name}", ext=".txt")
                    out_files[ext_name] = open(out_path, "w", encoding="utf-8")
                    if verbose:
                        print(f"  Extracting {channel.topic} -> {out_path}")

                try:
                    data = json.loads(message.data.decode("utf-8"))
                    if isinstance(data, dict):
                        text = data.get("message", json.dumps(data))
                    else:
                        text = str(data)
                except Exception:
                    text = message.data.decode("utf-8", errors="replace")

                out_files[ext_name].write(text.rstrip("\r\n") + "\n")
                counts[ext_name] += 1

    finally:
        for f_out in out_files.values():
            f_out.close()

    for ext_name, count in counts.items():
        out_path = util.get_outfile_name(mcap_file, suffix=f"_{ext_name}", ext=".txt")
        print(f"  Wrote {count:5d} messages to {out_path}")

    if not counts:
        print(f"  No extension logs found in {mcap_file}")

    return counts


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for MCAP files")
    parser.add_argument("-v", "--verbose", action="store_true", help="print extra progress details")
    args = parser.parse_args()

    files = util.expand_path(args.paths, args.recurse, ".mcap")
    print(f"Processing {len(files)} files")

    for file in files:
        print("-------------------")
        print(f"Reading {file}")
        dump_extension_logs(file, verbose=args.verbose)


if __name__ == "__main__":
    main()
