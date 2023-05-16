#!/usr/bin/env python3

"""
Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log), reconstruct the parameter state of a vehicle, and
write the parameters to a QGC-compatible params file.
"""

from argparse import ArgumentParser
import os
from pymavlink import mavutil
from typing import NamedTuple
import util

# Use MAVLink2
os.environ['MAVLINK20'] = '1'


class Param(NamedTuple):
    value: str
    type: str   # Actual values are MAV_PARAM_TYPE_*, but we'll store them as strings


class ParamState:
    def __init__(self):
        self.params: dict[str, Param] = {}
        self.autopilot_version: str = ''
        self.git_hash: str = ''

    def read(self, infile: str):
        mlog = mavutil.mavlink_connection(infile, robust_parsing=False, dialect='ardupilotmega')

        while (msg := mlog.recv_match(blocking=False, type=['PARAM_VALUE'])) is not None:
            data = msg.to_dict()
            param_id = data['param_id']
            param_value = data['param_value']

            if param_id in self.params and self.params[param_id].value != param_value:
                print(f'{param_id} was {self.params[param_id].value}, changed to {param_value}')

            self.params[param_id] = Param(param_value, data['param_type'])

    # TODO write ArduSub version #
    # TODO write ArduSub git revision #

    def write(self, outfile: str):
        """
        Write a QGC-compatible params file

        File format: https://dev.qgroundcontrol.com/master/en/file_formats/parameters.html
        """
        if len(self.params) == 0:
            print('Nothing to write')
            return

        print(f'Writing {outfile}')
        f = open(outfile, 'w')

        f.write('# Onboard parameters for Vehicle 1\n')
        f.write('#\n')
        f.write('# Stack: ArduPilot\n')
        f.write('# Vehicle: Sub\n')
        f.write('# Version: TODO \n')
        f.write('# Git Revision: TODO\n')
        f.write('#\n')
        f.write('# Vehicle-Id\tComponent-Id\tName\tValue\tType\n')

        for pi in sorted(self.params.items()):
            f.write(f'1\t1\t{pi[0]}\t{pi[1].value}\t{pi[1].type}\n')

        f.close()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for tlog files', action='store_true')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')

    for infile in files:
        print('-------------------')
        print(infile)
        dirname, basename = os.path.split(infile)
        root, ext = os.path.splitext(basename)
        outfile = os.path.join(dirname, root + '.params')

        param_state = ParamState()
        param_state.read(infile)
        param_state.write(outfile)


if __name__ == '__main__':
    main()
