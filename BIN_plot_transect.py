#!/usr/bin/env python3

"""
Read BIN files and plot transect data: path, altitude, and rangefinder vs target across modes.
Inspects the TRNS table from transect4.lua and checks for target consistency in SURFTRAK mode.

Plots:
1. Top-down XY plot of path (colored by mode)
2. Elevation Z view: Sub vertical motion + Terrain height + Target altitude
3. Rangefinder value vs Target (RF reading, Lua rf_target, SURFTRAK target)
4. Speed (TRNS commanded speed)
"""

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import util
from segment_reader import add_segment_args, choose_reader_list
from table_types import MODE_NAMES

MODE_COLORS = {
    "SURFTRAK": "orange",
    "GUIDED": "green",
    "ALT_HOLD": "blue",
    "STABILIZE": "cyan",
    "MANUAL": "gray",
    "AUTO": "magenta",
}


def get_mode_name(mode_num):
    return MODE_NAMES.get(mode_num, f"Unknown({mode_num})")


def load_data(reader):
    data = {
        "XKF1": [],
        "TRNS": [],
    }

    wanted_types = set(data.keys())

    for msg in reader:
        mtype = msg.get_type()
        if mtype in wanted_types:
            d = msg.to_dict()
            # Only 1 core in the BR Navigator; ignore other cores if present
            if mtype == "XKF1":
                if "C" in d and d["C"] != 0:
                    continue
            data[mtype].append(d)

    # Convert to DataFrames
    dfs = {}
    for k, v in data.items():
        if v:
            dfs[k] = pd.DataFrame(v)
        else:
            dfs[k] = pd.DataFrame()

    return dfs


def check_surftrak_targets(dfs, reader_name=None):
    """
    Check that surf_target_m (SurfTarg) is always the same as rf_target (RFTarg),
    if there is a target (RFTarg > 0), and we are in SURFTRAK mode (Mode == 21).
    Print out any problems found.
    """
    prefix = f"[{reader_name}] " if reader_name else ""

    df_trns = dfs["TRNS"]

    # SURFTRAK mode number is 21
    st_df = df_trns[df_trns["Mode"] == 21]
    if st_df.empty:
        print(f"{prefix}No SURFTRAK mode samples found in TRNS table.")
        return True, []

    problems = []

    # Check 1: In SURFTRAK mode with an active rf_target (RFTarg > 0),
    # SurfTarg must be set and match RFTarg.
    st_with_rf_target = st_df[st_df["RFTarg"] > 0]
    for _, row in st_with_rf_target.iterrows():
        rf_targ = row["RFTarg"]
        surf_targ = row["SurfTarg"]
        time_us = row["TimeUS"]

        if surf_targ <= 0:
            problems.append(
                {
                    "TimeUS": time_us,
                    "RFTarg": rf_targ,
                    "SurfTarg": surf_targ,
                    "desc": f"RFTarg is {rf_targ:.2f}m, but SurfTarg is not set ({surf_targ:.2f}m)",
                }
            )
        elif abs(surf_targ - rf_targ) > 0.01:
            diff = abs(surf_targ - rf_targ)
            problems.append(
                {
                    "TimeUS": time_us,
                    "RFTarg": rf_targ,
                    "SurfTarg": surf_targ,
                    "desc": f"RFTarg is {rf_targ:.2f}m, but SurfTarg is {surf_targ:.3f}m (diff {diff:.3f}m)",
                }
            )

    # Check 2: ArduSub had a SURFTRAK target, but Lua had no rf_target
    st_with_surf_no_rf = st_df[(st_df["SurfTarg"] > 0) & (st_df["RFTarg"] <= 0)]
    for _, row in st_with_surf_no_rf.iterrows():
        surf_targ = row["SurfTarg"]
        rf_targ = row["RFTarg"]
        time_us = row["TimeUS"]
        problems.append(
            {
                "TimeUS": time_us,
                "RFTarg": rf_targ,
                "SurfTarg": surf_targ,
                "desc": f"SurfTarg is {surf_targ:.2f}m, but RFTarg is not set ({rf_targ:.2f}m)",
            }
        )

    if problems:
        print(
            f"{prefix}WARNING: Found {len(problems)} SURFTRAK target problem(s) out of {len(st_df)} SURFTRAK sample(s):"
        )
        for prob in problems[:15]:
            print(f"  TimeUS {prob['TimeUS']}: {prob['desc']}")
        if len(problems) > 15:
            print(f"  ... and {len(problems) - 15} more problem sample(s).")
        return False, problems
    else:
        num_targets = len(st_with_rf_target)
        print(f"{prefix}OK: SurfTarg matches RFTarg across all {num_targets} SURFTRAK sample(s) with active target.")
        return True, []


