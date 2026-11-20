# ardusub_log_tools (asl)

## Overview

`ardusub_log_tools` (`asl`) is a Python 3.12 package of log analysis tools for [ArduSub](https://www.ardusub.com/) and [BlueOS](https://blueos.cloud/docs/stable/usage/overview/) logs (`.BIN` DataFlash, `.tlog` MAVLink telemetry, and `.mcap` BlueOS recordings). It uses a standard `src/` layout so other projects (such as `seaq_logs`, `orca5_1_tests`, and environments running `MAVExplorer.py`) can install it in editable mode (`pip install -e ../ardusub_log_tools`) and immediately invoke its CLI scripts or import `ardusub_log_tools.<module>`.

## Python Virtual Environment (.venv)

**CRITICAL RULE:** Never run bare `python3` or `python` from `host_ws`.
Always use the virtual environment for this project:
```bash
ardusub_log_tools/.venv/bin/python <script_path>
```

Set up or refresh the environment from `ardusub_log_tools/`:
```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` contains `-e .[dev]`, installing runtime dependencies plus `jsonschema`, `pytest`, and `ruff`.

To install `ardusub_log_tools` in editable mode into another project's `.venv`:
```bash
other_project/.venv/bin/pip install -e path/to/ardusub_log_tools
```

To install with `MAVExplorer.py` (`MAVProxy`, `wxPython`, `scipy`, `lxml`, `future`, `setuptools<80`):
```bash
.venv/bin/pip install -e ".[mavexplorer]"
```

## Linting, Formatting, and Testing

Configuration lives in [`pyproject.toml`](pyproject.toml):
- **Ruff**: `line-length = 120`, `target-version = "py312"`, `select = ["E", "F", "I"]`, `ignore = ["E501", "E402"]`, `quote-style = "double"`.
- **Pre-commit**: [`.pre-commit-config.yaml`](.pre-commit-config.yaml) runs `ruff` and `ruff-format`.
- **CI**: [`.github/workflows/test.yml`](.github/workflows/test.yml) enforces `ruff check .`, `ruff format --check .`, and `pytest` on Python 3.12.

Run locally from `host_ws`:
```bash
ardusub_log_tools/.venv/bin/ruff check ardusub_log_tools
ardusub_log_tools/.venv/bin/ruff format --check ardusub_log_tools
ardusub_log_tools/.venv/bin/pytest ardusub_log_tools
```

## Package Inventory (`src/ardusub_log_tools/`)

- **Core library modules**: `util`, `dive_logs`, `file_reader`, `segment_reader`, `log_merger`, `table_types`, `geometry`
- **DataFlash (`.BIN`) CLI tools**: `BIN_*.py` (`BIN_info.py`, `BIN_messages.py`, `BIN_timeline.py`, `BIN_param.py`, `BIN_merge.py`, `BIN_explode.py`, `BIN_plot_transect.py`, `BIN_plot_local.py`, `BIN_plot_viso.py`, `BIN_ekf_status.py`, `BIN_battery.py`, `BIN_filter.py`, `BIN_extract_files.py`, `BIN_graph_alt.py`, `BIN_gyro_bias_stats.py`, `BIN_mag_3d.py`, `BIN_mag_stats.py`, `BIN_map_maker.py`)
- **Telemetry (`.tlog`) CLI tools**: `tlog_*.py`, `check_offset_stability.py`, `mission_dump.py`
- **BlueOS (`.mcap`) CLI tools**: `mcap_*.py` (`mcap_channels.py`, `mcap_dump_logs.py`, `mcap_explode.py`, `mcap_explode_extension_logs.py`, `mcap_extract_video.py`, `mcap_map_maker.py`, `mcap_merge.py`, `mcap_plot_local.py`, `mcap_strip_video.py`, `mcap_tlog_diff.py`, `mcap_to_tlog.py`, `mcap_types.py`, `mcap_wl_ugps_acoustic_info.py`)
- **Multi-log / cross-format CLI tools**: `dive_logs.py`, `check_rtc_time.py`, `show_types.py`, `split_by_mode.py`, `map_maker.py`, `csv_bad_time.py`, `mav_type_echo.py`
