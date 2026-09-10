import argparse
import json
import os
from datetime import datetime, timezone, tzinfo
from zoneinfo import ZoneInfo

import pymavlink.dialects.v20.ardupilotmega as apm

from file_reader import FileReader, FileReaderList, NamedReader, add_file_args


class SegmentFormatException(Exception):
    pass


class Segment:
    """
    A segment is a collection of messages where the start < timestamp < end.
    """

    def __init__(self, start: float, end: float, name: str | None = None):
        self.start = start
        self.end = end

        if name is None:
            # This will be used in a filename, so avoid adding dots
            name = f"{start:.0f}_{end:.0f}"

        self.name = name

    def __repr__(self):
        return "{" + f"start={self.start}, end={self.end}, name={self.name}" + "}"


class SegmentReader(NamedReader):
    """
    Iterate over messages in a segment. A segment may span several files.
    """

    def __init__(self, segment: Segment, file_reader: FileReader, file_readers: FileReaderList | None):
        super().__init__(build_segment_name(file_reader.name, segment.name))
        self._segment = segment
        self._file_reader = file_reader
        self._file_readers = file_readers

    def __iter__(self):
        return self

    def __next__(self) -> apm.MAVLink_message:
        while True:
            msg = None

            # Get the next message
            try:
                msg = next(self._file_reader)
            except StopIteration:
                # If we don't have a list of readers, we're done
                if self._file_readers is None:
                    raise StopIteration

                # Get the next file reader, this might raise StopIteration, we do not intercept
                self._file_reader = next(self._file_readers)

                # Try again
                continue

            timestamp = getattr(msg, "_timestamp", 0.0)

            # Ignore messages before the segment start
            if timestamp < self._segment.start:
                continue

            # Is the segment over?
            if timestamp > self._segment.end:
                raise StopIteration

            return msg


class SegmentReaderList:
    """
    Iterate over a list of segments.
    """

    def __init__(self, args, segments, types: list[str] | None, ext: str = ".tlog"):
        print(f"Reading {len(segments)} segment(s)")
        self._segments_iter = iter(segments)

        # Get a list of file readers, and prime the pump by getting the first file reader
        self._file_readers = FileReaderList(args, types, ext)
        next(self._file_readers)

    def __iter__(self):
        return self

    def __next__(self) -> SegmentReader:
        # Get the current file reader without advancing, and pass it to the next segment reader
        file_reader = self._file_readers.current()
        if file_reader is None:
            raise StopIteration

        return SegmentReader(next(self._segments_iter), file_reader, self._file_readers)


def add_segment_args(parser: argparse.ArgumentParser, ext: str = ".tlog"):
    """
    Add args for working with multiple files and multiple segments.
    """
    add_file_args(parser, ext)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-k",
        "--keep",
        default=None,
        action="append",
        help="process just these segments; a segment is 2 timestamps and a name, e.g., start,end,s1",
    )
    group.add_argument(
        "-s",
        "--segments",
        default=None,
        help="process segments specified in a JSON file or inline JSON string (compatible with utc_plan.json)",
    )
    group.add_argument("-a", "--all", default=None, action="store_true", help="keep all (combining all tlog files)")


def _resolve_tz(tz_val):
    if tz_val is None:
        return timezone.utc
    if isinstance(tz_val, str):
        tz_str = tz_val.strip()
        if tz_str.upper() in ("UTC", "Z"):
            return timezone.utc
        try:
            return ZoneInfo(tz_str)
        except Exception as e:
            raise SegmentFormatException(f"Unknown or invalid timezone: '{tz_val}'") from e
    if isinstance(tz_val, tzinfo):
        return tz_val
    raise SegmentFormatException(f"Invalid timezone type: {type(tz_val)}")


