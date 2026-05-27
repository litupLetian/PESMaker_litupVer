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
"""Tests for PESMaker configuration parsing."""

from pesmaker.config.schema import PESMakerConfig


def test_config_from_mapping_minimal():
    """Minimal configs should get sensible default workflow engines."""
    config = PESMakerConfig.from_mapping(
        {
            "project": "demo",
            "structures": [{"path": "POSCAR"}],
        }
    )

    assert config.project == "demo"
    assert len(config.structures) == 1
    assert config.labeling.engine == "vasp"
    assert config.training.engine == "nep"


def test_dataset_split_must_sum_to_one():
    """Dataset split ratios must be normalized."""
    try:
        PESMakerConfig.from_mapping(
            {
                "project": "demo",
                "structures": [{"path": "POSCAR"}],
                "dataset": {"split": [0.8, 0.1, 0.2]},
            }
        )
    except ValueError as exc:
        assert "sum to 1.0" in str(exc)
    else:
        raise AssertionError("invalid split should fail")


def test_training_model_alias_selects_engine():
    """The concise `training.model` key should select the training engine."""
    config = PESMakerConfig.from_mapping(
        {
            "project": "demo",
            "structures": [{"path": "POSCAR"}],
            "training": {"model": "mace", "device": "cuda"},
        }
    )

    assert config.training.engine == "mace"
    assert config.training.options == {"device": "cuda"}


def test_generation_accepts_surface_defects_and_job_templates():
    """Extended workflow sections should remain structured config options."""
    config = PESMakerConfig.from_mapping(
        {
            "project": "demo",
            "structures": ["POSCAR"],
            "generation": {
                "supercell": [3, 3, 1],
                "surface": {"vacuum": 30, "axis": 2},
                "defects": {
                    "single_vacancies": {"elements": ["Te"], "max_count": 2}
                },
            },
            "jobs": {
                "machine": "cluster-a",
                "sbatch_templates": {"labeling": "templates/vasp.sh"},
            },
        }
    )

    assert config.generation.supercell == (3, 3, 1)
    assert config.generation.surface["vacuum"] == 30
    assert config.generation.defects["single_vacancies"]["elements"] == ["Te"]
    assert config.jobs.engine == "cluster-a"
    assert config.jobs.options["sbatch_templates"]["labeling"] == "templates/vasp.sh"


def test_structures_accept_simple_path_list():
    """Users can list structure paths directly without `{path: ...}`."""
    config = PESMakerConfig.from_mapping(
        {
            "project": "demo",
            "structures": ["Te-mp-19.cif", "Te-mp-23.cif"],
        }
    )

    assert [item.path.name for item in config.structures] == [
        "Te-mp-19.cif",
        "Te-mp-23.cif",
    ]


def test_structures_accept_include_patterns(tmp_path, monkeypatch):
    """Users can collect many structures with an `include` glob pattern.

    Args:
        tmp_path: Pytest temporary directory used as a fake project root.
        monkeypatch: Pytest fixture used to run glob expansion from `tmp_path`.
    """
    structure_dir = tmp_path / "initial_structures"
    structure_dir.mkdir()
    (structure_dir / "a.cif").write_text("", encoding="utf-8")
    (structure_dir / "b.cif").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = PESMakerConfig.from_mapping(
        {
            "project": "demo",
            "structures": {"include": ["initial_structures/*.cif"]},
        }
    )

    assert [item.path.as_posix() for item in config.structures] == [
        "initial_structures/a.cif",
        "initial_structures/b.cif",
    ]
