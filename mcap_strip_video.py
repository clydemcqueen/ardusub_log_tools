#!/usr/bin/env python3

"""
Open one or more MCAP files and write new MCAP files with the video removed.
"""

import argparse
import os

from mcap.reader import make_reader
from mcap.writer import CompressionType, Writer

import util


def is_video_channel(topic: str, schema_name: str | None) -> bool:
    """
    Determine if a channel contains video data based on its topic name or schema.
    """
    if topic.startswith("video/") or topic.startswith("/video/"):
        return True
    if schema_name:
        schema_lower = schema_name.lower()
        if "compressedvideo" in schema_lower or "compressedimage" in schema_lower or "rawimage" in schema_lower:
            return True
    return False


def strip_video_from_mcap(file_path: str):
    """
    Read an MCAP file, filter out video messages/channels, and save to a new MCAP file.
    """
    out_path = util.get_outfile_name(file_path, suffix="_no_video", ext=".mcap")
    print(f"Reading {file_path}")
    print(f"Writing {out_path}")

    try:
        in_size = os.path.getsize(file_path)
    except OSError:
        in_size = 0

    message_count = 0
    stripped_count = 0

    schema_map = {}
    channel_map = {}

    try:
        with open(file_path, "rb") as f_in, open(out_path, "wb") as f_out:
            reader = make_reader(f_in)
            writer = Writer(f_out, compression=CompressionType.ZSTD)
            writer.start()

            for schema, channel, message in reader.iter_messages():
                schema_name = schema.name if schema else None
                if is_video_channel(channel.topic, schema_name):
                    stripped_count += 1
                    continue

                # Register schema if we haven't already
                if schema:
                    if schema.id not in schema_map:
                        new_schema_id = writer.register_schema(
                            name=schema.name, encoding=schema.encoding, data=schema.data
                        )
                        schema_map[schema.id] = new_schema_id
                    dest_schema_id = schema_map[schema.id]
                else:
                    dest_schema_id = 0

                # Register channel if we haven't already
                if channel.id not in channel_map:
                    new_channel_id = writer.register_channel(
                        topic=channel.topic, message_encoding=channel.message_encoding, schema_id=dest_schema_id
                    )
                    channel_map[channel.id] = new_channel_id

                # Write the message
                writer.add_message(
                    channel_id=channel_map[channel.id],
                    log_time=message.log_time,
                    data=message.data,
                    publish_time=message.publish_time,
                    sequence=message.sequence,
                )
                message_count += 1

            writer.finish()

        try:
            out_size = os.path.getsize(out_path)
        except OSError:
            out_size = 0

        print(f"Done: {message_count:,} messages written, {stripped_count:,} video messages stripped.")
        if in_size > 0:
            reduction = ((in_size - out_size) / in_size) * 100
            print(f"Size: {in_size:,} bytes -> {out_size:,} bytes (reduced by {reduction:.1f}%)")
        else:
            print(f"Size: {out_size:,} bytes")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories")
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, ".mcap")

    for file in files:
        strip_video_from_mcap(file)


if __name__ == "__main__":
    main()
