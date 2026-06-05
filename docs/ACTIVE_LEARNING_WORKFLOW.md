# Workflow Guide

This page explains the whole PESMaker loop in plain language.

For command syntax, use the [Command Manual](commands/index.md). For small YAML
files, use [Minimal YAML Examples](examples/minimal-yaml.md).

## The Short Answer

Run:

```bash
pesmaker validate run.yaml
pesmaker next run.yaml
```

Then follow the `Next` block printed by `next`.

You normally do not run every stage command by hand. `next` runs local PESMaker
stages for you and stops only when an external scheduler job must be submitted
or finished.

By default, `next` prints only what it did and what you should do next. Use
`pesmaker status run.yaml` or `pesmaker next run.yaml --verbose` when you want
to inspect the detailed flow decision.

## What `next` Does

`next` checks two things:

1. What sections are in `run.yaml`.
2. What files already exist in the project folders.

Then it advances as far as it safely can.

```text
No generated manifest -> generate structures
Only generation configured -> write run.next.yaml and wait for settings
Sampling configured   -> prepare GPUMD folders
Need sampling jobs    -> write dry-run log and print submit command
movie.xyz exists      -> select frames
Need SCF jobs         -> write dry-run log and print submit command
OUTCAR exists         -> collect train.xyz
Training configured   -> prepare training folder and print submit command
```

If everything local is ready, one `next` run may perform several stages. If an
external result is missing, `next` waits and tells you what file it needs.
If no stage is needed, `next` reports that no PESMaker task needs to run now.

## Generate First, Configure Later

Use this when you only know the structure-generation settings now.

YAML shape:

```text
structures
generation
```

The first `next` run generates structures and writes `run.next.yaml`. Edit that
file to set VASP and submit paths, then continue:

```bash
pesmaker validate run.next.yaml
pesmaker next run.next.yaml
```

## Direct SCF Flow

Use this when structures should go directly to VASP labeling.

YAML shape:

```text
structures
generation
labeling
jobs
```

User loop:

```bash
pesmaker validate run.yaml
pesmaker next run.yaml
```

The first `next` run usually generates structures, prepares SCF folders, and
writes a dry-run submit log. It then prints:

```text
Submit SCF jobs: pesmaker submit run.yaml
```

After VASP finishes and `OUTCAR` files exist:

```bash
pesmaker next run.yaml
```

PESMaker collects `train.xyz`.

## Sampling and Training Flow

Use this when generated structures should first seed GPUMD MD sampling.

YAML shape:

```text
structures
generation
sampling
sampling.selection
labeling
training
jobs
```

User loop:

```bash
pesmaker validate run.yaml
pesmaker next run.yaml
# next prints: Submit GPUMD sampling jobs: pesmaker submit run.yaml --stage sampling
```

After GPUMD writes `movie.xyz`:

```bash
pesmaker next run.yaml
# next prints: Submit SCF jobs: pesmaker submit run.yaml
```

After VASP writes `OUTCAR`:

```bash
pesmaker next run.yaml
# next prints: Submit training jobs: pesmaker submit run.yaml --stage training
```

You do not need to remember this full chain. `next` prints the correct submit
command and stage name at each boundary. `pesmaker submit run.yaml` remains a
shortcut for SCF jobs; sampling and training use `--stage sampling` and
`--stage training`.

## What If Everything Is Already Done?

If generated structures, trajectories, selected frames, OUTCAR files, and the
dataset already exist, `next` skips finished work and continues to the next
missing local stage.

For example, if `OUTCAR` files already exist and training is configured,
`next` can collect the dataset, prepare training inputs, and stop at the
training submit preview in one run.

## What If I Want Manual Control?

Use command pages:

- [generate](commands/generate.md)
- [sample-setup](commands/sample-setup.md)
- [select](commands/select.md)
- [scf-setup](commands/scf-setup.md)
- [submit](commands/submit.md)
- [collect](commands/collect.md)
- [train-setup](commands/train-setup.md)

Manual mode is useful for debugging templates or inspecting one stage. It is
not required for ordinary use.
