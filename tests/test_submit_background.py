# Copyright 2026 Ting Liang and PESMaker development team
# This file is part of PESMaker.
"""Tests for detached whole-stage submission."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from pesmaker.cli import main
from pesmaker.config.io import load_config
from pesmaker.jobs.submit import (
    BackgroundSubmitProcess,
    start_background_submit,
)


def _write_config(path: Path, output_dir: Path) -> None:
    path.write_text(
        f"""project: background_submit_test
labeling:
  engine: vasp
  output_dir: {output_dir.as_posix()}
jobs:
  submit_command: bash
""",
        encoding="utf-8",
    )


def test_start_background_submit_detaches_outer_pesmaker_process(
    tmp_path, monkeypatch
):
    """The worker should have no terminal streams and use a new session."""
    output_dir = tmp_path / "labeling"
    config_path = tmp_path / "run.yaml"
    _write_config(config_path, output_dir)
    calls = []

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr("pesmaker.jobs.submit.subprocess.Popen", fake_popen)

    result = start_background_submit(
        load_config(config_path), config_path, stage="scf"
    )

    assert result.pid == 4321
    assert result.log_path.parent == output_dir
    assert result.log_path.name.startswith("scf_submit_")
    assert result.log_path.suffix == ".log"
    assert result.log_path.exists()
    command, kwargs = calls[0]
    assert command == [
        sys.executable,
        "-u",
        "-m",
        "pesmaker",
        "submit",
        str(config_path.resolve()),
        "--stage",
        "scf",
    ]
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.STDOUT
    assert kwargs["close_fds"] is True
    assert Path(kwargs["stdout"].name) == result.log_path
    if os.name == "nt":
        assert kwargs["creationflags"] == (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        assert "start_new_session" not in kwargs
    else:
        assert kwargs["start_new_session"] is True
        assert "creationflags" not in kwargs


def test_cli_submit_background_starts_worker_and_returns(
    tmp_path, monkeypatch, capsys
):
    """The foreground CLI should report the detached PID and log immediately."""
    output_dir = tmp_path / "labeling"
    config_path = tmp_path / "run.yaml"
    log_path = output_dir / "scf_submit_test.log"
    _write_config(config_path, output_dir)
    calls = []

    def fake_start(config, path, *, stage):
        calls.append((config.project, path, stage))
        return BackgroundSubmitProcess(pid=9876, log_path=log_path)

    monkeypatch.setattr("pesmaker.cli.start_background_submit", fake_start)

    assert main(["submit", str(config_path), "--background"]) == 0
    output = capsys.readouterr().out

    assert calls == [("background_submit_test", config_path, "scf")]
    assert "Background submission started." in output
    assert "Process ID       : 9876" in output
    assert f"Log              : {log_path}" in output


def test_cli_rejects_background_dry_run(tmp_path, monkeypatch, capsys):
    """A preview should stay foreground instead of spawning a detached worker."""
    config_path = tmp_path / "run.yaml"
    _write_config(config_path, tmp_path / "labeling")
    started = False

    def fake_start(*args, **kwargs):
        nonlocal started
        started = True

    monkeypatch.setattr("pesmaker.cli.start_background_submit", fake_start)

    assert (
        main(
            [
                "submit",
                str(config_path),
                "--background",
                "--dry-run",
            ]
        )
        == 2
    )

    assert started is False
    assert "--background cannot be used with --dry-run" in capsys.readouterr().err
