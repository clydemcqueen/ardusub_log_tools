"""
Output path resolution for ASL 2.0.
"""

from __future__ import annotations

import os


def resolve_outfile_name(
    infile: str,
    suffix: str = "",
    ext: str = ".csv",
    output_dir: str | None = None,
) -> str:
    """
    Given an input file path, return output path conforming to:
    [<output_dir>|<path to infile>]/<infile root>[_asl_<suffix>].<ext>
    """
    dirname, basename = os.path.split(infile)
    root, _ = os.path.splitext(basename)

    if output_dir:
        dirname = output_dir
        os.makedirs(dirname, exist_ok=True)

    if suffix:
        if suffix.startswith("_asl_"):
            full_suffix = suffix
        elif suffix.startswith("_"):
            full_suffix = f"_asl{suffix}"
        else:
            full_suffix = f"_asl_{suffix}"
    else:
        full_suffix = "_asl"

    return os.path.join(dirname, root + full_suffix + ext)
