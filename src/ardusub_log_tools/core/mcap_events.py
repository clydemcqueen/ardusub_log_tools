"""
Core MCAP Event and Message Extraction Helpers.
"""

from __future__ import annotations

import fnmatch
from typing import Any, Iterator

import pymavlink.dialects.v20.ardupilotmega as apm

from ardusub_log_tools.backends.telemetry import (
    EK3_SRCn_POSXY,
    EK3_SRCn_POSZ,
    EK3_SRCn_VELXY,
    EK3_SRCn_VELZ,
    EK3_SRCn_YAW,
)
from ardusub_log_tools.core import util


def resolve_enum_value(v: Any) -> int:
    """Resolve an enum value from MCAP JSON (int, dict with 'type', or pipe-delimited string)."""
    if isinstance(v, int):
        return v
    if isinstance(v, dict) and "type" in v:
        return getattr(apm, v["type"], 0)
    if isinstance(v, str):
        if "|" in v:
            res = 0
            for part in v.split("|"):
                res |= getattr(apm, part.strip(), 0)
            return res
        if hasattr(apm, v):
            return getattr(apm, v)
        try:
            return int(v)
        except ValueError:
            return 0
    return 0


class McapParam:
    """Represents a parameter extracted from MCAP PARAM_VALUE / PARAM_SET."""

    def __init__(self, param_id: str, value: float | int, param_type: int = 0, timestamp: float = 0.0):
        self.id = param_id
        self.value = value
        self.type = param_type
        self.timestamp = timestamp

    def is_int(self) -> bool:
        return isinstance(self.value, (int, float)) and float(self.value).is_integer()

    def value_str(self) -> str:
        if self.is_int():
            return str(int(self.value))
        return f"{self.value:.6f}"

    def comment(self) -> str | None:
        if self.id.startswith("EK3_SRC"):
            val_int = int(self.value)
            if self.id.endswith("POSXY"):
                return EK3_SRCn_POSXY.get(val_int, None)
            elif self.id.endswith("VELXY"):
                return EK3_SRCn_VELXY.get(val_int, None)
            elif self.id.endswith("POSZ"):
                return EK3_SRCn_POSZ.get(val_int, None)
            elif self.id.endswith("VELZ"):
                return EK3_SRCn_VELZ.get(val_int, None)
            elif self.id.endswith("YAW"):
                return EK3_SRCn_YAW.get(val_int, None)
            elif self.id == "EK3_SRC_OPTIONS":
                return "FuseAllVelocities" if val_int == 1 else "None"
        return None


def iter_mcap_statustext(mcap_file: str) -> Iterator[tuple[float, int, str]]:
    """Yield (timestamp_s, severity_int, text) for STATUSTEXT messages in an MCAP file."""
    for _, _, msg in util.iter_mcap_messages(mcap_file, message_types=["STATUSTEXT"], sys_id=None, comp_id=None):
        data = msg.json.get("message", {})
        sev = resolve_enum_value(data.get("severity", 0))
        text = str(data.get("text", "")).rstrip("\x00").strip()
        yield (msg.log_time_s, sev, text)


def extract_mcap_params(
    mcap_file: str,
    patterns: list[str] | None = None,
) -> tuple[dict[str, McapParam], list[tuple[float, McapParam, McapParam]]]:
    """
    Extract vehicle parameters from an MCAP file.

    Returns:
        params: dict mapping param_id -> final McapParam
        changes: list of (timestamp, old_param, new_param) tuples
    """
    params: dict[str, McapParam] = {}
    changes: list[tuple[float, McapParam, McapParam]] = []

    def matches_patterns(p_id: str) -> bool:
        if not patterns:
            return True
        return any(fnmatch.fnmatch(p_id, pat) for pat in patterns)

    for _, _, msg in util.iter_mcap_messages(mcap_file, message_types=["PARAM_VALUE"], sys_id=1, comp_id=1):
        m = msg.json.get("message", {})
        p_id = str(m.get("param_id", "")).rstrip("\x00").strip()
        if not p_id or not matches_patterns(p_id):
            continue

        p_val = m.get("param_value", 0.0)
        p_type = resolve_enum_value(m.get("param_type", 0))
        new_param = McapParam(p_id, p_val, p_type, msg.log_time_s)

        if p_id in params:
            old_param = params[p_id]
            if old_param.value != new_param.value:
                changes.append((msg.log_time_s, old_param, new_param))
        params[p_id] = new_param

    return params, changes
