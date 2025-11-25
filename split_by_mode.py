#!/usr/bin/env python3

"""
Split ArduSub log files (tlog and BIN) into separate files based on flight modes.
"""

import argparse
import os
import struct
from pymavlink import mavutil

# Force MAVLink 2.0
os.environ['MAVLINK20'] = '1'

# Custom mode definitions
SURFTRAK_MODE = 21
CUSTOM_MODES = {
    'SURFTRAK': SURFTRAK_MODE,
}

def get_mode_mapping():
    """
    Return a dictionary mapping mode names to mode numbers.
    """
    mapping = {}
    
    # Add standard ArduSub modes
    if hasattr(mavutil, 'mode_mapping_sub'):
        # mavutil.mode_mapping_sub is int -> str
        for num, name in mavutil.mode_mapping_sub.items():
            mapping[name] = num
        
    # Add custom modes
    mapping.update(CUSTOM_MODES)
    
    return mapping

def get_mode_name(mode_num, mapping):
    """
    Get mode name from number.
    """
    # mapping is name -> number
    for name, num in mapping.items():
        if num == mode_num:
            return name
    return f"MODE{mode_num}"

def process_bin(input_file, requested_modes):
    """
    Split a BIN file by mode.
    """
    print(f"Processing BIN file: {input_file}")
    
    mlog = mavutil.mavlink_connection(input_file, robust_parsing=False, dialect='ardupilotmega')
    
    fmt_msgs = []
    current_mode = None
    segment_count = {} # mode_name -> count
    
    # We need to buffer messages for the current segment
    # Writing directly to file is better if we can open/close on the fly
    
    outfile = None
    outfile_name = None
    
    mapping = get_mode_mapping()
    
    while True:
        msg = mlog.recv_match(blocking=False)
        if msg is None:
            break
            
        msg_type = msg.get_type()
        
        # Always keep FMT messages
        if msg_type == 'FMT':
            fmt_msgs.append(msg)
            if outfile:
                outfile.write(msg.get_msgbuf())
            continue
            
        # Check for mode changes
        if msg_type == 'MODE':
            new_mode = msg.Mode
            
            if new_mode != current_mode:
                # Close the previous file
                if outfile:
                    outfile.close()
                    outfile = None
                    print(f"Closed {outfile_name}")
                
                current_mode = new_mode
                mode_name = get_mode_name(current_mode, mapping)
                
                # Check if we should record this mode
                if requested_modes is None or current_mode in requested_modes:
                    # Start a new file
                    count = segment_count.get(mode_name, 0) + 1
                    segment_count[mode_name] = count
                    
                    base, ext = os.path.splitext(input_file)
                    outfile_name = f"{base}_{mode_name}{count}{ext}"
                    print(f"Starting {outfile_name}")
                    outfile = open(outfile_name, 'wb')
                    
                    # Write all FMT messages to the new file
                    for fmt in fmt_msgs:
                        outfile.write(fmt.get_msgbuf())
                        
        # Write the message if we have an open file
        if outfile:
            outfile.write(msg.get_msgbuf())
            
    if outfile:
        outfile.close()
        print(f"Closed {outfile_name}")

def process_tlog(input_file, requested_modes):
    """
    Split a tlog file by mode.
    """
    print(f"Processing tlog file: {input_file}")
    
    mlog = mavutil.mavlink_connection(input_file, robust_parsing=False, dialect='ardupilotmega')
    
    current_mode = None
    segment_count = {} # mode_name -> count
    
    outfile = None
    outfile_name = None
    
    mapping = get_mode_mapping()
    
    while True:
        msg = mlog.recv_match(blocking=False)
        if msg is None:
            break
            
        # Check for mode changes via HEARTBEAT
        if msg.get_type() == 'HEARTBEAT' and msg.type == mavutil.mavlink.MAV_TYPE_SUBMARINE:
            new_mode = msg.custom_mode
            
            if new_mode != current_mode:
                # Close the previous file
                if outfile:
                    outfile.close()
                    outfile = None
                    print(f"Closed {outfile_name}")
                
                current_mode = new_mode
                mode_name = get_mode_name(current_mode, mapping)
                
                # Check if we should record this mode
                if requested_modes is None or current_mode in requested_modes:
                    # Start a new file
                    count = segment_count.get(mode_name, 0) + 1
                    segment_count[mode_name] = count
                    
                    base, ext = os.path.splitext(input_file)
                    outfile_name = f"{base}_{mode_name}{count}{ext}"
                    print(f"Starting {outfile_name}")
                    outfile = open(outfile_name, 'wb')
        
        # Write the message if we have an open file
        if outfile:
            # Tlog format requires timestamp header
            timestamp_us = int(msg._timestamp * 1e6)
            header = struct.pack('>Q', timestamp_us)
            outfile.write(header)
            outfile.write(msg.get_msgbuf())

    if outfile:
        outfile.close()
        print(f"Closed {outfile_name}")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modes', help='Comma separated list of mode names (e.g. SURFTRAK,MANUAL)')
    parser.add_argument('paths', nargs='+', help='Input file(s)')
    
    args = parser.parse_args()

    # TODO(clyde) add --recurse option, and use util.expand_path() to expand paths
    
    mapping = get_mode_mapping()
    requested_modes = None
    
    if args.modes:
        requested_modes = set()
        for m in args.modes.split(','):
            m = m.strip()
            # Try to resolve name to number
            if m.upper() in mapping:
                requested_modes.add(mapping[m.upper()])
            else:
                # Try as integer
                try:
                    requested_modes.add(int(m))
                except ValueError:
                    print(f"Warning: Unknown mode '{m}', ignoring.")
                    
    for path in args.paths:
        if not os.path.exists(path):
            print(f"Error: File {path} not found.")
            continue
            
        _, ext = os.path.splitext(path)
        if ext.lower() == '.bin':
            process_bin(path, requested_modes)
        elif ext.lower() == '.tlog':
            process_tlog(path, requested_modes)
        else:
            print(f"Skipping {path}: Unknown file extension {ext}")

if __name__ == '__main__':
    main()
