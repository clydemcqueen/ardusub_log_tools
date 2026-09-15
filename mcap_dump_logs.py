#!/usr/bin/env python3

"""
Extract log messages (foxglove.Log type) from an MCAP file and write each log stream to a text file.
"""

import argparse
import json
from collections import defaultdict

from mcap.reader import make_reader

import util

FOXGLOVE_LOG_SCHEMA = "foxglove.Log"
EXTENSION_LOG_PREFIX = "extensions/logs/"


def topic_to_log_name(topic: str) -> str:
    """Derive a clean, safe output name/suffix from a channel topic."""
    if topic.startswith(EXTENSION_LOG_PREFIX):
        return topic[len(EXTENSION_LOG_PREFIX) :]
    if topic.startswith("services/") and topic.endswith("/log"):
        return topic[len("services/") : -len("/log")]
    if topic.startswith("services/"):
        return topic[len("services/") :].replace("/", "_")
    parts = topic.split("/")
    if len(parts) > 1 and parts[-1] in ("log", "logs"):
        parts = parts[:-1]
    return "_".join(parts)


def dump_logs(mcap_file: str, extensions_only: bool = False, verbose: bool = False) -> dict[str, int]:
    """
    Extract log messages from an MCAP file.
    Writes output files with the pattern: <path>/<basename>_<log_name>.txt
    Returns a dictionary mapping log name to message count.
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
                log_schema_ids = (
                    {s_id for s_id, s in summary.schemas.items() if s.name == FOXGLOVE_LOG_SCHEMA}
                    if summary.schemas
                    else set()
                )

                matching_topics = []
                for c in summary.channels.values():
                    if extensions_only:
                        if not c.topic.startswith(EXTENSION_LOG_PREFIX):
                            continue
                        if log_schema_ids and c.schema_id not in log_schema_ids:
                            continue
                        matching_topics.append(c.topic)
                    else:
                        if log_schema_ids:
                            if c.schema_id in log_schema_ids:
                                matching_topics.append(c.topic)
                        else:
                            if (
                                c.topic.startswith(EXTENSION_LOG_PREFIX)
                                or c.topic.startswith("services/")
                                or "log" in c.topic
                            ):
                                matching_topics.append(c.topic)

                if not matching_topics:
                    label = "extension logs" if extensions_only else "logs"
                    print(f"No {label} found in {mcap_file}")
                    return {}
                topics = matching_topics

            iter_kwargs = {"topics": topics} if topics is not None else {}

            for schema, channel, message in reader.iter_messages(**iter_kwargs):
                if extensions_only and not channel.topic.startswith(EXTENSION_LOG_PREFIX):
                    continue

                if schema and schema.name and schema.name != FOXGLOVE_LOG_SCHEMA:
                    continue

                log_name = topic_to_log_name(channel.topic)

                if log_name not in out_files:
                    out_path = util.get_outfile_name(mcap_file, suffix=f"_{log_name}", ext=".txt")
                    out_files[log_name] = open(out_path, "w", encoding="utf-8")
                    if verbose:
                        print(f"  Extracting {channel.topic} -> {out_path}")

                try:
                    data = json.loads(message.data.decode("utf-8"))
                    if isinstance(data, dict):
                        msg = data.get("message")
                        text = str(msg) if msg is not None else json.dumps(data)
                    else:
                        text = str(data)
                except Exception:
                    text = message.data.decode("utf-8", errors="replace")

                out_files[log_name].write(text.rstrip("\r\n") + "\n")
                counts[log_name] += 1

    finally:
        for f_out in out_files.values():
            f_out.close()

    for log_name, count in counts.items():
        out_path = util.get_outfile_name(mcap_file, suffix=f"_{log_name}", ext=".txt")
        print(f"  Wrote {count:5d} messages to {out_path}")

    if not counts:
        label = "extension logs" if extensions_only else "logs"
        print(f"  No {label} found in {mcap_file}")

    return counts


def dump_extension_logs(mcap_file: str, verbose: bool = False) -> dict[str, int]:
    """Compatibility wrapper to dump only extension logs."""
    return dump_logs(mcap_file, extensions_only=True, verbose=verbose)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for MCAP files")
    parser.add_argument("-v", "--verbose", action="store_true", help="print extra progress details")
    parser.add_argument("--extensions-only", action="store_true", help="only dump extension logs")
    args = parser.parse_args()

    files = util.expand_path(args.paths, args.recurse, ".mcap")
    print(f"Processing {len(files)} files")

    for file in files:
        print("-------------------")
        print(f"Reading {file}")
        dump_logs(file, extensions_only=args.extensions_only, verbose=args.verbose)


if __name__ == "__main__":
    main()
