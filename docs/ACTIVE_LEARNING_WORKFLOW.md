# Active Learning Workflow Manual

This manual explains the complete PESMaker workflow for generating structures,
preparing sampling jobs, selecting representative frames, preparing VASP SCF
calculations, collecting labeled datasets, and preparing potential training.

PESMaker intentionally splits the work into independent stages. Each command
writes normal files and folders, so expensive calculations can be inspected,
submitted, repaired, and rerun without hiding the process behind one monolithic
driver.

## Workflow Map

Direct generation and SCF labeling:

```bash
pesmaker validate run.yaml
pesmaker generate run.yaml
pesmaker scf-setup run.yaml
pesmaker submit run.yaml --dry-run   # preview SCF/VASP submissions
pesmaker submit run.yaml             # submit SCF/VASP jobs
pesmaker collect run.yaml
```

Full active-learning style loop:

```bash
pesmaker validate run.yaml
pesmaker generate run.yaml
pesmaker sample-setup run.yaml
pesmaker submit run.yaml --stage sampling   # submit MD sampling jobs
pesmaker select run.yaml
pesmaker scf-setup run.yaml
pesmaker submit run.yaml --dry-run          # preview SCF/VASP submissions
pesmaker submit run.yaml                    # submit SCF/VASP jobs
pesmaker collect run.yaml
pesmaker train-setup run.yaml
pesmaker submit run.yaml --stage training   # submit NEP training jobs
```

Expected stage outputs:

```text
generated/   # supercells, slabs, defects, perturbed structures, manifest
sampling/    # MD job folders, model.xyz, run.in, submit.sh
selected/    # selected trajectory frames and manifest
labeling/    # VASP SCF folders with POSCAR, INCAR, optional POTCAR, submit.sh
train.xyz    # collected extxyz dataset from completed SCF outputs
training/    # NEP input files and training submit script
```

There are multiple `submit` commands because they target different prepared
stages. `sample-setup` creates sampling `submit.sh` files, submitted with
`--stage sampling`. `scf-setup` creates labeling `submit.sh` files, submitted
by the default `pesmaker submit run.yaml`. `train-setup` creates training
`submit.sh` files, submitted with `--stage training`.

## Why PESMaker

PESMaker is built for targeted MLIP dataset construction. Instead of starting
from random structures, it starts from structures that matter for the target
application and makes the workflow reproducible.

Key benefits:

- one YAML file can describe bulk, surface, defect, and perturbed structure
  families;
- each generated structure is recorded in `manifest.jsonl` and summarized in
  `generation_summary.txt`;
- generated structures can go directly to VASP SCF labeling or first through
  GPUMD sampling and frame selection;
- `scf-setup` creates complete calculation folders and preserves source-path
  traceability;
- `submit` runs from the correct job directories and supports dry-run previews;
- collection and training setup are separate stages, so failed SCF jobs do not
  corrupt the dataset silently.

## Configuration Overview

Start from `examples/te_defect_md.yaml` or create a new starter file:

```bash
pesmaker init run.yaml
```

A complete workflow config has these main sections:

```yaml
project: Te_Pd_rich_defect_md

structures:
  include:
    - initial_structures/*.cif

generation:
  output_dir: generated
  tasks:
    - name: surface_331
      supercell: [3, 3, 1]
      surface:
        vacuum: 30.0
        axis: 2
        center: true
        defects:
          mode: random
          seed: 42
          single_vacancies:
            elements: [Te]
            max_count: 8
          double_vacancies:
            elements: [Te]
            max_count: 8
          line_defects:
            elements: [Te]
            max_count: 4
        perturb:
          pert_num: 20
          cell_pert_fraction: 0.03
          atom_pert_distance: 0.1
          atom_pert_style: normal
          seed: 42
          format: vasp
    - name: bulk_333
      supercell: [3, 3, 3]
      perturb:
        pert_num: 20
        cell_pert_fraction: 0.03
        atom_pert_distance: 0.1
        atom_pert_style: normal
        seed: 42
        format: vasp

sampling:
  engine: gpumd
  output_dir: sampling
  gpumd_dir: /path/to/GPUMD/src
  potential: nep89_20250409.txt
  temperatures: [300, 600, 900]
  run_in: templates/gpumd/run.in
  selection:
    trajectory_pattern: sampling/**/movie.xyz
    output_dir: selected
    min_distance: 0.2
    max_count: 200

labeling:
  engine: vasp
  output_dir: labeling
  input_manifest: selected/manifest.jsonl
  incar: templates/vasp/INCAR
  potcar_library: /path/to/VASP/potentials
  command: /path/to/vasp_std

dataset:
  format: extxyz
  split: [0.8, 0.1, 0.1]

training:
  model: nep
  output_dir: training
  dataset: train.xyz
  command: nep

jobs:
  machine: cluster-a
  submit_command: sbatch
  cores_cpu: 36
  gpus: 0
  sub_file:
    sampling: templates/sbatch/gpumd.sh
    labeling: templates/sbatch/vasp_cpu_36.sh
    training: templates/sbatch/nep.sh
```

