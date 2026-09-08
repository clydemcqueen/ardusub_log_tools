#!/usr/bin/env python3

"""
Extract video stream(s) from one or more MCAP files and write to MP4 format.
"""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys

from mcap.reader import make_reader

import util


def is_video_channel(topic: str, schema_name: str | None) -> bool:
    """
    Determine if a channel contains video data based on its topic name or schema.
    """
    if topic.startswith("video/") or topic.startswith("/video/"):
        return True
    if schema_name:
        schema_lower = schema_name.lower()
        if "compressedvideo" in schema_lower:
            return True
    return False


def parse_compressed_video(
    payload: bytes, encoding: str, schema_name: str | None
) -> tuple[float | None, str, str, bytes]:
    """
    Parse a video message payload to extract (timestamp, frame_id, format, raw_video_bytes).
    Supports CDR-encoded foxglove.CompressedVideo, JSON, and raw Annex B bitstreams.
    """
    if encoding == "cdr" or (schema_name and "compressedvideo" in schema_name.lower() and len(payload) > 16):
        try:
            offset = 4  # Skip 4-byte CDR header
            sec, nsec = struct.unpack_from("<iI", payload, offset)
            offset += 8

            # frame_id
            str_len = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            frame_id = payload[offset : offset + str_len - 1].decode("utf-8", errors="replace") if str_len > 1 else ""
            offset += str_len
            if offset % 4 != 0:
                offset += 4 - (offset % 4)

            # data (uint8[])
            data_len = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            data = payload[offset : offset + data_len]
            offset += data_len
            if offset % 4 != 0:
                offset += 4 - (offset % 4)

            # format
            vformat = "h264"
            if offset + 4 <= len(payload):
                format_len = struct.unpack_from("<I", payload, offset)[0]
                offset += 4
                if format_len > 1 and offset + format_len - 1 <= len(payload):
                    vformat = payload[offset : offset + format_len - 1].decode("utf-8", errors="replace")

            ts = sec + nsec * 1e-9 if (sec != 0 or nsec != 0) else None
            return ts, frame_id, vformat.lower(), data
        except Exception:
            pass

    if encoding == "json":
        try:
            obj = json.loads(payload.decode("utf-8"))
            if isinstance(obj, dict):
                vformat = obj.get("format", "h264").lower()
                data_field = obj.get("data", b"")
                if isinstance(data_field, str):
                    import base64

                    data = base64.b64decode(data_field)
                elif isinstance(data_field, list):
                    data = bytes(data_field)
                else:
                    data = bytes(data_field)
                ts_dict = obj.get("timestamp", {})
                ts = ts_dict.get("sec", 0) + ts_dict.get("nsec", 0) * 1e-9 if ts_dict else None
                return ts, obj.get("frame_id", ""), vformat, data
        except Exception:
            pass

    # Fallback: check if payload itself is raw Annex B stream
    return None, "", "h264", payload


def clean_channel_suffix(topic: str) -> str:
    """Derive a concise file suffix from a video topic name."""
    clean = topic.strip("/").replace("/", "_")
    if clean.startswith("video_"):
        clean = clean[len("video_") :]
    if clean.endswith("_stream"):
        clean = clean[: -len("_stream")]
    return clean if clean else "video"


