# `pesmaker scf-setup`

`scf-setup` prepares VASP SCF calculation folders.

Normal users can let [`next`](next.md) run this stage.

## Use

```bash
pesmaker scf-setup run.yaml
```

## Minimal YAML

```yaml
project: scf_run

labeling:
  engine: vasp
  output_dir: labeling
  input_dir: generated
  incar: templates/vasp/INCAR
  potcar_library: /path/to/VASP/potentials
  command: /path/to/vasp_std

jobs:
  submit_command: sbatch
  cores_cpu: 36
  sub_file: templates/sbatch/vasp_cpu_36.sh
```

## Copy A Submit Template Verbatim

By default, `sub_file` is a renderable template: PESMaker replaces supported
placeholders and refreshes the Slurm job name. To copy the template directly
to every SCF folder as `submit.sh`, enable:

```yaml
jobs:
  sub_file: templates/sbatch/vasp_cpu_36.sh
  copy_sub_file: true
```

In this mode PESMaker performs a byte-for-byte copy. It does not replace
`{command}`, `{job_name}`, resource placeholders, literal Slurm job names, or
literal command lines. The template must therefore be ready to submit without
per-job rendering. `copy_sub_file` must be `true` or `false` and defaults to
`false`; it applies only to VASP SCF/labeling submit scripts.

If `pesmaker submit` refreshes a pending or retry SCF script, copy mode copies
the current template again instead of rendering it. Edit the source template,
not an already prepared `submit.sh`, when this mode is enabled.

## Inputs

PESMaker looks for structures in this order:

1. `labeling.input_manifest`
2. `labeling.input_dir`
3. `generation.output_dir`
4. local `generated/`
5. `runs/<project>/generated`

When an input directory contains `manifest.jsonl`, PESMaker uses that manifest
because it preserves exact frame indices for multi-frame files created by
`select`. If no manifest is present, PESMaker recursively scans the directory
for structure files and prepares one SCF folder per discovered structure.

Scanned input files can be named `POSCAR`, `CONTCAR`, or `XDATCAR`, or use one
of these suffixes:

```text
.cif
.extxyz
.poscar
.traj
.vasp
.xyz
```

For scanned multi-frame `.xyz`, `.extxyz`, `.traj`, or `XDATCAR` files,
PESMaker prepares one SCF job per frame. This lets users point
`labeling.input_dir` at a manually prepared folder even when the folder was not
created by PESMaker and has no `manifest.jsonl`.

## Distribute Common Files To Every SCF Folder

Use `labeling.template_dir` to copy a set of common auxiliary files into every
prepared SCF calculation folder:

```yaml
labeling:
  engine: vasp
  input_dir: generated
  output_dir: labeling
  template_dir: templates/vasp/common
```

For example, given this source directory:

```text
templates/vasp/common/
  KPOINTS
  vdW_kernel.bindat
  helper.dat
  nested/
    ignored.dat
```

each prepared calculation folder receives `KPOINTS`, `vdW_kernel.bindat`, and
`helper.dat`. PESMaker copies only regular files directly inside
`template_dir`; it does not recursively copy `nested/` or any other
subdirectory. File names are preserved, and existing destination files with
the same names are overwritten at the time of copying. File metadata is
preserved where supported by the operating system.

Use this option for auxiliary files that should be identical in every SCF job.
Avoid placing PESMaker-managed names such as `POSCAR`, `INCAR`, `POTCAR`, or
`submit.sh` in `template_dir`, because setup ordering can cause one version to
overwrite another. In particular, PESMaker writes the final POTCAR and submit
script after distributing these common files.

`labeling.template_dir` is separate from `jobs.copy_sub_file`. The former
distributes all top-level files from a directory, while the latter copies one
submit-script template specifically to `submit.sh`.

## Outputs

```text
labeling/
  labeling_manifest.jsonl
  ...
    POSCAR
    INCAR
    POTCAR
    submit.sh
```

## VASP Resource Fields