Use `generation.tasks` when one run should prepare several independent
structure families. Do not repeat the same YAML key in one mapping; use
separate task entries instead.

## Stage 1: Generate Structures

Run:

```bash
pesmaker generate run.yaml
```

The `generation` section prepares the structural candidates for direct SCF
labeling or for MD sampling. The operation order inside each task is:

```text
input structure -> supercell -> surface -> defects -> perturb
```

Each task has its own `name`, `supercell`, optional `surface`, optional
`defects`, and optional `perturb` settings.

### Bulk and Perturbed Structures

For bulk perturbations:

```yaml
generation:
  output_dir: generated
  tasks:
    - name: bulk_333
      supercell: [3, 3, 3]
      perturb:
        pert_num: 20
        cell_pert_fraction: 0.03
        atom_pert_distance: 0.1
        atom_pert_style: normal
        seed: 42
        format: vasp
```

Important perturbation fields:

- `pert_num`: number of structures generated from each variant;
- `cell_pert_fraction`: random cell perturbation amplitude;
- `atom_pert_distance`: atomic displacement scale in Angstrom;
- `atom_pert_style`: `normal`, `uniform`, or `const`;
- `seed`: reproducible random seed;
- `format`: `vasp` or `extxyz`.

### Surface Slabs

For 2D materials or slab-like systems:

```yaml
surface:
  vacuum: 30.0
  axis: 2
  center: true
```

`vacuum` is the vacuum thickness in Angstrom. `axis: 2` adds vacuum along the
z direction, which is the usual choice for structures lying in the xy plane.
`center: true` places the slab in the middle of the vacuum direction.

### Defects

Defects can be applied after surface generation:

```yaml
surface:
  vacuum: 30.0
  axis: 2
  center: true
  defects:
    mode: random
    seed: 42
    single_vacancies:
      elements: [Te]
      max_count: 8
    double_vacancies:
      elements: [Te]
      max_count: 8
    line_defects:
      elements: [Te]
      max_count: 4
  perturb:
    pert_num: 20
    format: vasp
```

Supported variant families:

- `pristine`: the structure after supercell and surface operations, without
  removed atoms;
- `single_vacancies`: remove one atom from selected elements;
- `double_vacancies`: remove atom pairs, with nearest pairs generated first by
  default;
- `line_defects`: remove atom rows, with row grouping inferred automatically.

For reproducible random choices, set:

```yaml
defects:
  mode: random
  seed: 42
```

Per-family random settings can override the global mode:

```yaml
defects:
  single_vacancies:
    selection: random
    seed: 7
    elements: [Te]
    max_count: 8
```

Advanced line-defect controls are available when automatic row detection is not
enough:

- `coordinate_axis`: fractional coordinate used to group rows;
- `tolerance`: fractional-coordinate bin width for row grouping.

Expected output:

```text
generated/
  manifest.jsonl
  generation_summary.txt
  surface_331/
    Te-mp-19/
      pristine/
        surface_000000.vasp
      single_vacancy_Te_000000/
        defect_000000.vasp
      double_vacancy_Te000000_Te000001/
        defect_000000.vasp
      line_defect_axis1_000/
        defect_000000.vasp
  bulk_333/
    Te-mp-19/
      pristine/
        perturb_000000.vasp
```

`manifest.jsonl` is machine-readable. `generation_summary.txt` is the faster
file to inspect by eye.

## Stage 2: Prepare Sampling Jobs

Run:

```bash
pesmaker sample-setup run.yaml
```

The `sample-setup` stage creates one MD working directory for each generated
structure and sampling condition.

For GPUMD:

```yaml
sampling:
  engine: gpumd
  gpumd_dir: /path/to/GPUMD/src
  output_dir: sampling
  potential: nep89_20250409.txt
  temperatures: [300, 600, 900]
  run_in: templates/gpumd/run.in
```

`temperatures: [300, 600, 900]` creates one constant-temperature job per
temperature and generated structure:

```text
sampling/
  sampling_manifest.jsonl
  md_000000_temp_300K/
    model.xyz
    run.in
    submit.sh
  md_000000_temp_600K/
    model.xyz
    run.in
    submit.sh
```

For a heating ramp, use:

```yaml
sampling:
  engine: gpumd
  potential: nep89_20250409.txt
  temperature: 300-1500
```

If `potential` points to an existing file, PESMaker copies it into each MD
folder. If it is only a filename, PESMaker writes that filename into `run.in`
and assumes it will be available when GPUMD runs.

Submit sampling jobs with:

```bash
pesmaker submit run.yaml --stage sampling
```

