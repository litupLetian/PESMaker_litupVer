# Copyright 2026 Ting Liang and PESMaker development team
# This file is part of PESMaker.
#
# PESMaker is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PESMaker is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PESMaker. If not, see <https://www.gnu.org/licenses/>.
"""ASE-backed structure and trajectory parsing helpers."""

from __future__ import annotations

from glob import glob
from pathlib import Path
from typing import Any


def read_frames(pattern: str | Path, *, file_format: str | None = None) -> list[Any]:
    """Read all ASE frames matching a path or glob pattern."""
    groups = read_frame_groups(pattern, file_format=file_format)
    return [frame for _, frames in groups for frame in frames]


def read_frame_groups(
    pattern: str | Path,
    *,
    file_format: str | None = None,
) -> list[tuple[Path, list[Any]]]:
    """Read ASE frames grouped by each matched trajectory file."""
    try:
        from ase.io import read
        from ase.io.formats import UnknownFileTypeError
    except ImportError as exc:
        raise RuntimeError("Reading trajectory frames requires ASE") from exc

    pattern_text = str(pattern)
    paths = [Path(path) for path in sorted(glob(pattern_text, recursive=True))]
    if not paths and Path(pattern_text).exists():
        paths = [Path(pattern_text)]

    groups = []
    for path in paths:
        resolved_format = _resolve_ase_format(path, file_format)
        try:
            items = read(path, index=":", format=resolved_format)
        except UnknownFileTypeError as exc:
            raise ValueError(
                "ASE could not infer the trajectory format for "
                f"{path}. Set sampling.selection.trajectory_format, for example "
                "`vasp-xdatcar` for XDATCAR content stored with a nonstandard "
                "filename."
            ) from exc
        if not isinstance(items, list):
            items = [items]
        groups.append((path, items))
    if not any(frames for _, frames in groups):
        raise ValueError(f"no frames matched pattern: {pattern_text}")
    return groups


def _resolve_ase_format(path: Path, file_format: str | None) -> str | None:
    if file_format:
        return _normalize_ase_format(file_format)
    upper_name = path.name.upper()
    if upper_name == "XDATCAR" or upper_name.startswith("XDATCAR_"):
        return "vasp-xdatcar"
    if path.suffix.lower() == ".xdatcar":
        return "vasp-xdatcar"
    return None


def _normalize_ase_format(file_format: str) -> str:
    normalized = file_format.strip().lower().replace("_", "-")
    if normalized in {"xdatcar", "vasp-xdatcar"}:
        return "vasp-xdatcar"
    return normalized


def write_extxyz_many(path: str | Path, frames) -> None:
    """Write multiple frames as an extxyz dataset."""
    try:
        from ase.io import write
    except ImportError as exc:
        raise RuntimeError("Writing extxyz requires ASE") from exc

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write(output_path, frames, format="extxyz")
