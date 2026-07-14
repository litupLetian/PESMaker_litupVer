# Copyright 2026 Ting Liang and PESMaker development team
# This file is part of PESMaker.
#
# PESMaker is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Tests for submission script rendering and literal template copies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pesmaker.config.schema import PESMakerConfig
from pesmaker.jobs.scripts import _write_submit_script
from pesmaker.jobs.submit import submit_jobs


def _config(template: Path | None, *, copy_sub_file: object = False):
    jobs: dict[str, object] = {
        "copy_sub_file": copy_sub_file,
        "cores_cpu": 36,
    }
    if template is not None:
        jobs["sub_file"] = str(template)
    return PESMakerConfig.from_mapping(
        {
            "project": "submit_script_test",
            "labeling": {"engine": "vasp"},
            "jobs": jobs,
        }
    )


def test_scf_submit_template_can_be_copied_verbatim(tmp_path):
    """The opt-in copy mode must not render or normalize template bytes."""
    template = tmp_path / "template.sh"
    template_bytes = (
        b"#!/bin/bash\r\n"
        b"#SBATCH --job-name=keep-this-name\r\n"
        b"#SBATCH --ntasks=7\r\n"
        b"{command}\r\n"
    )
    template.write_bytes(template_bytes)
    workdir = tmp_path / "labeling" / "selected_000001"
    workdir.mkdir(parents=True)

    path = _write_submit_script(
        _config(template, copy_sub_file=True),
        workdir,
        stage="labeling",
        command="/new/path/vasp_std",
    )

    assert path == workdir / "submit.sh"
    assert path.read_bytes() == template_bytes


def test_scf_submit_template_uses_existing_rendering_by_default(tmp_path):
    """Omitting copy_sub_file must preserve the original rendering behavior."""
    template = tmp_path / "template.sh"
    template.write_text(
        "#!/bin/bash\n#SBATCH --job-name=old-name\n{command}\n",
        encoding="utf-8",
    )
    workdir = tmp_path / "labeling" / "selected_000001"
    workdir.mkdir(parents=True)

    path = _write_submit_script(
        _config(template),
        workdir,
        stage="labeling",
        command="/new/path/vasp_std",
    )
    text = path.read_text(encoding="utf-8")

    assert "#SBATCH --job-name=labeling_sel000001" in text
    assert "mpirun -np 36 /new/path/vasp_std" in text


def test_scf_submit_copy_requires_a_template(tmp_path):
    """Copy mode should fail clearly instead of falling back to generated text."""
    workdir = tmp_path / "labeling" / "selected_000001"
    workdir.mkdir(parents=True)

    with pytest.raises(ValueError, match="copy_sub_file requires"):
        _write_submit_script(
            _config(None, copy_sub_file=True),
            workdir,
            stage="labeling",
            command="vasp_std",
        )


def test_scf_submit_copy_switch_must_be_boolean(tmp_path):
    """String values should not silently enable or disable copy mode."""
    template = tmp_path / "template.sh"
    template.write_text("#!/bin/bash\n", encoding="utf-8")
    workdir = tmp_path / "labeling" / "selected_000001"
    workdir.mkdir(parents=True)

    with pytest.raises(ValueError, match="must be true or false"):
        _write_submit_script(
            _config(template, copy_sub_file="true"),
            workdir,
            stage="labeling",
            command="vasp_std",
        )


def test_scf_submit_refresh_respects_verbatim_copy_mode(tmp_path):
    """Submitting a pending SCF job must not render a copied template later."""
    template = tmp_path / "template.sh"
    template_bytes = b"#!/bin/bash\r\n#SBATCH -J unchanged\r\n{command}\r\n"
    template.write_bytes(template_bytes)
    output_dir = tmp_path / "labeling"
    workdir = output_dir / "selected_000001"
    workdir.mkdir(parents=True)
    (workdir / "submit.sh").write_text("old script\n", encoding="utf-8")
    (output_dir / "labeling_manifest.jsonl").write_text(
        json.dumps({"workdir": str(workdir)}) + "\n",
        encoding="utf-8",
    )
    config = PESMakerConfig.from_mapping(
        {
            "project": "submit_refresh_test",
            "labeling": {
                "engine": "vasp",
                "output_dir": str(output_dir),
                "command": "/new/path/vasp_std",
            },
            "jobs": {
                "sub_file": str(template),
                "copy_sub_file": True,
                "cores_cpu": 36,
            },
        }
    )

    submit_jobs(config, dry_run=True)

    assert (workdir / "submit.sh").read_bytes() == template_bytes
    log = (output_dir / "scf_submitted_jobs.txt").read_text(encoding="utf-8")
    assert "REFRESHED submit script" in log
