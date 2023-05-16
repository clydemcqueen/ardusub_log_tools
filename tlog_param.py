#!/usr/bin/env python3

"""
Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log), reconstruct the parameter state of a vehicle, and
write the parameters to a QGC-compatible params file.
"""

import os
from argparse import ArgumentParser
from typing import NamedTuple

import pymavlink.dialects.v20.common as mav_common
from pymavlink import mavutil

import util

# Use MAVLink2
os.environ['MAVLINK20'] = '1'


def firmware_version_type_str(firmware_version_type: int) -> str:
    if firmware_version_type == mav_common.FIRMWARE_VERSION_TYPE_DEV:
        return 'dev'
    elif firmware_version_type == mav_common.FIRMWARE_VERSION_TYPE_ALPHA:
        return 'alpha'
    elif firmware_version_type == mav_common.FIRMWARE_VERSION_TYPE_BETA:
        return 'beta'
    elif firmware_version_type == mav_common.FIRMWARE_VERSION_TYPE_RC:
        return 'rc'
    else:
        return ''


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

        while (msg := mlog.recv_match(blocking=False, type=['PARAM_VALUE', 'AUTOPILOT_VERSION'])) is not None:
            data = msg.to_dict()
            if msg.get_type() == 'PARAM_VALUE':
                param_id = data['param_id']
                param_value = data['param_value']

                if param_id in self.params and self.params[param_id].value != param_value:
                    print(f'{param_id} was {self.params[param_id].value}, changed to {param_value}')

                self.params[param_id] = Param(param_value, data['param_type'])
            else:
                flight_sw_version = data['flight_sw_version']
                major = (flight_sw_version >> (8 * 3)) & 0xFF
                minor = (flight_sw_version >> (8 * 2)) & 0xFF
                path = (flight_sw_version >> (8 * 1)) & 0xFF
                version_type = (flight_sw_version >> (8 * 0)) & 0xFF

                self.autopilot_version = f'{major}.{minor}.{path} {firmware_version_type_str(version_type)}'
                self.git_hash = bytes(data['flight_custom_version']).decode('utf-8')

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
        f.write(f'# Version: {self.autopilot_version}\n')
        f.write(f'# Git Revision: {self.git_hash}\n')
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
