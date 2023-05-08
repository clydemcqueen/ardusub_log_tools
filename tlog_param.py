#!/usr/bin/env python3

"""
Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log) and use these to reconstruct the parameter state of a vehicle.
"""

from argparse import ArgumentParser
import os
from pymavlink import mavutil
import util

# Use MAVLink2
os.environ['MAVLINK20'] = '1'


class TelemetryLogParam:
    def __init__(self, tlog_filename: str):
        self.tlog_filename = tlog_filename

    def read_and_report(self):
        print(f'Results for {self.tlog_filename}')
        mlog = mavutil.mavlink_connection(self.tlog_filename, robust_parsing=False, dialect='ardupilotmega')

        params = {}
        while (msg := mlog.recv_match(blocking=False, type=['PARAM_VALUE'])) is not None:
            data = msg.to_dict()
            params[data['param_id']] = data['param_value']

        # Print results
        for pi in sorted(params.items()):
            print(f'{pi[0]} = {pi[1]}')


# TODO save to a params file that QGC can read & use
# TODO also save to csv file
# TODO report interesting info as well, e.g., did params get overridden?

def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for tlog files', action='store_true')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        tlog_param = TelemetryLogParam(file)
        tlog_param.read_and_report()


if __name__ == '__main__':
    main()
