# `pesmaker submit`

`submit` submits prepared `submit.sh` files.

It does not create structures or setup folders. Run setup first, or let
[`next`](next.md) prepare the folders.

`next` prints the correct submit command. New users can simply copy the line
printed under `What you should do next`.

## SCF Jobs

```bash
pesmaker submit run.yaml
```

No `--stage` means SCF labeling. This shortcut is kept for compatibility and
for experienced users.

## Sampling Jobs

```bash
pesmaker submit run.yaml --stage sampling
```

## Training Jobs

```bash
pesmaker submit run.yaml --stage training
```

## Dry Run

Use dry-run before spending cluster time:

```bash
pesmaker submit run.yaml --dry-run
pesmaker submit run.yaml --stage sampling --dry-run
pesmaker submit run.yaml --stage training --dry-run
```

Dry-run writes a log of the commands but does not call the scheduler.

## Stage Names

`submit` is one command with different stages:

```text
SCF single-point jobs   : pesmaker submit run.yaml
GPUMD sampling jobs     : pesmaker submit run.yaml --stage sampling
NEP training jobs       : pesmaker submit run.yaml --stage training
```

These stages do not conflict. PESMaker reads different manifests and output
folders for each stage.

## Scheduler Settings

```yaml
jobs:
  submit_command: sbatch
  cores_cpu: 36
  gpus: 0
  sub_file:
    sampling: templates/sbatch/gpumd.sh
    labeling: templates/sbatch/vasp_cpu_36.sh
    training: templates/sbatch/nep.sh
```

For a one-stage SCF run, `sub_file` can be a single path.

## Important Rule

Submit from PESMaker with `pesmaker submit ...`, or manually submit from inside
each prepared job directory. The generated scripts assume the calculation
directory is the working directory.
