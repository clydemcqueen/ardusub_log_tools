#!/usr/bin/env python3

"""
Provide information about the battery type and usage.

Useful fields:
* BATTERY_STATUS.voltage shows the instantaneous voltage.
* BATTERY_STATUS.current_battery shows the instantaneous current.
* BATTERY_STATUS.current_consumed shows the total current consumed.
* BATTERY_STATUS.energy_consumed shows the total energy consumed.

If the "--terse" option is specified we show one line per file: Outland, battery, or no data.
The calculation of Outland vs battery depends on the voltage range. It is not foolproof.
"""

import argparse

import file_reader


def process_reader(reader, terse: bool):
    start_time = None
    end_time = None
    timestamps = []
    voltages = []
    currents = []
    current_consumed = None
    energy_consumed = None

    for msg in reader:
        msg_type = msg.get_type()
        if msg_type == 'BATTERY_STATUS':
            data = msg.to_dict()
            
            # Filter invalid voltage readings (e.g., 65535 mV)
            # 20V (20000 mV) seems like a reasonable upper bound for a 4S battery (max ~16.8V)
            # The test files show correct values around 16000 mV and invalid ones at 65535 mV
            voltage = data['voltages'][0]
            if voltage > 20000:
                continue

            timestamp = msg._timestamp
            if start_time is None:
                start_time = timestamp
            end_time = timestamp
            
            timestamps.append(timestamp)
            voltages.append(voltage)
            currents.append(data['current_battery'])
            
            if data['current_consumed'] != -1:
                current_consumed = data['current_consumed']
            if data['energy_consumed'] != -1:
                energy_consumed = data['energy_consumed']

    if not voltages:
        if terse:
            print(f'{reader.name} None')
        else:
            print('    No valid battery data found')
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

    # 200mV threshold for distinguishing constant voltage source from battery
    if voltage_range < 200:
        battery_type = 'Outland'
    else:
        battery_type = 'Battery'

    if terse:
        print(f'{reader.name} {battery_type}')
        return

    if battery_type == 'Outland':
        print('    System type: Outland (constant voltage)')
    else:
        print('    System type: BlueROV2 (battery)')

    duration = end_time - start_time
    avg_voltage = sum(voltages) / len(voltages)

    valid_currents = [c for c in currents if c != -1]
    if valid_currents:
        max_current = max(valid_currents)
        avg_current = sum(valid_currents) / len(valid_currents)
    else:
        max_current = 0
        avg_current = 0

    print(f'    Duration: {duration:.1f} seconds')
    print(f'    Voltage: {min_voltage} min, {max_voltage} max, {avg_voltage:.1f} avg (mV)')
    print(f'    Current: {max_current} max, {avg_current:.1f} avg (cA)')

    if current_consumed is not None and current_consumed >= 0:
        print(f'    Current consumed: {current_consumed} mAh')

    if energy_consumed is not None and energy_consumed >= 0:
        print(f'    Energy consumed: {energy_consumed} hJ')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    file_reader.add_file_args(parser)
    parser.add_argument('--terse', action='store_true', help='A terse report: show Outland vs battery')
    args = parser.parse_args()
    readers = file_reader.FileReaderList(args, ['BATTERY_STATUS'])

    for reader in readers:
        if not args.terse:
            print(f'Processing {reader.name}...')
        process_reader(reader, args.terse)


if __name__ == '__main__':
    main()
