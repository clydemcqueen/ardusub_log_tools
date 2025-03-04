#!/usr/bin/env python3

"""
Read messages from tlog (telemetry) and BIN (dataflash) logs and report on the message types found.
"""

import os

# Force WIRE_PROTOCOL_VERSION to be 2.0 to get the names of the messages with id > 255
os.environ['MAVLINK20'] = '1'

from argparse import ArgumentParser

from pymavlink import mavutil

import util


# Everything I've ever seen in a dataflash (.BIN) file
# My comments in [], the rest is from https://ardupilot.org/copter/docs/logmessages.html
DATAFLASH_DESC = {
    'AHR2': 'Backup AHRS data',
    'ARM': 'Arming status changes',
    'ARSP': 'Airspeed sensor data',
    'ATSC': 'Scale factors for attitude controller',
    'ATT': 'Canonical vehicle attitude',
    'BARO': 'Gathered Barometer data',
    'BAT': 'Gathered battery data',
    'CTRL': 'Attitude Control oscillation monitor diagnostics',
    'CTUN': 'Control Tuning information',
    'DSF': 'Onboard logging statistics',
    'DU32': 'Generic 32-bit-unsigned-integer storage',
    'ERR': 'Specifically coded error messages',
    'EV': 'Specifically coded event messages',
    'FILE': '[TODO -- what is this?]',
    'FMT': 'Message defining the format of messages in this file',
    'FMTU': 'Message defining units and multipliers used for fields of other messages',
    'FTN': 'Filter Tuning Message - per motor',
    'GPA': 'GPS accuracy information',
    'GPS': 'Information received from GNSS systems attached to the autopilot',
    'GUIP': 'Guided mode target information',
    'IMU': 'Inertial Measurement Unit data',
    'MAG': 'Information received from compasses',
    'MAV': 'GCS MAVLink link statistics',
    'MAVC': 'MAVLink command we have just executed',
    'MODE': 'vehicle control mode information',
    'MOTB': 'Motor mixer information',
    'MSG': 'Textual messages',
    'MULT': 'Message mapping from single character to numeric multiplier',
    'ORGN': 'Vehicle navigation origin or other notable position',
    'PARM': 'parameter value',
    'PIDA': 'Proportional/Integral/Derivative gain values for Altitude',
    'PIDP': 'Proportional/Integral/Derivative gain values for Pitch',
    'PIDR': 'Proportional/Integral/Derivative gain values for Roll',
    'PIDY': 'Proportional/Integral/Derivative gain values for Yaw',
    'PM': 'autopilot system performance and general data dumping ground',
    'POS': 'Canonical vehicle position [lat/lon/alt]',
    'PSCD': 'Position Control Down',
    'PSCE': 'Position Control East',
    'PSCN': 'Position Control North',
    'PSOD': 'Position Control Offsets Down',
    'PSOT': 'Position Control Offsets Terrain (Down)',
    'RATE': 'Desired and achieved vehicle attitude rates. Not logged in Fixed Wing Plane modes.',
    'RCI2': '(More) RC input channels to vehicle',
    'RCIN': 'RC input channels to vehicle',
    'RCO2': 'Servo channel output values 15 to 18',
    'RCOU': 'Servo channel output values 1 to 14',
    'RFND': 'Rangefinder sensor information',
    'SIM': 'SITL simulator state [rpy, lat/lon/alt, quat]',
    'SIM2': 'Additional simulator state [pos from home, vel]',
    'UNIT': 'Message mapping from single character to SI unit',
    'VER': '[TODO -- what is this?]',
    'VIBE': 'Processed (acceleration) vibration information',
    'VISO': 'Visual odometry, e.g., from a DVL',
    'XKF1': 'EKF3 estimator outputs',
    'XKF2': 'EKF3 estimator secondary outputs',
    'XKF3': 'EKF3 innovations',
    'XKF4': 'EKF3 variances',
    'XKF5': 'EKF3 Sensor innovations (primary core) and general dumping ground',
    'XKFD': 'EKF3 Body Frame Odometry errors',
    'XKFS': 'EKF3 sensor selection',
    'XKQ': 'EKF3 quaternion defining the rotation from NED to XYZ (autopilot) axes',
    'XKT': 'EKF3 timing information',
    'XKTV': 'EKF3 Yaw Estimator States',
    'XKV1': 'EKF3 State variances (primary core)',
    'XKV2': 'more EKF3 State Variances (primary core)',
    'XKY0': 'EKF Yaw Estimator States',
    'XKY1': 'EKF Yaw Estimator Innovations',

    # Replay, considered a "black box":
    'RBOH':  'Replay body odometry data',
    'RBRH':  'Replay Data Barometer Header',
    'RBRI':  'Replay Data Barometer Instance',
    'RFRF':  'Replay FRame data - Finished frame',
    'RFRH':  'Replay FRame Header',
    'RFRN':  'Replay FRame - aNother frame header',
    'RGPH':  'Replay Data GPS Header',
    'RGPI':  'Replay Data GPS Instance, infrequently changing data',
    'RGPJ':  'Replay Data GPS Instance - rapidly changing data',
    'RISH':  'Replay Inertial Sensor header',
    'RISI':  'Replay Inertial Sensor instance data',
    'RMGH':  'Replay Data Magnetometer Header',
    'RMGI':  'Replay Data Magnetometer Instance',
    'RRNH':  'Replay Data Rangefinder Header',
    'RRNI':  'Replay Data Rangefinder Instance',
    'RVOH':  'Replay Data Visual Odometry data',
}


def rate_str(count, tn, t0) -> str:
    if t0 >= tn:
        return ' N/A'
    else:
        rate = round(count / (tn - t0))
        if rate > 1000:
            # Some messages all come at once
            return 'HIGH'
        else:
            return f'{rate:4d}'


class TypeFinder:
    def __init__(self, filename: str):
        self.filename = filename
        self.is_dataflash = filename.endswith('.BIN')

    def read(self):
        mlog = mavutil.mavlink_connection(self.filename, dialect='ardupilotmega')

        msg_count = {}  # Count
        msg_t0 = {}     # First timestamp
        msg_tn = {}     # Last timestamp

        # Don't crash reading a corrupt file
        try:
            while True:
                msg = mlog.recv_match(blocking=False)
                if msg is None:
                    break

                msg_type = msg.get_type()
                if msg_type not in msg_count.keys():
                    msg_count[msg_type] = 1
                    msg_tn[msg_type] = msg_t0[msg_type] = getattr(msg, '_timestamp', 0)
                else:
                    msg_count[msg_type] += 1
                    msg_tn[msg_type] = getattr(msg, '_timestamp', 0)

        except Exception as e:
            print(f'CRASH WITH ERROR "{e}", SHOWING PARTIAL RESULTS')

        if self.is_dataflash:
            print(' COUNT  RATE  TYPE  DESCRIPTION')
        else:
            print('TYPE                                  COUNT  RATE')

        for msg_type, msg_count in sorted(msg_count.items()):
            rate = rate_str(msg_count, msg_tn[msg_type], msg_t0[msg_type])
            if self.is_dataflash:
                msg_desc = DATAFLASH_DESC[msg_type] if msg_type in DATAFLASH_DESC else 'TODO -- update tool'
                print(f'{msg_count:6d}  {rate}  {msg_type:4}  {msg_desc:82}')
            else:
                print(f'{msg_type:35}  {msg_count:6d}  {rate}')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true', help='enter directories looking for tlog and BIN files')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, ['.tlog', '.BIN'])
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        print(f'Reading {file}')
        scanner = TypeFinder(file)
        scanner.read()


if __name__ == '__main__':
    main()
