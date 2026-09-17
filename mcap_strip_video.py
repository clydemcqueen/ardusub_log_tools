#!/usr/bin/env python3

"""
Open one or more MCAP files and write new MCAP files with the video removed.

Supports standard mode (writes <stem>_asl_no_video.mcap) or in-place mode
(--in-place: renames original to <stem>_video.mcap and writes stripped file to <stem>.mcap).
"""

import argparse
import os
import tempfile

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


def strip_video_from_mcap(file_path: str, in_place: bool = False) -> bool:
    """
    Read an MCAP file, filter out video messages/channels, and save to an MCAP file.

    If in_place is False (default):
        Saves the stripped file to <path>/<root>_asl_no_video.mcap, leaving original untouched.
    If in_place is True:
        Renames the original file to <path>/<root>_video.mcap and saves the stripped
        file to <path>/<root>.mcap. Safety checks ensure no data is destroyed.
    """
    if not os.path.isfile(file_path):
        print(f"Error: '{file_path}' is not a valid file.")
        return False

    dirname, basename = os.path.split(file_path)
    root, ext = os.path.splitext(basename)

    if ext.lower() != ".mcap":
        print(f"Error: '{file_path}' does not have a .mcap extension.")
        return False

    target_dir = dirname if dirname else "."

    if in_place:
        if not os.access(file_path, os.R_OK | os.W_OK):
            print(f"Error: '{file_path}' is not readable and writable.")
            return False

        if not os.access(target_dir, os.W_OK):
            print(f"Error: Directory '{target_dir}' is not writable.")
            return False

        if root.endswith("_video"):
            print(f"Skipping '{file_path}': filename already ends with '_video'.")
            return False

        video_path = os.path.join(dirname, f"{root}_video{ext}")
        if os.path.exists(video_path):
            print(f"Skipping '{file_path}': target '{video_path}' already exists; aborting to avoid overwriting data.")
            return False

        # Create a unique temporary file in the same directory for atomic replace
        temp_fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix=f".{root}_strip_tmp_", suffix=ext)
        os.close(temp_fd)
        write_path = temp_path
        print(f"Processing {file_path} in-place:")
        print(f"  Stripped -> {file_path}")
        print(f"  Original (with video) -> {video_path}")
    else:
        if not os.access(file_path, os.R_OK):
            print(f"Error: '{file_path}' is not readable.")
            return False

        if not os.access(target_dir, os.W_OK):
            print(f"Error: Directory '{target_dir}' is not writable.")
            return False

        out_path = util.get_outfile_name(file_path, suffix="_no_video", ext=".mcap")
        if os.path.abspath(file_path) == os.path.abspath(out_path):
            print(f"Error: Output file '{out_path}' matches input file '{file_path}'.")
            return False

        write_path = out_path
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
        with open(file_path, "rb") as f_in, open(write_path, "wb") as f_out:
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

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        if os.path.exists(write_path):
            try:
                os.remove(write_path)
            except OSError:
                pass
        return False

    if in_place:
        if stripped_count == 0:
            print(f"No video messages found in {file_path}; file left unchanged.")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return True

        # Re-check before renaming in case video_path was created concurrently
        if os.path.exists(video_path):
            print(f"Error: target '{video_path}' was created during processing; aborting rename.")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False

        try:
            # Step 1: Rename original file to video_path
            os.replace(file_path, video_path)
            try:
                # Step 2: Rename temp file to file_path
                os.replace(temp_path, file_path)
            except Exception as e:
                # Rollback if Step 2 fails
                if not os.path.exists(file_path) and os.path.exists(video_path):
                    try:
                        os.replace(video_path, file_path)
                    except Exception:
                        pass
                raise e
        except Exception as e:
            print(f"Error during in-place rename for {file_path}: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False

        final_path = file_path
    else:
        final_path = write_path

    try:
        out_size = os.path.getsize(final_path)
    except OSError:
        out_size = 0

    print(f"Done: {message_count:,} messages written, {stripped_count:,} video messages stripped.")
    if in_size > 0:
        reduction = ((in_size - out_size) / in_size) * 100
        print(f"Size: {in_size:,} bytes -> {out_size:,} bytes (reduced by {reduction:.1f}%)")
    else:
        print(f"Size: {out_size:,} bytes")

    return True


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="strip video in-place: original file renamed to <stem>_video.mcap, stripped file written to <stem>.mcap",
    )
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, ".mcap")

    for file in files:
        strip_video_from_mcap(file, in_place=args.in_place)


if __name__ == "__main__":
    main()