```yaml
jobs:
  cores_cpu: 36
  vasp_kpar: 2
  vasp_ncore: 6
  skip_completed: true
  check_scf_convergence: true
```

PESMaker writes `KPAR` or `NCORE` to `INCAR` only when `jobs.vasp_kpar` or
`jobs.vasp_ncore` is explicitly set. If those keys are omitted, the INCAR
template is left in control of VASP parallel tags.

When `jobs.sub_file` is provided, PESMaker does not scan and rewrite literal
resource directives such as `#SBATCH --ntasks` or literal VASP command lines.
It only replaces explicit placeholders such as `{command}`, `{job_name}`,
`{workdir}`, `{nodes}`, `{ntasks}`, `{cores_cpu}`, `{gpus}`, `{vasp_kpar}`, and
`{vasp_ncore}`. As a convenience, PESMaker does update literal
`#SBATCH --job-name=...` and `#SBATCH -J ...` lines to the calculation folder
name so queued jobs are easier to identify. For nested SCF folders, the queue
name uses a compact parent/folder marker, for example
`mp-1186427_Pd_temp_300K/selected_000000` becomes
`mp1186427_Pd_sel000000`. If the template does not contain
`{command}`, the command line in the user script is left unchanged. If resource
fields such as `cores_cpu`, `nodes`, or `gpus` are present, they affect the
replacement value of `{command}` and the corresponding resource placeholders.

To let PESMaker add MPI ranks from the YAML, put `{command}` in the submit
template where VASP should run. For example, with `cores_cpu: 36` and
`command: /path/to/vasp_std`, this template line:

```bash
{command}
```

is rendered as:

```bash
mpirun -np 36 /path/to/vasp_std
```

If the template instead contains a literal line such as
`mpirun /path/to/vasp_std`, PESMaker keeps that line unchanged and does not add
`-np 36`.

For CPU VASP jobs with `cores_cpu` or `nodes` set, PESMaker uses
`mpirun -np <nodes * cores_cpu> <labeling.command>` when `labeling.command` is
only the VASP executable. If the command starts with `mpirun` or `mpiexec` but
does not include `-np`, `-n`, `--np`, or `--ntasks`, PESMaker inserts the same
rank count. Existing rank-count options are kept unchanged.

For GPU VASP, request GPUs with `jobs.gpus` and usually omit `vasp_kpar` and
`vasp_ncore`. When `gpus` is greater than zero, PESMaker does not add CPU VASP
parallel tags to `INCAR`. If `labeling.command` is only the VASP executable,
PESMaker runs it as `mpirun -np <jobs.gpus> <labeling.command>`. If the command
starts with `mpirun` or `mpiexec` but does not include an explicit rank count,
PESMaker inserts `-np <jobs.gpus>`. Commands that start with `srun` are kept
unchanged.

```yaml
project: 2D_Te_MD

labeling:
  engine: vasp
  output_dir: run_vasp_scf
  input_dir: selected
  incar: /home/a4s5d/LT/yixiu/MLP_structure/1.Te/1.Material_project_structure/INCAR
  potcar_library: /home/a4s5d/software/VASP/potentials
  command: /data/software/vasp6.4-gpu/bin/vasp_std

jobs:
  submit_command: sbatch
  cores_cpu: 6
  gpus: 1
  skip_completed: true
  check_scf_convergence: true
  sub_file: /home/a4s5d/LT/yixiu/MLP_structure/1.Te/1.Material_project_structure/sub_gpu.sh
```

This requests one GPU per prepared SCF folder. `cores_cpu: 6` should match the
CPU task count in the submit template, for example `#SBATCH -n 6`.

During SCF submission, `skip_completed` and `check_scf_convergence` both
default to `true`. PESMaker skips only VASP folders that terminated normally
without the electronic SCF nonconvergence marker.

## Next Step

Preview or submit SCF jobs:

```bash
pesmaker submit run.yaml --dry-run
pesmaker submit run.yaml
```

With `next`, PESMaker writes the dry-run log and prints the real submit
command.