def parse_time_value(val, default_date: str | None = None, default_tz=None) -> float:
    """
    Parse a time value into a float epoch timestamp (seconds).
    Accepts:
      - float or int (epoch timestamp in seconds)
      - string of a float/int (epoch timestamp in seconds)
      - ISO-8601 string (e.g. "2026-09-02T09:25:23-07:00", "2026-09-02T16:25:23Z", or "2026-09-02 09:25:23")
      - Timecode string (e.g. "09:25:23" or "09:25:23.500"), combined with default_date and default_tz
    """
    if isinstance(val, (int, float)):
        return float(val)

    if not isinstance(val, str):
        raise SegmentFormatException(f"Expected time value as float, int, or string, got {type(val).__name__}")

    s = val.strip()
    if not s:
        raise SegmentFormatException("Time value is empty")

    # If it's a numeric string (e.g., "1788366323" or "1788366323.5")
    if ":" not in s and "-" not in s:
        try:
            return float(s)
        except ValueError:
            raise SegmentFormatException(f"Unrecognized numeric time value: '{s}'")

    # If it contains a date (indicated by '-')
    if "-" in s:
        try:
            s_iso = s.replace(" ", "T")
            dt = datetime.fromisoformat(s_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_resolve_tz(default_tz))
            return dt.timestamp()
        except ValueError as e:
            raise SegmentFormatException(f"Invalid ISO datetime string '{s}': {e}") from e

    # Otherwise, it is a timecode without date (e.g., "09:25:23")
    if default_date is None:
        raise SegmentFormatException(f"Date is required for timecode '{s}'")

    date_clean = default_date.strip().replace("/", "-")
    if s.count(":") == 1:
        s += ":00"

    try:
        dt = datetime.fromisoformat(f"{date_clean}T{s}")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_resolve_tz(default_tz))
        return dt.timestamp()
    except ValueError as e:
        raise SegmentFormatException(f"Invalid timecode '{s}' for date '{default_date}': {e}") from e


