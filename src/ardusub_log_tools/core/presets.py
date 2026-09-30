"""
Type group presets and message type resolution for ASL 2.0.
"""

from __future__ import annotations

# Group presets mapped by format
PRESETS_BIN = {
    "EKF": ["XKF1", "XKF2", "XKF3", "XKF4", "XKF5", "XKFS", "XKFD", "XKQ1", "XKQ2"],
    "NAV": ["GPS", "POS", "ATT", "AHR2"],
}

PRESETS_MAVLINK = {
    "EKF": ["EKF_STATUS_REPORT"],
    "NAV": ["GLOBAL_POSITION_INT", "LOCAL_POSITION_NED", "ATTITUDE", "AHRS2"],
}


def resolve_types(types_arg: str | None, file_ext: str, is_all: bool = False) -> list[str] | None:
    """
    Resolve requested types string or --all flag into a list of table/message types.

    Returns None if all types should be processed.
    """
    if is_all or types_arg is None:
        return None

    ext_upper = file_ext.upper()
    is_bin = ext_upper == ".BIN"
    preset_map = PRESETS_BIN if is_bin else PRESETS_MAVLINK

    resolved: list[str] = []
    for item in types_arg.split(","):
        token = item.strip()
        if not token:
            continue
        token_upper = token.upper()
        if token_upper in preset_map:
            for preset_type in preset_map[token_upper]:
                if preset_type not in resolved:
                    resolved.append(preset_type)
        else:
            # Keep original case for extension topics (e.g. wl_dvl), upper for MAVLink/BIN
            type_name = token if token.startswith("wl_") else token_upper
            if type_name not in resolved:
                resolved.append(type_name)

    return resolved
