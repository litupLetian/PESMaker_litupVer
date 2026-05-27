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
"""Structure generation workflow for supercells and perturbations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pesmaker.config.schema import PESMakerConfig
from pesmaker.structures import (
    PerturbationSettings,
    apply_surface_settings,
    generate_defect_variants,
    load_structure,
    make_supercell,
    perturb_structures,
    write_structure,
)


@dataclass(frozen=True)
class GeneratedStructure:
    """Metadata for one generated structure file.

    Attributes:
        source: Original input structure path.
        path: Generated structure file path.
        variant: Structural variant name, such as `pristine` or a defect name.
        variant_description: Human-readable variant description.
        index: Zero-based index within the source structure's output folder.
        atom_count: Number of atoms in the generated structure.
    """

    source: Path
    path: Path
    index: int
    atom_count: int
    variant: str = "pristine"
    variant_description: str = "pristine"


@dataclass(frozen=True)
class GenerateResult:
    """Summary returned after structure generation completes.

    Attributes:
        output_dir: Root directory containing generated structures.
        structures: Metadata for every generated structure.
    """

    output_dir: Path
    structures: tuple[GeneratedStructure, ...]


def generate_structures(config: PESMakerConfig) -> GenerateResult:
    """Generate perturbed structures from every configured input structure.

    Args:
        config: Validated PESMaker configuration.

    Returns:
        Generation result containing the output directory and generated-file
        metadata.

    Raises:
        RuntimeError: If ASE is unavailable for structure IO.
        ValueError: If output format or perturbation settings are invalid.
        OSError: If output folders or files cannot be written.
    """
    output_dir = (
        config.generation.output_dir or Path("runs") / config.project / "generated"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = PerturbationSettings.from_mapping(config.generation.perturb)
    output_format = str(config.generation.perturb.get("format", "vasp")).lower()
    ase_format, suffix = _resolve_output_format(output_format)

    generated: list[GeneratedStructure] = []
    structure_dirs = _structure_output_dirs(config, output_dir)
    manifest_path = output_dir / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for input_index, structure in enumerate(config.structures):
            atoms = load_structure(structure.path)
            supercell_atoms = make_supercell(atoms, config.generation.supercell)
            base_atoms = apply_surface_settings(
                supercell_atoms, config.generation.surface
            )
            variants = generate_defect_variants(base_atoms, config.generation.defects)
            structure_dir = structure_dirs[input_index]
            structure_dir.mkdir(parents=True, exist_ok=True)
            use_variant_dirs = bool(config.generation.defects)
            for variant in variants:
                variant_dir = (
                    structure_dir / variant.name if use_variant_dirs else structure_dir
                )
                variant_dir.mkdir(parents=True, exist_ok=True)
                for structure_index, perturbed in enumerate(
                    perturb_structures(variant.atoms, settings)
                ):
                    output_path = (
                        variant_dir / f"structure_{structure_index:06d}.{suffix}"
                    )
                    write_structure(perturbed, output_path, fmt=ase_format)
                    item = GeneratedStructure(
                        source=structure.path,
                        path=output_path,
                        variant=variant.name,
                        variant_description=variant.description,
                        index=structure_index,
                        atom_count=len(perturbed),
                    )
                    generated.append(item)
                    manifest.write(json.dumps(_manifest_record(item)) + "\n")

    return GenerateResult(output_dir=output_dir, structures=tuple(generated))


def _structure_output_dirs(
    config: PESMakerConfig,
    output_dir: Path,
) -> tuple[Path, ...]:
    """Build one unique output directory for each input structure.

    Args:
        config: Validated PESMaker configuration.
        output_dir: Root generation output directory.

    Returns:
        Tuple of output directories aligned with `config.structures`. Duplicate
        structure stems receive numeric suffixes such as `_2`.
    """
    seen: dict[str, int] = {}
    paths: list[Path] = []
    for structure in config.structures:
        stem = structure.path.stem
        seen[stem] = seen.get(stem, 0) + 1
        folder = stem if seen[stem] == 1 else f"{stem}_{seen[stem]}"
        paths.append(output_dir / folder)
    return tuple(paths)


def _resolve_output_format(name: str) -> tuple[str, str]:
    """Map a user-facing output format to ASE format and file suffix.

    Args:
        name: User-facing format name from `generation.perturb.format`.

    Returns:
        Pair of ASE writer format and file suffix.

    Raises:
        ValueError: If `name` is not a supported output format.
    """
    if name in {"vasp", "poscar"}:
        return "vasp", "vasp"
    if name in {"extxyz", "xyz"}:
        return "extxyz", "xyz"
    raise ValueError(f"unsupported generation output format: {name}")


def _manifest_record(item: GeneratedStructure) -> dict[str, str | int]:
    """Serialize generated-structure metadata for manifest.jsonl.

    Args:
        item: Generated-structure metadata object.

    Returns:
        JSON-serializable dictionary written as one manifest line.
    """
    return {
        "index": item.index,
        "source": str(item.source),
        "path": str(item.path),
        "variant": item.variant,
        "variant_description": item.variant_description,
        "atom_count": item.atom_count,
    }
