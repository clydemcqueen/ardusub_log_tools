import argparse

import pymavlink.dialects.v20.ardupilotmega as apm
from pymavlink import mavutil

from util import expand_path


class NamedReader:
    def __init__(self, name: str):
        self.name = name


class FileReader(NamedReader):
    """
    Iterate over messages in a file.
    """

    def __init__(self, path: str, types: list[str] | None):
        super().__init__(path)
        self.count = 0
        self.first_ts = None
        self.last_ts = None
        self.types = types

        self._conn = mavutil.mavlink_connection(path, dialect='ardupilotmega')

        # Works for tlog, but not for BIN:
        # print(f'Reading {path}, WIRE_PROTOCOL_VERSION {self._conn.WIRE_PROTOCOL_VERSION}')

    def __iter__(self):
        return self

    def __next__(self) -> apm.MAVLink_message:
        msg = self._conn.recv_match(blocking=False, type=self.types)

        if msg is None:
            raise StopIteration
        else:
            self.count += 1
            self.last_ts = getattr(msg, '_timestamp', 0.0)
            if self.first_ts is None:
                self.first_ts = self.last_ts
            return msg


class FileReaderList:
    """
    Iterate over a list of file readers.
    """

    def __init__(self, args, types: list[str] | None):
        paths = expand_path(args.path, args.recurse, '.tlog')
        print(f'Reading {len(paths)} file(s)')
        self._types = types
        self._paths_iter = iter(paths)
        self._current = None

    def __iter__(self):
        return self

    def __next__(self) -> FileReader:
        self._current = FileReader(next(self._paths_iter), self._types)
        return self._current

    def current(self) -> FileReader | None:
        """
        Return the current reader w/o advancing, used by SegmentReaderList
        """
        return self._current


def add_file_args(parser: argparse.ArgumentParser):
    """
    Add args for working with multiple files.
    """
    parser.add_argument('-r', '--recurse', action='store_true', help='enter directories looking for files')
    parser.add_argument('path', nargs='+')
