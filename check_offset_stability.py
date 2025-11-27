#!/usr/bin/env python3

import argparse
import numpy as np
from pymavlink import mavutil

def check_offset_stability(tlog_path):
    print(f"Analyzing {tlog_path}")
    mlog = mavutil.mavlink_connection(tlog_path, robust_parsing=False)

    offsets = []
    first_offset = None

    while True:
        msg = mlog.recv_match(blocking=False)
        if msg is None:
            break

        if hasattr(msg, 'time_boot_ms'):
            # timestamp is in seconds, time_boot_ms is in ms
            # offset = unix_time - boot_time
            offset = getattr(msg, '_timestamp', 0) - msg.time_boot_ms / 1e3
            offsets.append(offset)
            
            if first_offset is None:
                first_offset = offset

    if not offsets:
        print("No messages with time_boot_ms found.")
        return

    offsets = np.array(offsets)
    
    print(f"Count: {len(offsets)}")
    print(f"First offset: {first_offset:.6f}")
    print(f"Min offset:   {offsets.min():.6f}")
    print(f"Max offset:   {offsets.max():.6f}")
    print(f"Mean offset:  {offsets.mean():.6f}")
    print(f"Std dev:      {offsets.std():.6f}")
    print(f"Range:        {offsets.max() - offsets.min():.6f}")
    
    # Check if first offset is significantly different from min
    diff = first_offset - offsets.min()
    print(f"First - Min:  {diff:.6f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tlog_path")
    args = parser.parse_args()
    check_offset_stability(args.tlog_path)
