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
"""Stage setup helpers for sampling, labeling, dataset, and training workflows."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import Any

import numpy as np

from pesmaker.config.schema import PESMakerConfig
from pesmaker.structures import load_structure, write_structure


DEFAULT_GPUMD_RUN_IN = """potential      nep89_20250409.txt
velocity       300

ensemble       npt_scr 300 300 100 0 0 0 20 20 100 1000
time_step      1
dump_thermo    1000
dump_position  3000
run            3000000
"""

DEFAULT_INCAR = """SYSTEM = PESMaker single point
ENCUT = 520
EDIFF = 1E-6
IBRION = -1
NSW = 0
ISMEAR = 0
SIGMA = 0.05
LREAL = Auto
"""

DEFAULT_NEP_IN = """type 1 Te
version 4
prediction 0
potential nep.txt
"""


@dataclass(frozen=True)
class StageResult:
    """Summary for a prepared or collected workflow stage."""

    output_dir: Path
    files: tuple[Path, ...]
    message: str


def setup_sampling(config: PESMakerConfig) -> StageResult:
    """Prepare MD sampling folders for GPUMD or future engines."""
    engine = config.sampling.engine.lower()
    output_dir = _section_output_dir(config, config.sampling.options, "sampling")
    output_dir.mkdir(parents=True, exist_ok=True)

    records = _load_input_records(config, config.sampling.options)
    run_in = _read_optional_file(
        config.sampling.options.get("run_in"),
        default=DEFAULT_GPUMD_RUN_IN,
    )
    files: list[Path] = []
    manifest_path = output_dir / "sampling_manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for index, record in enumerate(records):
            stage_dir = output_dir / f"md_{index:06d}"
            stage_dir.mkdir(parents=True, exist_ok=True)
            structure_path = stage_dir / "model.xyz"
            atoms = load_structure(record["path"])
            write_structure(atoms, structure_path, fmt="extxyz")
            run_in_path = stage_dir / "run.in"
            run_in_path.write_text(run_in, encoding="utf-8")
            command = _sampling_command(config)
            submit_path = _write_submit_script(
                config,
                stage_dir,
                stage="sampling",
                command=command,
            )
            files.extend([structure_path, run_in_path, submit_path])
            manifest.write(
                json.dumps(
                    {
                        "index": index,
                        "engine": engine,
                        "source": record["path"],
                        "workdir": str(stage_dir),
                        "run_in": str(run_in_path),
                    }
                )
                + "\n"
            )
    files.append(manifest_path)
    return StageResult(output_dir, tuple(files), f"Prepared {len(records)} MD job(s)")


def select_sampling_frames(config: PESMakerConfig) -> StageResult:
    """Select representative MD frames with farthest point sampling."""
    options = config.sampling.options.get("selection", {})
    if not isinstance(options, dict):
        raise ValueError("sampling.selection must be a mapping")
    pattern = str(options.get("trajectory_pattern", "runs/*/sampling/**/movie.xyz"))
    output_dir = Path(str(options.get("output_dir", "selected")))
    min_distance = float(options.get("min_distance", 0.0))
    max_count = options.get("max_count")
    max_count = int(max_count) if max_count is not None else None

    frames = _read_trajectory_frames(pattern)
    features = _structure_features(frames)
    selected_indices = _farthest_point_indices(
        features,
        min_distance=min_distance,
        max_count=max_count,
    )
    selected = [frames[index] for index in selected_indices]

    output_dir.mkdir(parents=True, exist_ok=True)
    selected_path = output_dir / "selected.xyz"
    _write_extxyz_many(selected_path, selected)
    selected_files = []
    manifest_path = output_dir / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for index, (frame_index, atoms) in enumerate(zip(selected_indices, selected)):
            frame_path = output_dir / f"selected_{index:06d}.xyz"
            write_structure(atoms, frame_path, fmt="extxyz")
            selected_files.append(frame_path)
            manifest.write(
                json.dumps(
                    {
                        "index": index,
                        "source_frame": frame_index,
                        "path": str(frame_path),
                    }
                )
                + "\n"
            )
    return StageResult(
        output_dir,
        (selected_path, *selected_files, manifest_path),
        f"Selected {len(selected)} of {len(frames)} MD frame(s)",
    )


def setup_labeling(config: PESMakerConfig) -> StageResult:
    """Prepare VASP single-point calculation folders."""
    output_dir = _section_output_dir(config, config.labeling.options, "labeling")
    output_dir.mkdir(parents=True, exist_ok=True)
    records = _load_input_records(config, config.labeling.options)
    incar = _read_optional_file(config.labeling.options.get("incar"), default=DEFAULT_INCAR)
    files: list[Path] = []
    manifest_path = output_dir / "labeling_manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for index, record in enumerate(records):
            calc_dir = output_dir / f"calc_{index:06d}"
            calc_dir.mkdir(parents=True, exist_ok=True)
            poscar_path = calc_dir / "POSCAR"
            atoms = load_structure(record["path"])
            write_structure(atoms, poscar_path, fmt="vasp")
            incar_path = calc_dir / "INCAR"
            incar_path.write_text(incar, encoding="utf-8")
            _copy_optional_templates(config.labeling.options, calc_dir)
            submit_path = _write_submit_script(
                config,
                calc_dir,
                stage="labeling",
                command=str(config.labeling.options.get("command", "vasp_std")),
            )
            files.extend([poscar_path, incar_path, submit_path])
            manifest.write(
                json.dumps(
                    {
                        "index": index,
                        "engine": config.labeling.engine,
                        "source": record["path"],
                        "workdir": str(calc_dir),
                    }
                )
                + "\n"
            )
    files.append(manifest_path)
    return StageResult(
        output_dir,
        tuple(files),
        f"Prepared {len(records)} single-point job(s)",
    )


def collect_labeled_dataset(config: PESMakerConfig) -> StageResult:
    """Collect completed single-point calculations into `train.xyz`."""
    output_dir = _section_output_dir(config, config.dataset.__dict__, "dataset")
    output_dir.mkdir(parents=True, exist_ok=True)
    default_pattern = Path("runs") / config.project / "labeling" / "**" / "OUTCAR"
    pattern = str(config.labeling.options.get("outcar_pattern", default_pattern))
    output_path = Path(
        str(config.labeling.options.get("dataset_path", output_dir / "train.xyz"))
    )
    outputs = [Path(path) for path in sorted(glob(pattern, recursive=True))]
    if not outputs:
        raise ValueError(f"no VASP outputs matched pattern: {pattern}")

    frames = []
    for output in outputs:
        frames.extend(_read_trajectory_frames(str(output)))
    _write_extxyz_many(output_path, frames)
    return StageResult(
        output_dir,
        (output_path,),
        f"Collected {len(frames)} labeled frame(s) into {output_path}",
    )


def setup_training(config: PESMakerConfig) -> StageResult:
    """Prepare potential training inputs and a submission script."""
    output_dir = _section_output_dir(config, config.training.options, "training")
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = Path(str(config.training.options.get("dataset", "train.xyz")))
    target_dataset = output_dir / dataset_path.name
    if dataset_path.exists():
        shutil.copy2(dataset_path, target_dataset)

    if config.training.engine.lower() == "nep":
        input_name = "nep.in"
        default_input = DEFAULT_NEP_IN
        command = str(config.training.options.get("command", "nep"))
    else:
        input_name = "train.in"
        default_input = "# Add trainer-specific options here.\n"
        command = str(config.training.options.get("command", config.training.engine))
    input_text = _read_optional_file(
        config.training.options.get("input"),
        default=default_input,
    )
    input_path = output_dir / input_name
    input_path.write_text(input_text, encoding="utf-8")
    submit_path = _write_submit_script(
        config,
        output_dir,
        stage="training",
        command=command,
    )
    return StageResult(
        output_dir,
        tuple(path for path in (target_dataset, input_path, submit_path) if path.exists()),
        f"Prepared training folder for {config.training.engine}",
    )


def _section_output_dir(
    config: PESMakerConfig,
    options: dict[str, Any],
    leaf: str,
) -> Path:
    value = options.get("output_dir")
    return Path(str(value)) if value else Path("runs") / config.project / leaf


def _load_input_records(
    config: PESMakerConfig,
    options: dict[str, Any],
) -> list[dict[str, str]]:
    manifest = options.get("input_manifest")
    if manifest:
        return _read_manifest(Path(str(manifest)))
    generation_dir = (
        config.generation.output_dir or Path("runs") / config.project / "generated"
    )
    manifest_path = generation_dir / "manifest.jsonl"
    if manifest_path.exists():
        return _read_manifest(manifest_path)
    paths = sorted(generation_dir.rglob("structure_*.*"))
    if not paths:
        raise ValueError(f"no generated structures found in {generation_dir}")
    return [{"path": str(path)} for path in paths]


def _read_manifest(path: Path) -> list[dict[str, str]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records.append({"path": str(record["path"]), **record})
    return records


def _read_optional_file(value: Any, *, default: str) -> str:
    if value:
        return Path(str(value)).read_text(encoding="utf-8")
    return default


def _sampling_command(config: PESMakerConfig) -> str:
    if config.sampling.engine.lower() == "gpumd":
        command = config.sampling.options.get("command")
        if command:
            return str(command)
        gpumd_dir = config.sampling.options.get("gpumd_dir")
        if gpumd_dir:
            return str(Path(str(gpumd_dir)) / "gpumd")
        return "gpumd"
    return str(config.sampling.options.get("command", config.sampling.engine))


def _write_submit_script(
    config: PESMakerConfig,
    workdir: Path,
    *,
    stage: str,
    command: str,
) -> Path:
    template_path = _job_template_path(config, stage)
    job_name = f"{config.project}-{stage}"
    if template_path:
        text = template_path.read_text(encoding="utf-8").format(
            command=command,
            job_name=job_name,
            workdir=workdir,
        )
    else:
        text = _default_submit_script(command=command, job_name=job_name)
    path = workdir / "submit.sh"
    path.write_text(text, encoding="utf-8")
    return path


def _job_template_path(config: PESMakerConfig, stage: str) -> Path | None:
    templates = config.jobs.options.get("sbatch_templates", {})
    if isinstance(templates, dict) and templates.get(stage):
        return Path(str(templates[stage]))
    template = config.jobs.options.get("sbatch_template")
    return Path(str(template)) if template else None


def _default_submit_script(*, command: str, job_name: str) -> str:
    return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --time=24:00:00

set -euo pipefail
cd "$(dirname "$0")"
{command}
"""


