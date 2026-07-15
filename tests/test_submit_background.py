# Copyright 2026 Ting Liang and PESMaker development team
# This file is part of PESMaker.
"""Tests for detached whole-stage submission."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pesmaker.cli import main
from pesmaker.config.io import load_config
from pesmaker.jobs.submit import (
    BackgroundSubmitProcess,
    SubmissionJobError,
    start_background_submit,
    submit_jobs,
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


def _write_prepared_jobs(output_dir: Path, count: int) -> list[Path]:
    output_dir.mkdir(parents=True)
    workdirs = []
    records = []
    for index in range(count):
        workdir = output_dir / f"calc_{index:06d}"
        workdir.mkdir()
        script = workdir / "submit.sh"
        script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        workdirs.append(workdir)
        records.append(
            {
                "workdir": str(workdir),
                "submit_script": str(script),
            }
        )
    (output_dir / "labeling_manifest.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    return workdirs


def test_bash_submit_reports_and_flushes_each_completed_job(
    tmp_path, monkeypatch, capsys
):
    """Each synchronous Bash job should be visible before the next one runs."""
    output_dir = tmp_path / "labeling"
    workdirs = _write_prepared_jobs(output_dir, 2)
    config_path = tmp_path / "run.yaml"
    _write_config(config_path, output_dir)
    monotonic_values = iter((10.0, 15.0, 20.0, 27.0))
    calls = []

    def fake_run(submit_command, script):
        calls.append(script.parent)
        current_log = (output_dir / "scf_submitted_jobs.txt").read_text(
            encoding="utf-8"
        )
        assert f" STARTED   {len(calls)}/2  {script.parent}" in current_log
        if len(calls) == 2:
            assert f" COMPLETED 1/2  {workdirs[0]}" in current_log
        return f"finished {script.parent.name}"

    monkeypatch.setattr("pesmaker.jobs.submit.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("pesmaker.jobs.submit._run_submit_command", fake_run)

    result = submit_jobs(load_config(config_path))
    output = capsys.readouterr().out
    log_text = result.files[0].read_text(encoding="utf-8")

    assert calls == workdirs
    assert f" STARTED   1/2  {workdirs[0]}" in output
    assert f" COMPLETED 1/2  {workdirs[0]}  elapsed=00:00:05" in output
    assert f" STARTED   2/2  {workdirs[1]}" in output
    assert f" COMPLETED 2/2  {workdirs[1]}  elapsed=00:00:07" in output
    assert f" STARTED   1/2  {workdirs[0]}" in log_text
    assert f" COMPLETED 1/2  {workdirs[0]}  elapsed=00:00:05" in log_text
    assert log_text.index("COMPLETED 1/2") < log_text.index("STARTED   2/2")


def test_bash_submit_reports_failure_before_stopping(
    tmp_path, monkeypatch, capsys
):
    """A failed foreground script should be flushed before the error escapes."""
    output_dir = tmp_path / "labeling"
    workdir = _write_prepared_jobs(output_dir, 1)[0]
    config_path = tmp_path / "run.yaml"
    _write_config(config_path, output_dir)
    monotonic_values = iter((100.0, 103.0))

    def fake_run(submit_command, script):
        raise subprocess.CalledProcessError(7, ["bash", script.name])

    monkeypatch.setattr("pesmaker.jobs.submit.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("pesmaker.jobs.submit._run_submit_command", fake_run)

    with pytest.raises(SubmissionJobError) as caught:
        submit_jobs(load_config(config_path))

    output = capsys.readouterr().out
    log_text = (output_dir / "scf_submitted_jobs.txt").read_text(
        encoding="utf-8"
    )
    expected = f" FAILED    1/1  {workdir}  elapsed=00:00:03"
    assert expected in output
    assert expected in log_text
    assert caught.value.returncode == 7
    assert caught.value.workdir == workdir
    assert caught.value.remaining_jobs == 0


def test_cli_formats_killed_bash_job_without_traceback(
    tmp_path, monkeypatch, capsys
):
    """A signal-style shell status should become a concise stop summary."""
    output_dir = tmp_path / "labeling"
    workdirs = _write_prepared_jobs(output_dir, 2)
    config_path = tmp_path / "run.yaml"
    _write_config(config_path, output_dir)
    monotonic_values = iter((200.0, 205.0))

    def fake_run(submit_command, script):
        raise subprocess.CalledProcessError(143, ["bash", script.name])

    monkeypatch.setattr(
        "pesmaker.jobs.submit.time.monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr("pesmaker.jobs.submit._run_submit_command", fake_run)

    assert main(["submit", str(config_path)]) == 2
    captured = capsys.readouterr()

    assert f" FAILED    1/2  {workdirs[0]}  elapsed=00:00:05" in captured.out
    assert "SCF serial submission stopped." in captured.err
    assert f"Failed job       : {workdirs[0]}" in captured.err
    assert "Exit status      : 143" in captured.err
    assert "Termination      : SIGTERM" in captured.err
    assert "Remaining jobs   : 1 not started" in captured.err
    assert "Traceback" not in captured.err
    assert "CalledProcessError" not in captured.err
