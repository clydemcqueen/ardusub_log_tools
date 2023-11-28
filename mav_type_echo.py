#!/usr/bin/env python3

"""
Connect to a running MAVLink system and echo a message type.
"""

import argparse
import os
import time

from pymavlink.dialects.v20 import ardupilotmega as apm2

# Use MAVLink2 wire protocol, must include this before importing pymavlink.mavutil
os.environ['MAVLINK20'] = '1'

# Late import
from pymavlink import mavutil


def type_echo(types: list[str]):
    # Be a good citizen and send HEARTBEAT messages at 1Hz
    heartbeat_msg = apm2.MAVLink_heartbeat_message(apm2.MAV_TYPE_GCS, apm2.MAV_AUTOPILOT_INVALID, 0, 0, 0, 3)

    # Connect to BlueOS
    conn = mavutil.mavlink_connection('udpout:192.168.2.2:14550', source_system=250, source_component=99)

    try:
        print('hit ctrl-C to quit')
        count = 0
        while True:
            if count % 10 == 0:
                conn.mav.send(heartbeat_msg)

            while (msg := conn.recv_match(type=types, blocking=False)) is not None:
                print(msg.to_dict())

            time.sleep(0.1)
            count += 1

    except KeyboardInterrupt:
        print('interrupt, quitting')
    except Exception as e:
        print(f'random exception: {e}')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('type', nargs='+')
    args = parser.parse_args()
    type_echo(args.type)


if __name__ == '__main__':
    main()