def extract_video_from_mcap(
    file_path: str,
    fps: float = 30.0,
    topic_filter: str | None = None,
    suffix: str | None = None,
    out_dir: str | None = None,
    verbose: bool = False,
) -> list[str]:
    """
    Extract video streams from an MCAP file and write to MP4 using ffmpeg.
    Returns a list of created MP4 file paths.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        print("Error: ffmpeg is required to extract video to MP4, but was not found in PATH.", file=sys.stderr)
        return []

    try:
        f_in = open(file_path, "rb")
    except OSError as e:
        print(f"Error opening {file_path}: {e}", file=sys.stderr)
        return []

    created_files = []
    with f_in:
        reader = make_reader(f_in)
        summary = reader.get_summary()

        video_channels = {}
        if summary and summary.channels:
            for ch_id, ch in summary.channels.items():
                schema = summary.schemas.get(ch.schema_id) if ch.schema_id else None
                schema_name = schema.name if schema else None
                if is_video_channel(ch.topic, schema_name):
                    if topic_filter and topic_filter not in ch.topic:
                        continue
                    video_channels[ch_id] = ch

        # If summary was not available or had no channels, scan headers
        if not video_channels and summary is None:
            # Will discover dynamically during iteration
            pass

        if summary and not video_channels:
            print(f"No matching video channels found in {file_path}")
            return []

        # Determine output file paths per channel
        # If single channel, use <basename><suffix>.mp4; if multiple, use <basename>_<stream><suffix>.mp4
        single_channel = len(video_channels) == 1
        writers = {}

        try:
            topics_to_read = [ch.topic for ch in video_channels.values()] if video_channels else None
            iter_kwargs = {"topics": topics_to_read} if topics_to_read else {}

            for schema, channel, message in reader.iter_messages(**iter_kwargs):
                schema_name = schema.name if schema else None
                if channel.id not in video_channels:
                    if not is_video_channel(channel.topic, schema_name):
                        continue
                    if topic_filter and topic_filter not in channel.topic:
                        continue
                    video_channels[channel.id] = channel

                if channel.id not in writers:
                    if single_channel:
                        file_suffix = f"_{suffix}" if suffix else "_video"
                    else:
                        stream_tag = clean_channel_suffix(channel.topic)
                        file_suffix = f"_{stream_tag}_{suffix}" if suffix else f"_{stream_tag}"

                    default_out_path = util.get_outfile_name(file_path, suffix=file_suffix, ext=".mp4")
                    if out_dir:
                        out_path = os.path.join(out_dir, os.path.basename(default_out_path))
                    else:
                        out_path = default_out_path

                    # Parse first message to detect format
                    _, _, vformat, raw_data = parse_compressed_video(
                        message.data, channel.message_encoding, schema_name
                    )
                    fmt_flag = "hevc" if "h265" in vformat or "hevc" in vformat else "h264"

                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-r",
                        str(fps),
                        "-f",
                        fmt_flag,
                        "-i",
                        "-",
                        "-c",
                        "copy",
                        out_path,
                    ]

                    if verbose:
                        print(f"  Starting ffmpeg for {channel.topic} -> {out_path}")
                        print(f"  Command: {' '.join(cmd)}")

                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE if not verbose else None,
                        stderr=subprocess.PIPE if not verbose else None,
                    )

                    writers[channel.id] = {
                        "proc": proc,
                        "out_path": out_path,
                        "topic": channel.topic,
                        "schema_name": schema_name,
                        "encoding": channel.message_encoding,
                        "frames": 0,
                        "bytes": 0,
                    }
                    created_files.append(out_path)

                w = writers[channel.id]
                _, _, _, raw_data = parse_compressed_video(message.data, w["encoding"], w["schema_name"])

                try:
                    w["proc"].stdin.write(raw_data)
                    w["frames"] += 1
                    w["bytes"] += len(raw_data)
                except BrokenPipeError:
                    print(f"Warning: ffmpeg process exited prematurely for {w['topic']}", file=sys.stderr)
                    break

        finally:
            for w in writers.values():
                proc = w["proc"]
                try:
                    stdout, stderr = proc.communicate()
                    if proc.returncode != 0:
                        err_msg = stderr.decode(errors="replace") if stderr else "Unknown error"
                        print(
                            f"Error: ffmpeg failed for {w['topic']} (code {proc.returncode}):\n{err_msg}",
                            file=sys.stderr,
                        )
                    else:
                        file_sz = os.path.getsize(w["out_path"]) if os.path.exists(w["out_path"]) else 0
                        duration_sec = w["frames"] / fps if fps > 0 else 0
                        duration_str = f"{int(duration_sec // 60)}m {duration_sec % 60:04.1f}s"
                        print(
                            f"  Wrote {w['frames']:,} frames to {w['out_path']} "
                            f"({file_sz / (1024 * 1024):.1f} MB, {duration_str} @ {fps:.1f} fps)"
                        )
                except Exception as e:
                    print(f"Error finalizing video {w['out_path']}: {e}", file=sys.stderr)

    return created_files


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for MCAP files")
    parser.add_argument("-v", "--verbose", action="store_true", help="print extra progress details")
    parser.add_argument("-f", "--fps", type=float, default=30.0, help="framerate of the output MP4 (default: 30.0)")
    parser.add_argument("-s", "--suffix", type=str, default=None, help="optional suffix for output file name")
    parser.add_argument("-o", "--out-dir", type=str, default=None, help="directory to place output MP4 files")
    parser.add_argument("-t", "--topic", type=str, default=None, help="filter for a specific video topic")
    args = parser.parse_args()

    files = util.expand_path(args.paths, args.recurse, ".mcap")
    print(f"Processing {len(files)} files")

    for file in files:
        print("-------------------")
        print(f"Reading {file}")
        try:
            extract_video_from_mcap(
                file,
                fps=args.fps,
                topic_filter=args.topic,
                suffix=args.suffix,
                out_dir=args.out_dir,
                verbose=args.verbose,
            )
        except Exception as e:
            print(f"Error processing {file}: {e}")


if __name__ == "__main__":
    main()