def plot_transect(dfs, pdf_outfile, csv_outfile, show_plot, reader_name=None):
    if dfs["TRNS"].empty:
        print("No TRNS data found. Cannot plot transect.")
        return

    # Always perform the consistency check
    check_surftrak_targets(dfs, reader_name=reader_name)

    if dfs["XKF1"].empty:
        print("No XKF1 position data found. Cannot plot.")
        return

    # Master time base will be XKF1
    main_df = dfs["XKF1"][["TimeUS", "PN", "PE", "PD"]].copy()
    main_df.sort_values("TimeUS", inplace=True)

    # Merge TRNS table (Mode, targets, readings, depth, heading, speed)
    trns_df = dfs["TRNS"][["TimeUS", "Mode", "RFTarg", "RFRead", "SurfTarg", "Depth", "TargZ", "Head", "Spd"]].copy()
    trns_df.sort_values("TimeUS", inplace=True)
    merged = pd.merge_asof(main_df, trns_df, on="TimeUS", direction="nearest", tolerance=200000)

    # Fill mode forward/backward for any edge XKF1 samples
    merged["Mode"] = merged["Mode"].ffill().bfill()

    # Add derived columns for CSV and plotting
    t0 = merged["TimeUS"].iloc[0]
    merged["TimeS"] = (merged["TimeUS"] - t0) / 1e6
    merged["SubAlt"] = -merged["PD"]

    # RF reading from TRNS
    rf_read = merged["RFRead"].copy()
    rf_read[rf_read <= 0] = np.nan
    merged["RFRead"] = rf_read
    merged["TerrainAlt"] = merged["SubAlt"] - merged["RFRead"]

    # RF target from TRNS
    rf_targ = merged["RFTarg"].copy()
    rf_targ[rf_targ <= 0] = np.nan
    merged["RFTarg"] = rf_targ

    # SURFTRAK target from TRNS
    surf_targ = merged["SurfTarg"].copy()
    surf_targ[surf_targ <= 0] = np.nan
    merged["SurfTarg"] = surf_targ

    # Target altitude in GUIDED mode (TargZ is depth down)
    targ_z = merged["TargZ"].copy()
    targ_z[targ_z < 0] = np.nan
    merged["SubTargetAlt"] = -targ_z

    # Speed from TRNS
    spd = merged["Spd"].copy()
    spd[spd < 0] = np.nan
    merged["Spd"] = spd

    merged["ModeName"] = merged["Mode"].map(get_mode_name)

    if csv_outfile:
        merged.to_csv(csv_outfile, index=False)
        print(f"CSV saved to {csv_outfile}")

    if not (pdf_outfile or show_plot):
        return

    # --- PLOT 1: XY Motion ---
    fig, axes = plt.subplots(4, 1, figsize=(10, 20), sharex=False)

    ax_xy = axes[0]
    ax_xy.set_title("Sub Motion (XY Top-Down)")
    ax_xy.set_xlabel("East (m)")
    ax_xy.set_ylabel("North (m)")
    ax_xy.axis("equal")
    ax_xy.grid(True)

    # Identify changes in mode
    merged["ModeChange"] = merged["Mode"].diff().ne(0).cumsum()

    for _, group in merged.groupby("ModeChange"):
        mode_num = group["Mode"].iloc[0]
        mode_name = get_mode_name(mode_num)
        color = MODE_COLORS.get(mode_name, None)

        label = mode_name if mode_name not in [line.get_label() for line in ax_xy.get_lines()] else None
        ax_xy.plot(group["PE"], group["PN"], color=color, label=label)

    ax_xy.legend()

    # --- PLOT 2: Elevation Z (Sub + Terrain + Target) ---
    ax_z = axes[1]
    ax_z.set_title("Vertical Motion")
    ax_z.set_xlabel("Time (s)")
    ax_z.set_ylabel("Altitude (m)")
    ax_z.grid(True)

    ax_z.plot(merged["TimeS"], merged["SubAlt"], label="Sub Altitude", color="blue")
    ax_z.plot(merged["TimeS"], merged["TerrainAlt"], label="Terrain Altitude", color="brown", alpha=0.6)

    if not merged["SubTargetAlt"].isna().all():
        ax_z.plot(
            merged["TimeS"],
            merged["SubTargetAlt"],
            label="Target Altitude (GUIDED)",
            color="green",
            linestyle="--",
            alpha=0.8,
        )

    ax_z.legend()

    # --- PLOT 3: Rangefinder vs Target ---
    ax_rf = axes[2]
    ax_rf.set_title("Rangefinder vs Target")
    ax_rf.set_xlabel("Time (s)")
    ax_rf.set_ylabel("Range (m)")
    ax_rf.grid(True)

    ax_rf.plot(merged["TimeS"], merged["RFRead"], label="RF Reading", color="black", alpha=0.5)

    if not merged["RFTarg"].isna().all():
        ax_rf.plot(merged["TimeS"], merged["RFTarg"], label="RF Target (TRNS)", color="orange", linewidth=2)

    if not merged["SurfTarg"].isna().all():
        ax_rf.plot(
            merged["TimeS"], merged["SurfTarg"], label="SURFTRAK Target", color="purple", linestyle=":", linewidth=1.5
        )

    ax_rf.legend()

    # --- PLOT 4: Speed ---
    ax_spd = axes[3]
    ax_spd.set_title("Speed")
    ax_spd.set_xlabel("Time (s)")
    ax_spd.set_ylabel("Speed (m/s)")
    ax_spd.grid(True)

    ax_spd.plot(merged["TimeS"], merged["Spd"], label="Speed (TRNS)", color="blue")
    ax_spd.legend()

    # Output
    plt.tight_layout()
    if pdf_outfile:
        plt.savefig(pdf_outfile)
        print(f"Plot saved to {pdf_outfile}")

    if show_plot:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_segment_args(parser, ".BIN")
    parser.add_argument("--pdf", action="store_true", help="Write plot to PDF instead of showing it")
    parser.add_argument("--csv", action="store_true", help="Write results to CSV")
    parser.add_argument("--check", action="store_true", help="Only check SURFTRAK target consistency without plotting")

    args = parser.parse_args()

    readers = choose_reader_list(args, None, ".BIN")

    for reader in readers:
        print(f"Processing {reader.name}...")
        dfs = load_data(reader)

        if dfs["TRNS"].empty:
            print(f"[{reader.name}] No TRNS table found in log.")
            continue

        if args.check:
            check_surftrak_targets(dfs, reader_name=reader.name)
            continue

        pdf_outfile = None
        if args.pdf:
            pdf_outfile = util.get_outfile_name(reader.name, suffix="_transect", ext=".pdf")

        csv_outfile = None
        if args.csv:
            csv_outfile = util.get_outfile_name(reader.name, suffix="_transect", ext=".csv")

        show_plot = not (args.pdf or args.csv)
        plot_transect(dfs, pdf_outfile, csv_outfile, show_plot, reader_name=reader.name)


if __name__ == "__main__":
    main()