Use a dry run first when checking a new machine template:

```bash
pesmaker submit run.yaml --stage sampling --dry-run
```

Future sampling engines, such as LAMMPS-MACE, can use the same stage boundary
with engine-specific writers.

## Stage 3: Select Representative Frames

After MD jobs finish and trajectories such as `movie.xyz` exist, run:

```bash
pesmaker select run.yaml
```

Configure selection under `sampling.selection`:

```yaml
sampling:
  selection:
    trajectory_pattern: sampling/**/movie.xyz
    output_dir: selected
    min_distance: 0.2
    max_count: 200
```

The current selector uses farthest point sampling. It keeps adding the frame
farthest from the selected set until `max_count` is reached or the
nearest-selected distance falls below `min_distance`.

Expected output:

```text
selected/
  selected.xyz
  selected_000000.xyz
  selected_000001.xyz
  manifest.jsonl
```

`selected.xyz` is a multi-frame inspection file. The single-frame files listed
in `selected/manifest.jsonl` are used by `scf-setup`.

## Stage 4: Prepare VASP SCF Jobs

Run:

```bash
pesmaker scf-setup run.yaml
```

The `scf-setup` stage turns generated structures or selected frames into
independent SCF calculation folders.

### From Selected MD Frames

Use `input_manifest` when labeling frames selected from MD:

```yaml
labeling:
  engine: vasp
  output_dir: labeling
  input_manifest: selected/manifest.jsonl
  incar: templates/vasp/INCAR
  potcar_library: /path/to/VASP/potentials
  command: /path/to/vasp_std
```

Expected output:

```text
labeling/
  labeling_manifest.jsonl
  selected_000000/
    POSCAR
    INCAR
    POTCAR
    POTCAR.spec
    submit.sh
```

### Directly From Generated Structures

Use `input_dir` when generated structures should go straight to SCF labeling:

```yaml
labeling:
  engine: vasp
  output_dir: labeling
  input_dir: generated
  incar: templates/vasp/INCAR
  potcar_library: /path/to/VASP/potentials
  command: /path/to/vasp_std
```

This SCF-only config can omit `structures`. PESMaker reads
`input_dir/manifest.jsonl` when present. If no manifest exists, it recursively
scans for `POSCAR`, `CONTCAR`, `*.vasp`, `*.poscar`, `*.cif`, `*.extxyz`, and
`*.xyz`.

The generated folder structure is preserved by default while file suffixes are
dropped from calculation folder names:

```text
labeling/
  surface_331/
    Te-mp-19/
      single_vacancy_Te_000000/
        defect_000000/
          POSCAR
          defect_000000.vasp-bak
          INCAR
          POTCAR
          POTCAR.spec
          submit.sh
```

The original generated structure is backed up by default. Set
`backup_source: false` under `labeling` only if these backups are not wanted.

### VASP Inputs

The default `examples/templates/vasp/INCAR` is a conservative static SCF
template:

```text
SYSTEM = PESMaker single point
GGA = PE
LREAL = Auto
ENCUT = 650
KSPACING = 0.2
KGAMMA = .TRUE.
NSW = 0
IBRION = -1
ALGO = Normal
EDIFF = 1E-06
SIGMA = 0.02
ISMEAR = 0
PREC = Accurate
NELM = 150
```

For CPU VASP jobs, PESMaker writes `KPAR` and `NCORE` into `INCAR`. `KPAR`
defaults to `2` when `jobs.cores_cpu` is even, otherwise `1`. `NCORE` is chosen
as a factor within each KPAR group. For example, `cores_cpu: 36` gives
`KPAR = 2` and `NCORE = 3`.

Override these values when your cluster or benchmarks require it:

```yaml
jobs:
  cores_cpu: 36
  vasp_kpar: 2
  vasp_ncore: 6
```

PESMaker writes `NCORE`, not legacy `NPAR`.

If `potcar_library` is set, PESMaker writes `POTCAR` automatically from its
built-in recommended VASP potential table. For ordinary PBE calculations this
uses the standard PBE recommendations, such as `Te`, `Na_pv`, `K_sv`, and
`Ga_d`. For GW potentials, set:

```yaml
labeling:
  gw_potcar: true
```

Each calculation folder also contains `POTCAR.spec`, recording the exact
potential directories concatenated into `POTCAR`.

You can also provide explicit files:

```yaml
labeling:
  potcar: templates/vasp/POTCAR
  kpoints: templates/vasp/KPOINTS
  template_dir: templates/vasp/static_scf
```

## Stage 5: Submit Jobs

`submit` submits prepared `submit.sh` files. It does not create new inputs; it
only submits files created by `sample-setup`, `scf-setup`, or `train-setup`.
By default it submits the SCF labeling stage:

```bash
pesmaker submit run.yaml
```

Preview first:

