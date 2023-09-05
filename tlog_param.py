#!/usr/bin/env python3

"""
Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log), reconstruct the parameter state of a vehicle, and
write the parameters to a QGC-compatible params file.
"""

import os
from argparse import ArgumentParser

import numpy as np
import pymavlink.dialects.v20.common as mav_common
from pymavlink import mavutil

import util

EK3_SRCn_POSXY = {
    0: 'None',
    3: 'GPS',
    4: 'Beacon',
    6: 'ExternalNav',
}

EK3_SRCn_VELXY = {
    0: 'None',
    3: 'GPS',
    4: 'Beacon',
    5: 'OpticalFlow',
    6: 'ExternalNav',
    7: 'WheelEncoder',
}

EK3_SRCn_POSZ = {
    0: 'None',
    1: 'Baro',
    2: 'RangeFinder',
    3: 'GPS',
    4: 'Beacon',
    6: 'ExternalNav',
}

EK3_SRCn_VELZ = {
    0: 'None',
    3: 'GPS',
    4: 'Beacon',
    6: 'ExternalNav',
}

EK3_SRCn_YAW = {
    0: 'None',
    1: 'Compass',
    2: 'GPS',
    3: 'GPS with Compass Fallback',
    6: 'ExternalNav',
    8: 'GSF',
}


def firmware_version_type_str(firmware_version_type: int) -> str:
    try:
        return mav_common.enums['FIRMWARE_VERSION_TYPE'][firmware_version_type].description

    except KeyError:
        pass

    return ''


class Param:
    def __init__(self, param_id: str, param_value: float, value_type: int):
        self.id = param_id
        self.value = param_value
        self.type = value_type

    def value_int(self) -> int:
        if self.type < 1 or self.type > 8:
            print(f'ERROR: {self.id} has type {self.type}, will try to convert {self.value} to int')
            try:
                return int(self.value)
            finally:
                return 0

        return int(self.value)

    def value_str(self) -> str:
        if self.type is mav_common.MAV_PARAM_TYPE_REAL32:
            return str(np.float32(self.value))
        elif self.type is mav_common.MAV_PARAM_TYPE_REAL64:
            return str(self.value)
        else:
            return str(int(self.value))

    def comment(self) -> str | None:
        if self.id.startswith('EK3_SRC'):
            if self.id.endswith('POSXY'):
                return EK3_SRCn_POSXY[self.value_int()]
            elif self.id.endswith('VELXY'):
                return EK3_SRCn_VELXY[self.value_int()]
            elif self.id.endswith('POSZ'):
                return EK3_SRCn_POSZ[self.value_int()]
            elif self.id.endswith('VELZ'):
                return EK3_SRCn_VELZ[self.value_int()]
            elif self.id.endswith('YAW'):
                return EK3_SRCn_YAW[self.value_int()]
            elif self.id == 'EK3_SRC_OPTIONS':
                return 'FuseAllVelocities' if self.value_int() == 1 else 'None'
        return None


class TelemetryLogParam:
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

                self.params[param_id] = Param(param_id, param_value, data['param_type'])
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
        if not len(self.params):
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

        for _, param in sorted(self.params.items()):
            comment = param.comment()
            if comment is not None:
                f.write(f'1\t1\t{param.id}\t{param.value_str()}\t{param.type}\t# {comment}\n')
            else:
                f.write(f'1\t1\t{param.id}\t{param.value_str()}\t{param.type}\n')

        f.close()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for tlog files', action='store_true')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')

    for infile in files:
        print('-------------------')
        print(infile)
        dirname, basename = os.path.split(infile)
        root, ext = os.path.splitext(basename)
        outfile = os.path.join(dirname, root + '.params')

        tlog_param = TelemetryLogParam()
        tlog_param.read(infile)
        tlog_param.write(outfile)


if __name__ == '__main__':
    main()
