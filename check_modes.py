import os

os.environ['MAVLINK20'] = '1'
from pymavlink import mavutil

print("ArduSub modes:")
try:
    print(mavutil.mode_mapping_sub)
except Exception as e:
    print(f"Error accessing mode_mapping_sub: {e}")

print("\nArduCopter modes (for reference):")
try:
    print(mavutil.mode_mapping_acm)
except Exception as e:
    print(f"Error accessing mode_mapping_acm: {e}")
