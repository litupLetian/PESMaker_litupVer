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
"""Sampling backend interfaces for foundation potentials and MLIPs."""

from __future__ import annotations

from pesmaker.config.schema import PESMakerConfig
from pesmaker.results import StageResult


def setup_sampling(config: PESMakerConfig) -> StageResult:
    """Dispatch sampling setup to the configured engine backend."""
    engine = config.sampling.engine.strip().lower().replace("_", "-")
    if engine == "gpumd":
        from pesmaker.samplers.gpumd import setup_sampling as setup_gpumd_sampling

        return setup_gpumd_sampling(config)
    if engine in {"mace", "lammps-mace"}:
        from pesmaker.samplers.lammps_mace import (
            setup_sampling as setup_lammps_mace_sampling,
        )

        return setup_lammps_mace_sampling(config)
    raise ValueError(
        "sampling.engine must be one of: gpumd, mace, lammps-mace, lammps_mace"
    )


__all__ = ["setup_sampling"]
