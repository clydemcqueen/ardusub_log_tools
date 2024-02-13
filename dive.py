#!/usr/bin/env python3

"""
Read all BIN and tlog files in a directory and figure out how they line up.
"""

import argparse
import glob
import os

import file_reader
import util


class TelemetryLog:
    def __init__(self, reader):
        self._reader = reader

    def process(self, dive):
        for msg in self._reader:
            # Only consider messages from the autopilot
            if msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1:
                dive.note_time(self._reader.name, getattr(msg, '_timestamp', 0.0), msg.time_boot_ms)

    def report(self):
        print(f'>>> First {util.time_str(self._reader.first_ts)} ({self._reader.first_ts})')
        print(f'>>> Last {util.time_str(self._reader.last_ts)} ({self._reader.last_ts})')


class ExpectedDataflashLog:
    def __init__(self, name, ts, time_boot_s):
        self.name = name

        self.first_time_boot_s = time_boot_s
        self.first_ts = ts

        self.last_time_boot_s = time_boot_s
        self.last_ts = ts

    def report(self):
        print(f'>>> Reference {self.name}, first {self.first_time_boot_s :.2f}s, last {self.last_time_boot_s :.2f}s')


class DataflashLog:
    def __init__(self, reader):
        self._reader = reader

    def process(self):
        for _ in self._reader:
            pass

    def report(self):
        print(f'>>> First {self._reader.first_ts :.2f}s, last {self._reader.last_ts :.2f}s')


class DiveReaderList:
    """
    A variation on file_reader.FileReaderList
    """
    def __init__(self, dir_path: str, ext: str, types: list[str] | None):
        paths = sorted(glob.glob(dir_path + f'/*.{ext}'))
        self._types = types
        self._paths_iter = iter(paths)
        self._current = None

    def __iter__(self):
        return self

    def __next__(self) -> file_reader.FileReader:
        self._current = file_reader.FileReader(next(self._paths_iter), self._types)
        return self._current


class Dive:
    """
    A note on time:

    SYSTEM_TIME.time_boot_ms is the time-since-boot in ms. This comes from AP_HAL::millis(), which typically gets it
    from time::clock_gettime(CLOCK_MONOTONIC). I often seeing it start at around 100s, which I think means that it takes
    about 100s to fully boot the Pi, start BlueOS, and start ArduSub.

    SYSTEM_TIME.time_unix_usec is the Pi system clock is set by AP_RTC::get_utc_usec. If there is a GPS then this is the
    time from the GPS, otherwise it is always 0. This script does not use this field.

    The pymavlink message object contains a '_timestamp' attribute, measured in seconds.

    For telemetry log files, the timestamp attribute is the QGC system time, which is recorded in the tlog file just
    prior to the message.

    For dataflash logs, pymavlink looks ahead for or GPS or GPS2 message. If found, the GPS system time is used to
    initialize a clock object, which is used to estimate the system for each dataflash message.

    If there is no GPS or GPS2 message then the clock object is initialized with time_boot_ms, so the timestamp
    attribute is basically the same as time_boot_ms (in seconds), except that it is available for every message.

    In any case, we can use the timestamp attribute to find gaps in the MAVLink messages, which might indicate a reboot.

    Puzzle: SYSTEM_TIME.time_unix_usec seems to contain non-0 very early -- is pymavlink doing something magic here?
    """

    def __init__(self, dir_path: str):
        self._dir_path = dir_path
        self._ex_df_logs: list[ExpectedDataflashLog] = []   # BIN files seen by QGC

    def note_time(self, tlog_name, timestamp, time_boot_ms):
        """Build the list of expected dataflash logs."""
        time_boot_s = time_boot_ms / 1e3

        if len(self._ex_df_logs) == 0:
            print(f'>>> Bootstrap: expect dataflash log starting around {time_boot_s :.2f}s')
            self._ex_df_logs.append(ExpectedDataflashLog(tlog_name, timestamp, time_boot_s))
        elif timestamp > self._ex_df_logs[-1].last_ts + 5:
            print(f'>>> Gap at {self._ex_df_logs[-1].last_time_boot_s :.2f}s, expect dataflash log starting around {time_boot_s :.2f}s')
            self._ex_df_logs.append(ExpectedDataflashLog(tlog_name, timestamp, time_boot_s))
        elif time_boot_s < self._ex_df_logs[-1].last_time_boot_s:
            print(f'!!! Backwards at {self._ex_df_logs[-1].last_time_boot_s :.2f}s, expect dataflash log starting around {time_boot_s :.2f}s')
            self._ex_df_logs.append(ExpectedDataflashLog(tlog_name, timestamp, time_boot_s))
        else:
            self._ex_df_logs[-1].last_ts = timestamp
            self._ex_df_logs[-1].last_time_boot_s = time_boot_s

    def process_and_report(self):
        # SYSTEM_TIME is logged at a reasonable rate
        readers = DiveReaderList(self._dir_path, 'tlog', types=['SYSTEM_TIME'])
        for reader in readers:
            print(f'Reading {reader.name}')
            log = TelemetryLog(reader)
            log.process(self)
            log.report()
            print()

        print('Summary of expected dataflash logs:')
        for log in self._ex_df_logs:
            log.report()
        print()

        # MAV is always logged at 1 mps, so we get a good first and last timestamp
        readers = DiveReaderList(self._dir_path, 'BIN', types=['MAV'])
        for reader in readers:
            print(f'Reading {reader.name}')
            log = DataflashLog(reader)
            log.process()
            log.report()
            print()


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('path')
    args = parser.parse_args()

    if not os.path.isdir(args.path):
        print(f'{args.path} is not a directory!')
        return -1

    dive = Dive(args.path)
    dive.process_and_report()


if __name__ == '__main__':
    main()
