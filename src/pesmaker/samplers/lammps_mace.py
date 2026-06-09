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

"""LAMMPS MLIAP/MACE sampling setup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pesmaker.artifacts import _load_input_records, _section_output_dir
from pesmaker.config.schema import PESMakerConfig
from pesmaker.jobs.scripts import _write_submit_script
from pesmaker.results import StageResult
from pesmaker.samplers.gpumd import (
    SamplingCondition,
    _format_temperature,
    _sampling_conditions,
)
from pesmaker.structures import load_structure

DEFAULT_MACE_RUN_IN_NAME = "in.run_mace_npt"

DEFAULT_MACE_TRAJECTORY = "mace.lammpstrj"

DEFAULT_MACE_RUN_IN = """units         metal
dimension     3
boundary      p p p
atom_style    atomic
atom_modify   map yes
newton        on

variable      ts         equal 0.001
variable      Tstart     equal {temperature_start}
variable      Tstop      equal {temperature_end}
variable      Tdamp      equal ${ts}*100
variable      Pdamp      equal ${ts}*1000
variable      P_0        equal 0.0
variable      dt_dump    equal 3000
variable      dt_thermo  equal 1000

read_data     {data_file}

pair_style    mliap unified {potential} 0
pair_coeff    * * {elements}

dump          myDump all custom ${dt_dump} {trajectory} id element x y z
dump_modify   myDump sort id element {elements}

thermo_style  custom step time cpu pe ke etotal temp press vol density
thermo        ${dt_thermo}
thermo_modify lost ignore

velocity      all create ${Tstart} 123456 mom yes rot yes dist gaussian
fix           MD all npt temp ${Tstart} ${Tstop} ${Tdamp} &
              x ${P_0} ${P_0} ${Pdamp} &
              y ${P_0} ${P_0} ${Pdamp} &
              z ${P_0} ${P_0} ${Pdamp} &
              couple none

timestep      ${ts}
run           3000000
"""


def setup_sampling(config: PESMakerConfig) -> StageResult:
    """Prepare LAMMPS-MACE sampling folders."""
    engine = config.sampling.engine.lower()
    options = config.sampling.options
    output_dir = _section_output_dir(config, options, "sampling")
    output_dir.mkdir(parents=True, exist_ok=True)

    records = _load_input_records(config, options)
    conditions = _sampling_conditions(options)
    run_template = _mace_run_template(options)
    run_in_name = _mace_run_in_name(options)
    potential = _mace_potential(options)
    trajectory = str(options.get("trajectory", DEFAULT_MACE_TRAJECTORY))

    files: list[Path] = []
    manifest_path = output_dir / "sampling_manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        job_index = 0
        for record_index, record in enumerate(records):
            for condition in conditions:
                stage_dir = output_dir / f"md_{record_index:06d}_{condition.name}"
                stage_dir.mkdir(parents=True, exist_ok=True)
                atoms = load_structure(record["path"])
                elements = _first_seen_elements(atoms)

                data_path = stage_dir / "data.in"
                _write_lammps_data(atoms, data_path, elements)

                run_in_path = stage_dir / run_in_name
                run_in_path.write_text(
                    _render_mace_run_in(
                        run_template,
                        condition,
                        data_file=data_path.name,
                        potential=potential,
                        elements=elements,
                        trajectory=trajectory,
                    ),
                    encoding="utf-8",
                )

                submit_path = _write_submit_script(
                    config,
                    stage_dir,
                    stage="sampling",
                    command=_mace_command(options, run_in_name),
                )
                files.extend((data_path, run_in_path, submit_path))
                manifest.write(
                    json.dumps(
                        {
                            "index": job_index,
                            "engine": engine,
                            "source": record["path"],
                            "condition": condition.name,
                            "potential": potential,
                            "elements": elements,
                            "temperature_start": condition.start,
                            "temperature_end": condition.end,
                            "workdir": str(stage_dir),
                            "data_file": str(data_path),
                            "run_in": str(run_in_path),
                            "trajectory": str(stage_dir / trajectory),
                            "submit_script": str(submit_path),
                        }
                    )
                    + "\n"
                )
                job_index += 1
    files.append(manifest_path)
    job_count = len(records) * len(conditions)
    return StageResult(
        output_dir,
        tuple(files),
        f"Prepared {job_count} MACE sampling job(s)",
    )


def _mace_run_template(options: dict[str, Any]) -> str:
    run_in = options.get("run_in")
    if run_in:
        return Path(str(run_in)).read_text(encoding="utf-8")
    return DEFAULT_MACE_RUN_IN


def _mace_run_in_name(options: dict[str, Any]) -> str:
    run_in = options.get("run_in")
    if run_in:
        return Path(str(run_in)).name
    return DEFAULT_MACE_RUN_IN_NAME


def _mace_potential(options: dict[str, Any]) -> str:
    raw_potential = options.get("potential")
    if not raw_potential:
        raise ValueError("sampling.potential is required for MACE sampling")
    potential = Path(str(raw_potential))
    if potential.exists():
        return str(potential.resolve())
    return str(raw_potential)


def _mace_command(options: dict[str, Any], run_in_name: str) -> str:
    command = options.get("command")
    if command:
        return str(command)
    return f"lmp -in {run_in_name}"


def _render_mace_run_in(
    template: str,
    condition: SamplingCondition,
    *,
    data_file: str,
    potential: str,
    elements: list[str],
    trajectory: str,
) -> str:
    values = {
        "data_file": data_file,
        "potential": potential,
        "model": potential,
        "elements": " ".join(elements),
        "temperature": _format_temperature(condition.start),
        "temperature_start": _format_temperature(condition.start),
        "temperature_end": _format_temperature(condition.end),
        "trajectory": trajectory,
    }
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def _first_seen_elements(atoms) -> list[str]:
    elements: list[str] = []
    for symbol in atoms.get_chemical_symbols():
        if symbol not in elements:
            elements.append(symbol)
    return elements


def _write_lammps_data(atoms, path: Path, elements: list[str]) -> None:
    try:
        from ase.io.lammpsdata import write_lammps_data
    except ImportError as exc:
        raise RuntimeError("Writing LAMMPS data files requires ASE") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        write_lammps_data(
            handle,
            atoms,
            specorder=elements,
            masses=True,
            atom_style="atomic",
            units="metal",
        )
