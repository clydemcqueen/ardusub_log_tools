import argparse
import os

import pymavlink.dialects.v20.ardupilotmega as apm

from file_reader import NamedReader, FileReader, FileReaderList, add_file_args


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
            name = f'{start :.0f}_{end :.0f}'

        self.name = name

    def __repr__(self):
        return '{' + f'start={self.start}, end={self.end}, name={self.name}' + '}'


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

            timestamp = getattr(msg, '_timestamp', 0.0)

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

    def __init__(self, args, segments, types: list[str] | None):
        print(f'Reading {len(segments)} segment(s)')
        self._segments_iter = iter(segments)

        # Get a list of file readers, and prime the pump by getting the first file reader
        self._file_readers = FileReaderList(args, types)
        next(self._file_readers)

    def __iter__(self):
        return self

    def __next__(self) -> SegmentReader:
        # Get the current file reader without advancing, and pass it to the next segment reader
        file_reader = self._file_readers.current()
        if file_reader is None:
            raise StopIteration

        return SegmentReader(next(self._segments_iter), file_reader, self._file_readers)


def add_segment_args(parser: argparse.ArgumentParser):
    """
    Add args for working with multiple files and multiple segments.
    """
    add_file_args(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-k', '--keep', default=None, action='append',
                       help='process just these segments; a segment is 2 timestamps and a name, e.g., start,end,s1')
    group.add_argument('-a', '--all', default=None, action='store_true',
                       help='keep all (combining all tlog files)')


def parse_segment(segment_str: str) -> Segment:
    """
    Parse a --keep string and return a segment.
    """
    strs = segment_str.split(',')
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
        print(f'ERROR {start_str} must be a number')
        raise SegmentFormatException

    try:
        end = float(end_str)
    except ValueError:
        print(f'ERROR {end_str} must be a number')
        raise SegmentFormatException

    return Segment(start, end, name)


ALL_START = 0
ALL_END = 2552399285  # 2050 should be far enough


def parse_segment_args(args) -> list[Segment]:
    """
    Parse segment arguments (--all, --keep) and return a list of segments.
    """
    if args.all:
        return [Segment(ALL_START, ALL_END, 'all')]

    try:
        results = []
        if args.keep is not None:
            for keep in args.keep:
                results.append(parse_segment(keep))
        return results
    except SegmentFormatException:
        exit(1)


def choose_reader_list(args, types):
    """
    If there are segments return a SegmentReaderList, otherwise return a FileReaderList.
    """
    segments = parse_segment_args(args)
    if len(segments) > 0:
        return SegmentReaderList(args, segments, types)
    else:
        return FileReaderList(args, types)


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