```bash
pesmaker submit run.yaml --dry-run
```

Submit other stages explicitly:

```bash
pesmaker submit run.yaml --stage sampling   # MD sampling jobs from sampling/
pesmaker submit run.yaml --stage training   # training jobs from training/
```

Machine-specific submission settings live under `jobs`:

```yaml
jobs:
  machine: cluster-a
  submit_command: sbatch
  nodes: 1
  cores_cpu: 36
  gpus: 0
  sub_file:
    sampling: templates/sbatch/gpumd.sh
    labeling: templates/sbatch/vasp_cpu_36.sh
    training: templates/sbatch/nep.sh
```

For a single-stage config, `sub_file` can be one path:

```yaml
jobs:
  submit_command: sbatch
  cores_cpu: 36
  sub_file: templates/sbatch/vasp_cpu_36.sh
```

Submit templates can use these placeholders:

```text
{job_name}          # generated from the work directory name
{workdir}           # stage working directory
{command}           # engine command, such as gpumd, vasp_std, or nep
{nodes}             # jobs.nodes, default 1
{ntasks}            # nodes * cores_cpu
{cores_cpu}         # CPU cores per node
{ntasks_per_node}   # alias for cores_cpu
{gpus}              # GPUs per node
{vasp_kpar}         # generated VASP KPAR
{vasp_ncore}        # generated VASP NCORE
```

Placeholders are optional for common Slurm fields. When a user-provided
template already contains `#SBATCH --job-name`, `#SBATCH --ntasks`, or a VASP
run line such as `mpirun /path/to/vasp_std`, PESMaker rewrites those values for
each calculation folder while keeping site-specific lines such as partitions,
accounts, modules, and environment setup.

The default CPU VASP run command is:

```bash
mpirun {command}
```

For GPU jobs, set `gpus`:

```yaml
jobs:
  cores_cpu: 8
  gpus: 1
```

`pesmaker submit` runs the scheduler command from each job folder, so manual
submission should do the same:

```bash
cd labeling/path/to/calc
sbatch submit.sh
```

## Stage 6: Collect the Labeled Dataset

After SCF jobs finish, collect completed outputs:

```bash
pesmaker collect run.yaml
```

Configure the OUTCAR search pattern and dataset path:

```yaml
labeling:
  outcar_pattern: labeling/**/OUTCAR
  dataset_path: train.xyz
```

The command reads matched VASP outputs with ASE and writes an extxyz dataset.
Collection is separate from SCF setup and submission so failed or partial
calculations can be inspected before rebuilding the dataset.

## Stage 7: Prepare Training

Run:

```bash
pesmaker train-setup run.yaml
```

For NEP:

```yaml
training:
  model: nep
  output_dir: training
  dataset: train.xyz
  command: nep
```

Expected output:

```text
training/
  train.xyz
  nep.in
  submit.sh
```

Submit training with:

```bash
pesmaker submit run.yaml --stage training
```

For non-NEP trainers, set `training.model` and `training.command`. The stage
boundary remains the same, so new trainers can be added without changing
generation, sampling, labeling, or collection.

## Practical Checklist

Before generation:

- Run `pesmaker validate run.yaml`.
- Confirm input structures have the intended chemistry, cell, and dimensionality.
- For 2D materials, confirm `surface.axis` and `surface.vacuum`.
- Start with small `max_count` and `pert_num` values before scaling up.

After generation:

- Inspect `generated/generation_summary.txt`.
- Open representative pristine, vacancy, double-vacancy, and line-defect
  structures visually.
- Confirm atom counts and defect families match the intended campaign.

Before submission:

- Run `pesmaker submit run.yaml --dry-run`.
- Inspect one `submit.sh` per stage.
- For SCF jobs, inspect one folder for `POSCAR`, `INCAR`, `POTCAR`,
  `POTCAR.spec`, and resource settings.
- Confirm `labeling.command`, `jobs.cores_cpu`, and any cluster modules match
  the target machine.

After SCF jobs:

- Check convergence before collection.
- Collect only completed outputs matched by `labeling.outcar_pattern`.
- Keep `train.xyz` versioned by project or campaign name.
- Prepare training only after confirming the dataset contents.

## Current Scope and Extension Points

Current implemented capabilities:

- multi-task structure generation;
- supercells, 2D vacuum setup, pristine structures, single vacancies, double
  vacancies, line defects, and perturbations;
- GPUMD sampling setup;
- farthest point trajectory-frame selection;
- VASP SCF folder setup with submit scripts and optional POTCAR assembly;
- scheduler submission with dry-run support;
- extxyz dataset collection through ASE;
- NEP training setup.

Planned extension points:

- LAMMPS-MACE sampling templates and engine-specific input writers;
- more chemically aware defect enumeration;
- stricter VASP convergence filtering during dataset collection;
- richer dataset splitting and training reports.