def parse_segment_json(json_content_or_path: str) -> list[Segment]:
    """
    Parse a segment JSON file or JSON string into a list of Segment objects.
    Compatible with utc_plan.json as well as simplified segment lists.
    """
    if not json_content_or_path or not json_content_or_path.strip():
        raise SegmentFormatException("Segment JSON input is empty")

    data = None
    if os.path.isfile(json_content_or_path):
        try:
            with open(json_content_or_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise SegmentFormatException(f"Failed to read JSON file '{json_content_or_path}': {e}") from e
    else:
        try:
            data = json.loads(json_content_or_path)
        except Exception as e:
            trimmed = json_content_or_path.strip()
            if not (trimmed.startswith("{") or trimmed.startswith("[")):
                raise SegmentFormatException(f"Segment file not found: '{json_content_or_path}'") from None
            raise SegmentFormatException(f"Failed to parse segment JSON: {e}") from e

    segments: list[Segment] = []

    if isinstance(data, dict):
        if "sites" in data:
            sites = data.get("sites")
            if not isinstance(sites, list):
                raise SegmentFormatException("'sites' must be a list in segment JSON")
            global_tz = data.get("timezone")
            global_date = data.get("date")
            multi_site = len(sites) > 1

            for site_idx, site in enumerate(sites):
                if not isinstance(site, dict):
                    raise SegmentFormatException(f"Site at index {site_idx} must be an object")
                site_name = site.get("name")
                site_date = site.get("date", global_date)
                site_tz = site.get("timezone", global_tz)
                transects = site.get("transects", [])
                if not isinstance(transects, list):
                    raise SegmentFormatException(f"'transects' must be a list in site '{site_name or site_idx}'")
                for t_idx, t in enumerate(transects):
                    if not isinstance(t, dict):
                        raise SegmentFormatException(
                            f"Transect at index {t_idx} in site '{site_name or site_idx}' must be an object"
                        )
                    t_name = t.get("name")
                    if multi_site and site_name:
                        seg_name = f"{site_name}_{t_name}" if t_name else f"{site_name}_{t_idx}"
                    else:
                        seg_name = t_name

                    start_raw = t.get("start") if "start" in t else t.get("start_tc")
                    end_raw = t.get("end") if "end" in t else t.get("end_tc")
                    if start_raw is None or end_raw is None:
                        raise SegmentFormatException(
                            f"Transect '{seg_name or t_idx}' missing start/end or start_tc/end_tc"
                        )
                    t_date = t.get("date", site_date)
                    t_tz = t.get("timezone", site_tz)
                    start_s = parse_time_value(start_raw, default_date=t_date, default_tz=t_tz)
                    end_s = parse_time_value(end_raw, default_date=t_date, default_tz=t_tz)
                    if start_s >= end_s:
                        raise SegmentFormatException(
                            f"Segment '{seg_name or t_idx}' start ({start_s}) must be strictly before end ({end_s})"
                        )
                    segments.append(Segment(start_s, end_s, seg_name))

        elif "segments" in data:
            seg_list = data.get("segments")
            if not isinstance(seg_list, list):
                raise SegmentFormatException("'segments' must be a list in segment JSON")
            global_tz = data.get("timezone")
            global_date = data.get("date")

            for s_idx, s in enumerate(seg_list):
                if not isinstance(s, dict):
                    raise SegmentFormatException(f"Segment at index {s_idx} must be an object")
                s_name = s.get("name")
                start_raw = s.get("start") if "start" in s else s.get("start_tc")
                end_raw = s.get("end") if "end" in s else s.get("end_tc")
                if start_raw is None or end_raw is None:
                    raise SegmentFormatException(f"Segment '{s_name or s_idx}' missing start/end or start_tc/end_tc")
                s_date = s.get("date", global_date)
                s_tz = s.get("timezone", global_tz)
                start_s = parse_time_value(start_raw, default_date=s_date, default_tz=s_tz)
                end_s = parse_time_value(end_raw, default_date=s_date, default_tz=s_tz)
                if start_s >= end_s:
                    raise SegmentFormatException(
                        f"Segment '{s_name or s_idx}' start ({start_s}) must be strictly before end ({end_s})"
                    )
                segments.append(Segment(start_s, end_s, s_name))

        else:
            raise SegmentFormatException("JSON object must contain either 'sites' or 'segments'")

    elif isinstance(data, list):
        for s_idx, s in enumerate(data):
            if not isinstance(s, dict):
                raise SegmentFormatException(f"Segment at index {s_idx} must be an object")
            s_name = s.get("name")
            start_raw = s.get("start") if "start" in s else s.get("start_tc")
            end_raw = s.get("end") if "end" in s else s.get("end_tc")
            if start_raw is None or end_raw is None:
                raise SegmentFormatException(f"Segment '{s_name or s_idx}' missing start/end or start_tc/end_tc")
            s_date = s.get("date")
            s_tz = s.get("timezone")
            start_s = parse_time_value(start_raw, default_date=s_date, default_tz=s_tz)
            end_s = parse_time_value(end_raw, default_date=s_date, default_tz=s_tz)
            if start_s >= end_s:
                raise SegmentFormatException(
                    f"Segment '{s_name or s_idx}' start ({start_s}) must be strictly before end ({end_s})"
                )
            segments.append(Segment(start_s, end_s, s_name))
    else:
        raise SegmentFormatException("JSON root must be an object or a list")

    if not segments:
        raise SegmentFormatException("No segments found in JSON specification")

    return segments


def parse_segment(segment_str: str) -> Segment:
    """
    Parse a --keep string and return a segment.
    """
    strs = segment_str.split(",")
    if len(strs) == 3:
        start_str, end_str, name = strs
    elif len(strs) == 2:
        start_str, end_str = strs
        name = None
    else:
        print(f'ERROR {segment_str} must be "start,end" or "start,end,name"')
        raise SegmentFormatException

    try:
        start = float(start_str)
    except ValueError:
        print(f"ERROR {start_str} must be a number")
        raise SegmentFormatException

    try:
        end = float(end_str)
    except ValueError:
        print(f"ERROR {end_str} must be a number")
        raise SegmentFormatException

    return Segment(start, end, name)


ALL_START = 0
ALL_END = 2552399285  # 2050 should be far enough


def parse_segment_args(args) -> list[Segment]:
    """
    Parse segment arguments (--all, --keep, --segments) and return a list of segments.
    """
    if getattr(args, "all", False):
        return [Segment(ALL_START, ALL_END, "all")]

    try:
        if getattr(args, "segments", None) is not None:
            return parse_segment_json(args.segments)

        results = []
        if getattr(args, "keep", None) is not None:
            for keep in args.keep:
                results.append(parse_segment(keep))
        return results
    except SegmentFormatException as e:
        if str(e):
            print(f"ERROR: {e}")
        exit(1)


def choose_reader_list(args, types: list[str] | None, ext: str = ".tlog"):
    """
    If there are segments return a SegmentReaderList, otherwise return a FileReaderList.
    """
    segments = parse_segment_args(args)
    if len(segments) > 0:
        return SegmentReaderList(args, segments, types, ext)
    else:
        return FileReaderList(args, types, ext)


def build_segment_name(first_path: str, segment_name: str):
    """
    Build a segment name from 2 parts:
    1. the directory part ('dirname') of the path of the 1st file in the list
    2. the segment name the user provided

    E.g., if the first file path for this segment is "./2023_09_15/foo.tlog" and the segment name is "transect1",
    the result is "./2023_09_15/transect1".
    """
    dirname, _ = os.path.split(first_path)
    return os.path.join(dirname, segment_name)
