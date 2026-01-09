#!/usr/bin/env python3

"""
Read BIN files and plot rangefinder vs target forSURFTRAK and GUIDED above-terrain modes.

Plots:
1. Top-down XY plot of path (colored by mode) + Guided Targets.
2. Elevation Z view: Sub vertical motion + Terrain height.
3. Rangefinder value vs Target (SURFTRAK/GUIDED only).
"""

import argparse
import sys
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

import util
from segment_reader import add_segment_args, choose_reader_list
from table_types import MODE_NAMES

MODE_COLORS = {
    'SURFTRAK': 'orange',
    'GUIDED': 'green',
    'ALT_HOLD': 'blue',
    'STABILIZE': 'cyan',
    'MANUAL': 'gray',
    'SURFACE': 'magenta',
}


def get_mode_name(mode_num):
    return MODE_NAMES.get(mode_num, f'Unknown({mode_num})')


def load_data(reader):
    data = {
        'XKF1': [],
        'GUIP': [],
        'GUIT': [],
        'CTUN': [],
        'RFND': [],
        'MODE': [],
    }
    
    # We want these types
    wanted_types = set(data.keys())

    for msg in reader:
        mtype = msg.get_type()
        if mtype in wanted_types:
            d = msg.to_dict()
            # Only 1 core in the BR Navigator; ignore other cores if present
            if mtype == 'XKF1':
                if 'C' in d and d['C'] != 0:
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


