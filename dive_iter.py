#!/usr/bin/env python3

"""
TODO add a description
"""

import argparse

from pymavlink import mavutil

import util


class DiveIterator:
    """
    Merge an overlapping tlog file and BIN file.

    Usage:
        dive_iter = DiveIterator(tlog_path, bin_path)
        while msg := next(dive_iter):
            print(msg)
    """
    def __init__(self, tlog_path: str, bin_path: str):
        self.tlog_path = tlog_path
        self.bin_path = bin_path
        
        # The next message to return from each file
        self._next_tlog = None
        self._next_bin = None

        # Open both files
        self._tlog_conn = mavutil.mavlink_connection(tlog_path)
        self._bin_conn = mavutil.mavlink_connection(bin_path)

        # Find the first offset between Unix time and time-since-boot
        self.rtc_shift = util.get_rtc_shift(self._tlog_conn, rewind=True)

        if self.rtc_shift is None:
            raise ValueError("The tlog file is empty or has no messages with a time_boot_ms field")

        # Get the first message from each file
        tlog_msg = self._tlog_conn.recv_match(blocking=False)
        bin_msg = self._bin_conn.recv_match(blocking=False)

        if not bin_msg:
             raise ValueError("The BIN file is empty or has no messages with a TimeUS field")

        # Get the timestamps
        tlog_timestamp = getattr(tlog_msg, '_timestamp', 0)
        bin_timestamp = getattr(bin_msg, '_timestamp', 0) + self.rtc_shift

        # Pick the start of the overlap
        overlap_start = max(tlog_timestamp, bin_timestamp)
        print(f"tlog start {tlog_timestamp}, BIN start {bin_timestamp}, overlap start {overlap_start}")

        # Rewind both files
        self._tlog_conn.rewind()
        self._bin_conn.rewind()

        # Seek both files, leaving _next_tlog and _next_bin pointing to the first messages in the overlap region
        self._seek_tlog(overlap_start)
        self._seek_bin(overlap_start)

        # If either seek failed, then the files do not overlap
        if self._next_tlog is None or self._next_bin is None:
            raise ValueError("The files do not overlap")

    def _seek_tlog(self, target):
        while True:
            msg = self._tlog_conn.recv_match(blocking=False)
            if msg is None:
                self._next_tlog = None
                return
            if  getattr(msg, '_timestamp', 0) >= target:
                self._next_tlog = msg
                return
    
    def _seek_bin(self, target):
        while True:
            msg = self._bin_conn.recv_match(blocking=False)
            if msg is None:
                self._next_bin = None
                return
            if  getattr(msg, '_timestamp', 0) + self.rtc_shift >= target:
                self._next_bin = msg
                return

    def __iter__(self):
        return self

    def __next__(self):
        # Stop iteration if EITHER file ends (intersection only)
        if self._next_tlog is None or self._next_bin is None:
            raise StopIteration
            
        tlog_timestamp = getattr(self._next_tlog, '_timestamp', 0)
        bin_timestamp = getattr(self._next_bin, '_timestamp', 0) + self.rtc_shift

        # Compare timestamps
        if tlog_timestamp <= bin_timestamp:
            msg = self._next_tlog
            self._next_tlog = self._tlog_conn.recv_match(blocking=False)
            return msg
        else:
            msg = self._next_bin
            self._next_bin = self._bin_conn.recv_match(blocking=False)

            # Adjust the BIN message timestamp
            setattr(msg, '_timestamp', bin_timestamp)
            return msg


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('--count', type=int, default=20, help='number of messages to print')
    parser.add_argument('tlog_path')
    parser.add_argument('bin_path')
    args = parser.parse_args()

    try:
        dive_iter = DiveIterator(args.tlog_path, args.bin_path)

        count = 0
        while msg := next(dive_iter):
            print(f"{getattr(msg, '_timestamp', 0.0):.3f} {msg.get_type():30}")
            count += 1
            if count >= args.count:
                break

    except ValueError as e:
        print(f"ERROR: {e}")

    except StopIteration:
        pass


if __name__ == '__main__':
    main()
