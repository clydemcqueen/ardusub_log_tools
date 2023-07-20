import glob
import os


def add_rate_field(messages: list[dict], half_n: int, max_gap: float, field_name: str):
    """
    Calc message rate using the MAV timestamp (comes from QGC wall time) based on 2 * half_n intervals.

    If there is a long gap in the timestamps then split the list into 2 segments and mark the gap by setting the rate
    to 0.0 on the messages just before and just after the gap. This will make the gap obvious in a log viewer.

    Note that messages might be coming from multiple components, e.g., DISTANCE_SENSOR from autopilot and BlueOS.
    Re-run with compid=x to isolate each source component.

    This is a linear but tricky algorithm. See the tests for example output.
    """

    if len(messages) < 2 * half_n + 1:
        return

    def is_gap_right(j: int):
        return j + 1 < len(messages) and messages[j + 1]['timestamp'] - messages[j]['timestamp'] > max_gap

    total_gaps = 0

    # If timestamps aren't monotonic we might end up with division by zero
    try:
        # Note left and right edge of window
        wl = i = wr = 0
        while wr < len(messages) and wr < half_n and not is_gap_right(wr):
            wr += 1

        while i < len(messages) - 1:
            # Expand window on the right
            if wr < len(messages) and not is_gap_right(wr - 1):
                wr += 1

            if is_gap_right(i):
                gap_len = messages[i + 1]['timestamp'] - messages[i]['timestamp']
                total_gaps += gap_len
                print(f'NOTE: {gap_len :.2f}s gap detected while generating {field_name}')

                # Set the rate to 0.0 on either side of the segment
                messages[i][field_name] = 0.0
                i += 1
                messages[i][field_name] = 0.0

                # Reset the window
                wl = wr = i
                while wr < len(messages) and wr - wl - 1 < half_n and not is_gap_right(wr):
                    wr += 1
            else:
                # print(f"{i} :: {wr - wl - 1}.0 / (messages[{wr - 1}]['timestamp'] - messages[{wl}]['timestamp']")
                messages[i][field_name] = (wr - wl - 1) / (messages[wr - 1]['timestamp'] - messages[wl]['timestamp'])

                # Shrink window on the left
                if i - wl >= half_n:
                    wl += 1

            i += 1

        # Last message should have rate=0.0. This will be easy to spot in plotjuggler.
        messages[-1][field_name] = 0.0

    except ZeroDivisionError:
        print(f'WARNING: divide by zero while calculating {field_name}, timestamps may repeat due to high rate')

    total_time = messages[-1]['timestamp'] - messages[0]['timestamp']
    without_gaps = total_time - total_gaps
    print(f'{field_name} summary: {len(messages)} messages in {total_time :.2f} seconds for '
          f'{len(messages) / total_time :.2f} mps, without gaps {len(messages) / without_gaps :.2f} mps')


def expand_path(paths: list[str], recurse: bool, ext: str | list[str]) -> list[str]:
    files = set()

    if type(ext) is str:
        ext = [ext]

    for path in paths:
        if os.path.isfile(path):
            _, file_ext = os.path.splitext(os.path.basename(path))
            if file_ext in ext:
                files.add(path)
        else:
            if recurse:
                paths += glob.glob(path + '/*')

    return sorted(files)


def get_outfile_name(infile: str, suffix: str = '', ext: str = '.csv'):
    """Given input file path, return <path to infile>/<infile root>suffix.ext"""
    dirname, basename = os.path.split(infile)
    root, _ = os.path.splitext(basename)
    return os.path.join(dirname, root + suffix + ext)
