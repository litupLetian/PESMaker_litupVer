# Defect, MD, Labeling, and Training Workflow

This workflow keeps each expensive stage separate so generated structures,
MD sampling, single-point calculations, dataset collection, and training do
not overwrite each other.

## 1. Generate 2D defect candidates

Use `generation.surface` for slab vacuum and `generation.defects` for vacancy
families.

```yaml
generation:
  supercell: [3, 3, 1]
  output_dir: generated
  surface:
    vacuum: 30.0
    axis: 2
    center: true
  defects:
    include_pristine: true
    single_vacancies:
      elements: [Te]
      max_count: 8
    double_vacancies:
      elements: [Te]
      nearest_first: true
      max_count: 8
    line_defects:
      elements: [Te]
      coordinate_axis: 1
      tolerance: 0.05
      max_count: 4
  perturb:
    pert_num: 20
    cell_pert_fraction: 0.03
    atom_pert_distance: 0.1
    atom_pert_style: normal
    seed: 42
    format: vasp
```

Run:

```bash
pesmaker generate run.yaml
```

The manifest is written to `generated/manifest.jsonl`. Defect variants are
stored under per-structure folders such as `generated/Te-mp-19/pristine` and
`generated/Te-mp-19/single_vacancy_Te_000000`.

## 2. Prepare large-model MD sampling

For GPUMD, configure the executable or its source directory:

```yaml
sampling:
  engine: gpumd
  gpumd_dir: /home/tingliang/software/GPUMD/GPUMD-master-26-05-2026/src
  output_dir: sampling
  run_in: templates/gpumd/run.in
```

Run:

```bash
pesmaker sample-setup run.yaml
```

This creates one `sampling/md_XXXXXX` folder for each generated structure,
with `model.xyz`, `run.in`, and `submit.sh`.

The same boundary can support future engines such as LAMMPS-MACE by setting
`sampling.engine` and `sampling.command`.

## 3. Select MD frames

After MD produces trajectories such as `movie.xyz`, use farthest point sampling:

```yaml
sampling:
  selection:
    trajectory_pattern: sampling/**/movie.xyz
    output_dir: selected
    min_distance: 0.2
    max_count: 200
```

Run:

```bash
pesmaker select run.yaml
```

The selected structures are written to `selected/selected.xyz` with
`selected/manifest.jsonl`.

## 4. Prepare single-point calculations

```yaml
labeling:
  engine: vasp
  output_dir: labeling
  input_manifest: selected/manifest.jsonl
  incar: templates/vasp/INCAR
  command: vasp_std
```

Run:

```bash
pesmaker label-setup run.yaml
```

This creates independent `labeling/calc_XXXXXX` folders with `POSCAR`,
`INCAR`, optional copied templates, and `submit.sh`.

## 5. Collect training data

After VASP finishes:

```yaml
labeling:
  outcar_pattern: labeling/**/OUTCAR
  dataset_path: train.xyz
```

Run:

```bash
pesmaker collect run.yaml
```

The command reads matched VASP outputs with ASE and writes an extxyz training
set.

## 6. Prepare training

```yaml
training:
  model: nep
  output_dir: training
  dataset: train.xyz
  command: nep
```

Run:

```bash
pesmaker train-setup run.yaml
```

For different machines, set:

```yaml
jobs:
  machine: cluster-a
  sbatch_templates:
    sampling: templates/sbatch/gpumd.sh
    labeling: templates/sbatch/vasp.sh
    training: templates/sbatch/nep.sh
```

Templates may use `{job_name}`, `{workdir}`, and `{command}` placeholders.
