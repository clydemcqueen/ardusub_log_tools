#!/usr/bin/env python3

"""
Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log), reconstruct the parameter state of a vehicle, and
write the parameters to a QGC-compatible params file.
"""
import os
import time
from argparse import ArgumentParser

import numpy as np
import pymavlink.dialects.v20.common as mav_common
from pymavlink import mavutil

import util

# These parameters change all the time, so changes are uninteresting
NOISY_PARAMS: list[str] = ['BARO1_GND_PRESS', 'BARO2_GND_PRESS', 'STAT_FLTTIME', 'STAT_RUNTIME']

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


def is_int(param_type: int) -> bool:
    return mav_common.MAV_PARAM_TYPE_UINT8 <= param_type <= mav_common.MAV_PARAM_TYPE_INT64


class Param:
    def __init__(self, msg: mav_common.MAVLink_param_value_message):
        self.id = msg.param_id
        self.value = msg.param_value
        self.type = msg.param_type
        timestamp = getattr(msg, '_timestamp', 0.0)
        self.when = f'[{timestamp :.3f}] {time.asctime(time.localtime(timestamp))}'

    def is_int(self) -> bool:
        return is_int(self.type)

    def value_int(self) -> int:
        if self.is_int():
            return int(self.value)
        else:
            print(f'ERROR: {self.id} has type {self.type}, will try to convert {self.value} to int')
            try:
                return int(self.value)
            finally:
                return 0

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


def print_change(old_param: Param | None, new_param: Param | None):
    """
    Note the change
    """
    param_id = new_param.id if new_param else old_param.id
    if param_id in NOISY_PARAMS:
        return

    param_type = new_param.type if new_param else old_param.type
    param_when = new_param.when if new_param else 'REMOVED'

    if is_int(param_type):
        old_param_str = f'{old_param.value_int()}' if old_param else 'ADDED'
        new_param_str = f'{new_param.value_int()}' if new_param else ''
    else:
        old_param_str = f'{old_param.value :.6f}' if old_param else 'ADDED'
        new_param_str = f'{new_param.value :.6f}' if new_param else ''

    print(f'{param_when} {param_id :18s} {old_param_str} -> {new_param_str}')


class TelemetryLogParam:
    def __init__(self, infile: str, print_intra_file_changes):
        self.infile = infile
        self.params: dict[str, Param] = {}
        self.autopilot_version: str = ''
        self.git_hash: str = ''
        mlog = mavutil.mavlink_connection(infile, robust_parsing=False, dialect='ardupilotmega')

        while (msg := mlog.recv_match(blocking=False, type=['PARAM_VALUE', 'PARAM_SET', 'AUTOPILOT_VERSION'])) is not None:
            if msg.get_type() == 'PARAM_VALUE':
                self.handle_param_value(msg, print_intra_file_changes)
            elif msg.get_type() == 'PARAM_SET':
                self.handle_param_set(msg)
            else:
                self.handle_version(msg)

    def handle_param_value(self, msg: mav_common.MAVLink_param_value_message, print_intra_file_changes: bool):
        new_param = Param(msg)

        if new_param.id in self.params:
            old_param = self.params[new_param.id]

            if print_intra_file_changes and new_param.type != old_param.type:
                print(f'ERROR: {old_param.id} type changed from {old_param.type} to {new_param.type}')

            if new_param.value != old_param.value:
                if print_intra_file_changes:
                    print_change(old_param, new_param)

                # Update the value (not the type)
                old_param.value = new_param.value
        else:
            # Add the param to the dict
            self.params[new_param.id] = new_param

    def handle_param_set(self, msg: mav_common.MAVLink_param_set_message):
        print(f'PARAM_SET ({msg.get_srcSystem()}, {msg.get_srcComponent()}) -> ({msg.target_system}, {msg.target_component}), param {msg.param_id}, new value {msg.param_value}')

    def handle_version(self, msg: mav_common.MAVLink_autopilot_version_message):
        flight_sw_version = msg.flight_sw_version
        major = (flight_sw_version >> (8 * 3)) & 0xFF
        minor = (flight_sw_version >> (8 * 2)) & 0xFF
        path = (flight_sw_version >> (8 * 1)) & 0xFF
        version_type = (flight_sw_version >> (8 * 0)) & 0xFF

        self.autopilot_version = f'{major}.{minor}.{path} {firmware_version_type_str(version_type)}'
        self.git_hash = bytes(msg.flight_custom_version).decode('utf-8')

    def write_params_file(self, outfile: str):
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


def print_changes(previous_file: TelemetryLogParam, current_file: TelemetryLogParam):
    """
    Compare to a previous tlog file
    """
    if not len(previous_file.params) or not len(current_file.params):
        print('Nothing to compare')
        return

    # Print UNSET -> param and param -> param
    for _, param in sorted(current_file.params.items()):
        if param.id not in previous_file.params:
            print_change(None, param)
        elif param.value != previous_file.params[param.id].value:
            print_change(previous_file.params[param.id], param)

    # Print param -> UNSET
    for _, param in sorted(previous_file.params.items()):
        if param.id not in current_file.params:
            print_change(param, None)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse',
                        help='enter directories looking for tlog files',
                        action='store_true')
    parser.add_argument('-c', '--changes',
                        help='only show changes across files, do not write *.params files',
                        action='store_true')
    parser.add_argument('-s', '--skip',
                        help='skip one or more files, comma separated list of filenames',
                        type=str, default='')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')
    skip = args.skip.split(',')

    previous_file = None
    for infile in files:
        print('-------------------')
        _, basename = os.path.split(infile)

        if basename in skip:
            print(f'Skipping: {infile}')
            continue

        # The BlueOS file names have a prefix which screws up the sort order, drop for now
        if args.changes and basename[5] == '-':
            print(f'Skipping BlueOS-generated tlog: {infile}')
            continue

        print(f'Reading {infile}')
        current_file = TelemetryLogParam(infile, not args.changes)

        # If --changes is True, then print changes between files, but not changes w/in files
        if args.changes:
            if previous_file is not None:
                print_changes(previous_file, current_file)
            previous_file = current_file
        else:
            current_file.write_params_file(util.get_outfile_name(infile, ext='.params'))


if __name__ == '__main__':
    main()
