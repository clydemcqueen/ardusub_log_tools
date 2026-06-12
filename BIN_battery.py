#!/usr/bin/env python3

"""
Provide information about the battery type and usage from a dataflash (BIN) file.

Useful fields:
* BAT.Volt shows the instantaneous voltage.
* BAT.Curr shows the instantaneous current.
* BAT.CurrTot shows the total current consumed.
* BAT.EnrgTot shows the total energy consumed.

If the "--terse" option is specified we show one line per file: Outland, battery, or no data.
The calculation of Outland vs battery depends on the voltage range. It is not foolproof.
"""

import argparse

import matplotlib.pyplot as plt

import file_reader
import util


def process_reader(reader, terse: bool, plot: bool):
    start_time = None
    end_time = None
    timestamps = []
    voltages = []
    currents = []
    plot_timestamps = []
    plot_power = []
    plot_energy = []
    current_consumed = None
    energy_consumed = None

    for msg in reader:
        msg_type = msg.get_type()
        if msg_type == "BAT":
            data = msg.to_dict()

            if data.get("Inst", 0) != 0:
                continue

            # Volt is in Volts
            voltage = data["Volt"]

            # Filter invalid voltage readings
            # 20V seems like a reasonable upper bound for a 4S battery (max ~16.8V)
            if voltage > 20.0:
                continue

            timestamp = data["TimeUS"] / 1_000_000.0
            if start_time is None:
                start_time = timestamp
            end_time = timestamp

            timestamps.append(timestamp)
            voltages.append(voltage)
            currents.append(data["Curr"])

            # log_BAT comment says CurrTot is Ah, but in fact it is logging mAh
            current_consumed = data["CurrTot"] / 1_000.0

            # EnrgTot is in Watt-hours
            energy_consumed = data["EnrgTot"]

            if plot:
                plot_timestamps.append(timestamp - start_time)
                power_w = data["Volt"] * data["Curr"]
                plot_power.append(power_w)
                if data["EnrgTot"] >= 0:
                    plot_energy.append(data["EnrgTot"])
                else:
                    plot_energy.append(0.0)

    if not voltages:
        if terse:
            print(f"{reader.name} None")
        else:
            print("    No valid battery data found")
        return

    # Detect system type based on voltage variance
    # Use Interquartile Range (IQR) to be robust against spikes at start/end
    sorted_voltages = sorted(voltages)
    min_voltage = sorted_voltages[0]
    max_voltage = sorted_voltages[-1]
    n = len(sorted_voltages)
    q25 = sorted_voltages[n // 4]
    q75 = sorted_voltages[3 * n // 4]
    voltage_range = q75 - q25

    # 0.2V threshold for distinguishing constant voltage source from battery
    if voltage_range < 0.2:
        battery_type = "Outland"
    else:
        battery_type = "Battery"

    if terse:
        print(f"{reader.name} {battery_type}")
        return

    if battery_type == "Outland":
        print("    Voltage variance < 0.2 V, possibly Outland?")
    else:
        print("    Voltage variance > 0.2 V, possibly battery?")

    duration = end_time - start_time
    avg_voltage = sum(voltages) / len(voltages)

    valid_currents = [c for c in currents if c != -1]
    if valid_currents:
        max_current = max(valid_currents)
        avg_current = sum(valid_currents) / len(valid_currents)
    else:
        max_current = 0
        avg_current = 0

    print(f"    Duration: {duration:.1f} seconds")
    print(f"    Voltage: {min_voltage:.2f} min, {max_voltage:.2f} max, {avg_voltage:.2f} avg (V)")
    print(f"    Current: {max_current:.2f} max, {avg_current:.2f} avg (A)")

    if current_consumed is not None and current_consumed >= 0:
        print(f"    Current consumed: {current_consumed:.2f} Ah")

    if energy_consumed is not None and energy_consumed >= 0:
        print(f"    Energy consumed: {energy_consumed:.2f} Wh")

    if plot and plot_timestamps:
        output_filename = util.get_outfile_name(reader.name, ext=".pdf")

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True, figsize=(10, 10))

        ax1.plot(plot_timestamps, voltages, label="Voltage (V)", color="green")
        ax1.set_ylabel("Voltage (V)")
        ax1.grid(True)
        ax1.set_title("Battery Usage")

        ax2.plot(plot_timestamps, plot_energy, label="Energy (Wh)")
        ax2.set_ylabel("Energy (Wh)")
        ax2.grid(True)

        ax3.plot(plot_timestamps, plot_power, label="Power (W)", color="orange")
        ax3.set_xlabel("Flight Time (s)")
        ax3.set_ylabel("Power (W)")
        ax3.grid(True)

        plt.tight_layout()
        plt.savefig(output_filename)
        plt.close()
        if not terse:
            print(f"    Saved plot to {output_filename}")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    file_reader.add_file_args(parser, ext=".BIN")
    parser.add_argument("--terse", action="store_true", help="A terse report: show Outland vs battery")
    parser.add_argument("--plot", action="store_true", help="Plot Energy and Power and save as PDF")
    args = parser.parse_args()
    readers = file_reader.FileReaderList(args, ["BAT"], ext=".BIN")

    for reader in readers:
        if not args.terse:
            print(f"Processing {reader.name}...")
        process_reader(reader, args.terse, args.plot)


if __name__ == "__main__":
    main()
