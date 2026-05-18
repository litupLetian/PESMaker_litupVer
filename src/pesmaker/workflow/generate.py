from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pesmaker.config.schema import PESMakerConfig
from pesmaker.structures import (
    PerturbationSettings,
    load_structure,
    make_supercell,
    perturb_structures,
    write_structure,
)


@dataclass(frozen=True)
class GeneratedStructure:
    source: Path
    path: Path
    index: int
    atom_count: int


@dataclass(frozen=True)
class GenerateResult:
    output_dir: Path
    structures: tuple[GeneratedStructure, ...]


def generate_structures(config: PESMakerConfig) -> GenerateResult:
    output_dir = (
        config.generation.output_dir or Path("runs") / config.project / "generated"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = PerturbationSettings.from_mapping(config.generation.perturb)
    output_format = str(config.generation.perturb.get("format", "vasp")).lower()
    ase_format, suffix = _resolve_output_format(output_format)

    generated: list[GeneratedStructure] = []
    manifest_path = output_dir / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        global_index = 0
        for structure in config.structures:
            atoms = load_structure(structure.path)
            supercell_atoms = make_supercell(atoms, config.generation.supercell)
            for perturbed in perturb_structures(supercell_atoms, settings):
                output_path = output_dir / f"structure_{global_index:06d}.{suffix}"
                write_structure(perturbed, output_path, fmt=ase_format)
                item = GeneratedStructure(
                    source=structure.path,
                    path=output_path,
                    index=global_index,
                    atom_count=len(perturbed),
                )
                generated.append(item)
                manifest.write(json.dumps(_manifest_record(item)) + "\n")
                global_index += 1

    return GenerateResult(output_dir=output_dir, structures=tuple(generated))


def _resolve_output_format(name: str) -> tuple[str, str]:
    if name in {"vasp", "poscar"}:
        return "vasp", "vasp"
    if name in {"extxyz", "xyz"}:
        return "extxyz", "xyz"
    raise ValueError(f"unsupported generation output format: {name}")


def _manifest_record(item: GeneratedStructure) -> dict[str, str | int]:
    return {
        "index": item.index,
        "source": str(item.source),
        "path": str(item.path),
        "atom_count": item.atom_count,
    }
