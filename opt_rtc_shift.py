#!/usr/bin/env python3

"""
Optimize the RTC shift value by comparing data that appears in both tlog and BIN files.
"""

import argparse
import matplotlib.pyplot as plt
import numpy as np
from pymavlink import mavutil

import util


def calculate_mse(tlog_times, tlog_alts, bin_times, bin_alts, shift) -> float:
    """
    Calculate MSE for a given additional shift. Interpolate bin_alts to match tlog_times.
    """
    bin_times_shifted = bin_times + shift
    bin_alts_interpolated = np.interp(tlog_times, bin_times_shifted, bin_alts)
    return float(np.mean((tlog_alts - bin_alts_interpolated) ** 2))


def optimize_rtc_shift(tlog_path, bin_path, graph):
    """
    Optimize the RTC shift value by comparing data that appears in both tlog and BIN files.
    """

    print(f"Open {tlog_path}")
    tlog_conn = mavutil.mavlink_connection(tlog_path)

    # Use the various time_boot_ms messages to get an estimate of the RTC shift
    rtc_shift = util.get_rtc_shift(tlog_conn, rewind=True)
    print(f"Initial rtc_shift: {rtc_shift}")

    print(f"Open {bin_path}")
    bin_conn = mavutil.mavlink_connection(bin_path)

    # Get GLOBAL_POSITION_INT.rel_alt messages from the tlog
    tlog_times = []
    tlog_alts = []
    while True:
        msg = tlog_conn.recv_match(type='GLOBAL_POSITION_INT', blocking=False)
        if msg is None:
            break

        tlog_times.append(msg._timestamp)
        tlog_alts.append(msg.relative_alt / 1000.0)  # Convert mm to m

    # Get XKF1.PD messages from the BIN file
    bin_times = []
    bin_pds = []
    while True:
        msg = bin_conn.recv_match(type='XKF1', blocking=False)
        if msg is None:
            break

        # TimeUS is in microseconds, convert to seconds and apply shift
        timestamp = (msg.TimeUS / 1e6) + rtc_shift
        bin_times.append(timestamp)
        bin_pds.append(msg.PD)

    # Invert the sign to match tlog_alts
    bin_alts = [-x for x in bin_pds]

    # Continue in numpy
    tlog_times = np.array(tlog_times)
    tlog_alts = np.array(tlog_alts)
    bin_times = np.array(bin_times)
    bin_alts = np.array(bin_alts)

    # Remove NaNs if any
    # valid_tlog = ~np.isnan(tlog_alts)
    # tlog_times = tlog_times[valid_tlog]
    # tlog_alts = tlog_alts[valid_tlog]

    # valid_bin = ~np.isnan(bin_alts)
    # bin_times = bin_times[valid_bin]
    # bin_alts = bin_alts[valid_bin]

    # Only consider the overlapping time range
    start_time = max(float(tlog_times[0]), float(bin_times[0]))
    end_time = min(float(tlog_times[-1]), float(bin_times[-1]))
    mask = (tlog_times >= start_time) & (tlog_times <= end_time)

    # GLOBAL_POSITION_INT is probably lower frequency than XKF1, so we'll interpolate the XKF1 values
    tlog_times = tlog_times[mask]
    tlog_alts = tlog_alts[mask]

    if len(tlog_times) == 0:
        print("Files do not overlap!")
        return

    # Calculate MSE with current rtc_shift
    initial_mse = calculate_mse(tlog_times, tlog_alts, bin_times, bin_alts, 0)
    print(f"Initial MSE: {initial_mse:.8f}")

    # Optimize: search +/- 0.2 seconds with high resolution
    shifts = np.linspace(-0.2, 0.2, 2000)  # 0.2ms resolution
    mses = [calculate_mse(tlog_times, tlog_alts, bin_times, bin_alts, s) for s in shifts]

    min_mse_idx = np.argmin(mses)
    optimal_shift_offset = float(shifts[min_mse_idx])
    min_mse = mses[min_mse_idx]

    print(f"Optimal shift offset: {optimal_shift_offset:.6f} s")
    print(f"Minimum MSE: {min_mse:.8f}")
    print(f"Improvement: {(initial_mse - min_mse) / initial_mse * 100:.2f}%")
    print(f"Total suggested rtc_shift: {rtc_shift + optimal_shift_offset:.6f}")

    if graph:
        plt.figure(figsize=(10, 5))
        plt.plot(shifts, mses)
        plt.axvline(x=0, color='r', linestyle='--', label='Current Shift')
        plt.axvline(x=optimal_shift_offset, color='g', linestyle='--', label='Optimal Shift')
        plt.xlabel('Additional Shift (s)')
        plt.ylabel('MSE')
        plt.title('MSE vs Time Shift (Zoomed)')
        plt.legend()
        plt.grid(True)
        plt.savefig("mse_optimization.png")
        print("Plot saved to mse_optimization.png")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("--graph", action='store_true', help="Graph optimization results")
    parser.add_argument("tlog_path", help="Path to the tlog file")
    parser.add_argument("bin_path", help="Path to the BIN file")
    args = parser.parse_args()
    optimize_rtc_shift(args.tlog_path, args.bin_path, args.graph)


if __name__ == "__main__":
    main()
