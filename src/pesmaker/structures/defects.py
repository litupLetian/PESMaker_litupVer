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
"""Surface and defect builders for generated candidate structures."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np


@dataclass(frozen=True)
class StructureVariant:
    """One generated structural variant before random perturbation.

    Attributes:
        name: Filesystem-safe variant name.
        atoms: ASE `Atoms` object for this variant.
        description: Human-readable variant description for manifests.
    """

    name: str
    atoms: Any
    description: str


def apply_surface_settings(atoms, settings: dict[str, Any] | None):
    """Apply optional 2D slab centering and vacuum settings.

    Args:
        atoms: ASE `Atoms` object.
        settings: Mapping such as `{vacuum: 30.0, axis: 2, center: true}`.

    Returns:
        A copied ASE `Atoms` object with the requested vacuum applied.
    """
    result = atoms.copy()
    settings = settings or {}
    if not settings:
        return result

    axis = int(settings.get("axis", 2))
    vacuum = settings.get("vacuum")
    center = bool(settings.get("center", True))
    if axis not in {0, 1, 2}:
        raise ValueError("generation.surface.axis must be 0, 1, or 2")
    if vacuum is not None:
        vacuum_value = float(vacuum)
        if vacuum_value < 0:
            raise ValueError("generation.surface.vacuum can not be negative")
        if center:
            result.center(vacuum=vacuum_value, axis=axis)
        else:
            cell = result.cell.array.copy()
            cell[axis] = cell[axis] / np.linalg.norm(cell[axis]) * vacuum_value
            result.set_cell(cell, scale_atoms=False)
    return result


def generate_defect_variants(
    atoms,
    settings: dict[str, Any] | None,
) -> tuple[StructureVariant, ...]:
    """Build pristine, vacancy, and line-defect variants from a base structure.

    Args:
        atoms: ASE `Atoms` object after supercell/surface preparation.
        settings: Defect settings from `generation.defects`.

    Returns:
        Tuple of structural variants. Missing settings return only pristine.
    """
    settings = settings or {}
    variants: list[StructureVariant] = []
    include_pristine = bool(settings.get("include_pristine", True))
    if include_pristine or not settings:
        variants.append(StructureVariant("pristine", atoms.copy(), "pristine"))

    variants.extend(_single_vacancies(atoms, settings.get("single_vacancies")))
    variants.extend(_double_vacancies(atoms, settings.get("double_vacancies")))
    variants.extend(_line_defects(atoms, settings.get("line_defects")))
    return tuple(variants)


def _single_vacancies(atoms, settings: Any) -> list[StructureVariant]:
    options = _normalize_defect_options(settings, default_max=len(atoms))
    if not options["enabled"]:
        return []

    variants: list[StructureVariant] = []
    for index in _candidate_indices(atoms, options)[: options["max_count"]]:
        variant = atoms.copy()
        symbol = variant[index].symbol
        del variant[index]
        variants.append(
            StructureVariant(
                f"single_vacancy_{symbol}_{index:06d}",
                variant,
                f"single vacancy: remove {symbol} atom {index}",
            )
        )
    return variants


def _double_vacancies(atoms, settings: Any) -> list[StructureVariant]:
    options = _normalize_defect_options(settings, default_max=20)
    if not options["enabled"]:
        return []

    pairs = list(combinations(_candidate_indices(atoms, options), 2))
    if options.get("nearest_first"):
        positions = atoms.get_positions()
        pairs.sort(key=lambda pair: np.linalg.norm(positions[pair[0]] - positions[pair[1]]))

    variants: list[StructureVariant] = []
    for first, second in pairs[: options["max_count"]]:
        variant = atoms.copy()
        symbols = (variant[first].symbol, variant[second].symbol)
        for index in sorted((first, second), reverse=True):
            del variant[index]
        variants.append(
            StructureVariant(
                f"double_vacancy_{symbols[0]}{first:06d}_{symbols[1]}{second:06d}",
                variant,
                f"double vacancy: remove atoms {first} and {second}",
            )
        )
    return variants


def _line_defects(atoms, settings: Any) -> list[StructureVariant]:
    options = _normalize_defect_options(settings, default_max=4)
    if not options["enabled"]:
        return []

    coordinate_axis = int(options.get("coordinate_axis", 1))
    tolerance = float(options.get("tolerance", 0.04))
    if coordinate_axis not in {0, 1, 2}:
        raise ValueError("line_defects.coordinate_axis must be 0, 1, or 2")
    if tolerance <= 0:
        raise ValueError("line_defects.tolerance must be positive")

    candidates = _candidate_indices(atoms, options)
    scaled = atoms.get_scaled_positions(wrap=True)
    rows: dict[int, list[int]] = {}
    for index in candidates:
        row_key = int(round(scaled[index][coordinate_axis] / tolerance))
        rows.setdefault(row_key, []).append(index)

    variants: list[StructureVariant] = []
    ordered_rows = sorted(rows.values(), key=lambda row: (-len(row), row[0]))
    for line_index, row in enumerate(ordered_rows[: options["max_count"]]):
        variant = atoms.copy()
        for index in sorted(row, reverse=True):
            del variant[index]
        variants.append(
            StructureVariant(
                f"line_defect_axis{coordinate_axis}_{line_index:03d}",
                variant,
                f"line defect: remove {len(row)} atom(s) along row {line_index}",
            )
        )
    return variants


def _normalize_defect_options(settings: Any, *, default_max: int) -> dict[str, Any]:
    if settings in (None, False):
        return {"enabled": False, "max_count": 0}
    if settings is True:
        return {"enabled": True, "max_count": default_max}
    if not isinstance(settings, dict):
        raise ValueError("defect settings must be a mapping or boolean")
    options = dict(settings)
    options["enabled"] = bool(options.get("enabled", True))
    options["max_count"] = int(options.get("max_count", default_max))
    if options["max_count"] < 0:
        raise ValueError("defect max_count can not be negative")
    return options


def _candidate_indices(atoms, options: dict[str, Any]) -> list[int]:
    explicit_indices = options.get("indices")
    if explicit_indices is not None:
        return [int(index) for index in explicit_indices]

    elements = options.get("elements")
    if elements is None:
        return list(range(len(atoms)))
    allowed = {str(element) for element in elements}
    return [index for index, atom in enumerate(atoms) if atom.symbol in allowed]