def plot_surftrak(dfs, pdf_outfile, csv_outfile, show_plot):
    # Check if we have essential data (XKF1 for position)
    if dfs['XKF1'].empty:
        print("No XKF1 position data found. Cannot plot.")
        return

    # Master time base will be XKF1
    main_df = dfs['XKF1'][['TimeUS', 'PN', 'PE', 'PD']].copy()
    main_df.sort_values('TimeUS', inplace=True)
    
    # Merge Mode
    if not dfs['MODE'].empty:
        mode_df = dfs['MODE'][['TimeUS', 'ModeNum']].copy()
        mode_df.sort_values('TimeUS', inplace=True)
        # merge_asof: direction='backward' means for each XKF1 time, find the last MODE time <= XKF1 time
        merged = pd.merge_asof(main_df, mode_df, on='TimeUS', direction='backward')
        # Fill NaN modes at the start
        merged['ModeNum'] = merged['ModeNum'].ffill().bfill()
    else:
        merged = main_df.copy()
        merged['ModeNum'] = -1 # Unknown

    # Merge RFND for Terrain
    # RFND usually higher rate or similar.
    if not dfs['RFND'].empty:
        rfnd_df = dfs['RFND'][['TimeUS', 'Dist']].copy()
        rfnd_df.sort_values('TimeUS', inplace=True)
        merged = pd.merge_asof(merged, rfnd_df, on='TimeUS', direction='nearest', tolerance=200000) # 200ms tolerance
    else:
        merged['Dist'] = np.nan

    # Merge Targets (CTUN.DSAlt, GUIT.RFTarg)
    # CTUN
    if not dfs['CTUN'].empty:
        ctun_df = dfs['CTUN'][['TimeUS', 'DSAlt']].copy()
        ctun_df.sort_values('TimeUS', inplace=True)
        merged = pd.merge_asof(merged, ctun_df, on='TimeUS', direction='nearest', tolerance=200000)
    else:
        merged['DSAlt'] = np.nan

    # GUIT
    if not dfs['GUIT'].empty:
        guit_df = dfs['GUIT'][['TimeUS', 'RFTarg']].copy()
        guit_df.sort_values('TimeUS', inplace=True)
        merged = pd.merge_asof(merged, guit_df, on='TimeUS', direction='nearest', tolerance=200000)
    else:
        merged['RFTarg'] = np.nan

    # GUIP
    if not dfs['GUIP'].empty:
        # GUIP is in cm, convert to m
        guip_df = dfs['GUIP'][['TimeUS', 'pX', 'pY', 'pZ']].copy()
        guip_df['GuipPN'] = guip_df['pX'] / 100.0
        guip_df['GuipPE'] = guip_df['pY'] / 100.0
        guip_df['GuipPD'] = guip_df['pZ'] / 100.0
        guip_df = guip_df[['TimeUS', 'GuipPN', 'GuipPE', 'GuipPD']]
        guip_df.sort_values('TimeUS', inplace=True)
        merged = pd.merge_asof(merged, guip_df, on='TimeUS', direction='nearest', tolerance=200000)
    else:
        merged['GuipPN'] = np.nan
        merged['GuipPE'] = np.nan
        merged['GuipPD'] = np.nan

    # Add derived columns for CSV and convenient plotting
    t0 = merged['TimeUS'].iloc[0]
    merged['TimeS'] = (merged['TimeUS'] - t0) / 1e6
    merged['SubAlt'] = -merged['PD']
    
    dist_clean = merged['Dist'].copy()
    dist_clean[dist_clean == 0] = np.nan
    merged['TerrainAlt'] = merged['SubAlt'] - dist_clean
    
    merged['ModeName'] = merged['ModeNum'].map(get_mode_name)

    if csv_outfile:
        merged.to_csv(csv_outfile, index=False)
        print(f"CSV saved to {csv_outfile}")

    if not (pdf_outfile or show_plot):
        return
        
    # --- PLOT 1: XY Motion ---
    fig, axes = plt.subplots(3, 1, figsize=(10, 15), sharex=False)
    
    ax_xy = axes[0]
    ax_xy.set_title('Sub Motion (XY Top-Down)')
    ax_xy.set_xlabel('East (m)')
    ax_xy.set_ylabel('North (m)')
    ax_xy.axis('equal')
    ax_xy.grid(True)

    # Identify changes in mode
    merged['ModeChange'] = merged['ModeNum'].diff().ne(0).cumsum()
    
    for _, group in merged.groupby('ModeChange'):
        mode_num = group['ModeNum'].iloc[0]
        mode_name = get_mode_name(mode_num)
        color = MODE_COLORS.get(mode_name, None) # None lets matplotlib cycle
        
        label = mode_name if mode_name not in [l.get_label() for l in ax_xy.get_lines()] else None
        
        ax_xy.plot(group['PE'], group['PN'], color=color, label=label)

    # Plot GUIP targets if available
    if not dfs['GUIP'].empty:
        # The code suggests that the data is in meters, but ArduSub actually logs in cm (a small bug)
        guip_df = dfs['GUIP']
        ax_xy.plot(guip_df['pY'] / 100, guip_df['pX'] / 100, '.', color='red', label='Guided Target', markersize=0.5) 

    ax_xy.legend()
    
    # --- PLOT 2: Elevation Z (Sub + Terrain) ---
    ax_z = axes[1]
    ax_z.set_title('Vertical Motion')
    ax_z.set_xlabel('Time (s)')
    ax_z.set_ylabel('Altitude (m)')
    ax_z.grid(True)
    
    ax_z.plot(merged['TimeS'], merged['SubAlt'], label='Sub Altitude')
    
    ax_z.plot(merged['TimeS'], merged['TerrainAlt'], label='Terrain Altitude', alpha=0.6)
    
    ax_z.legend()
    
    # --- PLOT 3: Rangefinder vs Target ---
    ax_rf = axes[2]
    ax_rf.set_title('Rangefinder vs Target')
    ax_rf.set_xlabel('Time (s)')
    ax_rf.set_ylabel('Range (m)')
    ax_rf.grid(True)
    
    # Re-create dist_clean for plotting to avoid plotting 0s
    dist_clean = merged['Dist'].copy()
    dist_clean[dist_clean == 0] = np.nan
    
    ax_rf.plot(merged['TimeS'], dist_clean, label='RF Reading', color='black', alpha=0.5)
    
    is_surftrak = merged['ModeNum'] == 21 # SURFTRAK
    is_guided = merged['ModeNum'] == 4   # GUIDED
    
    # Plot SURFTRAK target
    surftrak_target = merged['DSAlt'].copy()
    surftrak_target[~is_surftrak] = np.nan
    if not surftrak_target.isna().all():
        ax_rf.plot(merged['TimeS'], surftrak_target, label='SurfTrak Target', color='orange', linewidth=2)
        
    # Plot GUIDED target
    guided_target = merged['RFTarg'].copy()
    guided_target[~is_guided] = np.nan
    if not guided_target.isna().all():
        ax_rf.plot(merged['TimeS'], guided_target, label='Guided Target', color='green', linewidth=2)

    ax_rf.legend()
    
    # Output
    plt.tight_layout()
    if pdf_outfile:
        plt.savefig(pdf_outfile)
        print(f"Plot saved to {pdf_outfile}")
    
    if show_plot:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_segment_args(parser, '.BIN')
    parser.add_argument('--pdf', action='store_true', help='Write plot to PDF instead of showing it')
    parser.add_argument('--csv', action='store_true', help='Write results to CSV')
    
    args = parser.parse_args()
    
    readers = choose_reader_list(args, None, '.BIN')
    
    for reader in readers:
        print(f"Processing {reader.name}...")
        dfs = load_data(reader)
        
        pdf_outfile = None
        if args.pdf:
            pdf_outfile = util.get_outfile_name(reader.name, '', '.pdf')
            
        csv_outfile = None
        if args.csv:
            csv_outfile = util.get_outfile_name(reader.name, '', '.csv')
            
        show_plot = not (args.pdf or args.csv)
        plot_surftrak(dfs, pdf_outfile, csv_outfile, show_plot)


if __name__ == '__main__':
    main()
