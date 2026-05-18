# PESMaker

PESMaker is a planned lightweight workflow package for building application-oriented
datasets and machine-learned interatomic potentials from user-provided atomistic
structures.

The working full name is **Potential Energy Surface Maker**.

## Scope

PESMaker focuses on this path:

```text
initial structures
  -> structure generation and targeted sampling
  -> candidate filtering
  -> DFT single-point labeling
  -> dataset assembly
  -> NEP or MACE training
  -> model report and deployable potential
```

The first implementation target is VASP single-point labeling, followed by
GPUMD/NEP and MACE training workflows.

## Differentiation

PESMaker is designed to be:

- user-structure-driven rather than random-structure-search first;
- foundation-potential-assisted for affordable sampling before DFT labeling;
- NEP/GPUMD and MACE friendly from the beginning;
- lightweight enough to run without a mandatory database service;
- application-oriented for batteries, solid electrolytes, thermal transport,
  alloys, defects, surfaces, catalysis, and reactions.

## Current skeleton

```text
src/pesmaker/
  config/        # YAML/TOML input parsing and validation
  structures/    # POSCAR/CIF/XYZ IO, supercells, perturbations
  samplers/      # LAMMPS+MACE, GPUMD+NEP sampling interfaces
  generators/    # defects, vacancies, surfaces, transition states
  labelers/      # VASP first, CP2K later
  jobs/          # Slurm/PBS/local submission and monitoring
  parsers/       # VASP, GPUMD, MACE output parsing
  dataset/       # extxyz, NEP train.xyz, HDF5, metadata
  trainers/      # NEP and MACE training interfaces
  workflow/      # workflow planning and state tracking
  cli.py         # command line interface
```

## Try the scaffold

```bash
python -m pesmaker validate examples/pesmaker.yaml
python -m pesmaker plan examples/pesmaker.yaml
```

For editable development:

```bash
pip install -e ".[dev]"
pesmaker plan examples/pesmaker.yaml
```