def _copy_optional_templates(options: dict[str, Any], calc_dir: Path) -> None:
    for key in ("potcar", "kpoints", "template_dir"):
        value = options.get(key)
        if not value:
            continue
        source = Path(str(value))
        if source.is_dir():
            for item in source.iterdir():
                if item.is_file():
                    shutil.copy2(item, calc_dir / item.name)
        elif source.exists():
            shutil.copy2(source, calc_dir / source.name.upper())


def _read_trajectory_frames(pattern: str):
    try:
        from ase.io import read
    except ImportError as exc:
        raise RuntimeError("Trajectory selection requires ASE") from exc

    paths = [Path(path) for path in sorted(glob(pattern, recursive=True))]
    if not paths and Path(pattern).exists():
        paths = [Path(pattern)]
    frames = []
    for path in paths:
        items = read(path, index=":")
        if not isinstance(items, list):
            items = [items]
        frames.extend(items)
    if not frames:
        raise ValueError(f"no trajectory frames matched pattern: {pattern}")
    return frames


def _write_extxyz_many(path: Path, frames) -> None:
    try:
        from ase.io import write
    except ImportError as exc:
        raise RuntimeError("Writing extxyz requires ASE") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, frames, format="extxyz")


def _structure_features(frames) -> np.ndarray:
    raw = []
    max_length = 0
    for atoms in frames:
        numbers = atoms.get_atomic_numbers().reshape(-1, 1)
        scaled = atoms.get_scaled_positions(wrap=True)
        feature = np.concatenate([numbers, scaled], axis=1).reshape(-1)
        feature = np.concatenate([np.array([len(atoms)]), feature])
        raw.append(feature)
        max_length = max(max_length, len(feature))
    features = np.zeros((len(raw), max_length), dtype=float)
    for index, feature in enumerate(raw):
        features[index, : len(feature)] = feature
    return features


def _farthest_point_indices(
    features: np.ndarray,
    *,
    min_distance: float,
    max_count: int | None,
) -> list[int]:
    selected = [0]
    distances = np.linalg.norm(features - features[0], axis=1)
    while True:
        next_index = int(np.argmax(distances))
        next_distance = float(distances[next_index])
        if next_index in selected or next_distance < min_distance:
            break
        if max_count is not None and len(selected) >= max_count:
            break
        selected.append(next_index)
        new_distances = np.linalg.norm(features - features[next_index], axis=1)
        distances = np.minimum(distances, new_distances)
    return selected
