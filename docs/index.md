# PESMaker

PESMaker is a lightweight Python workflow package for generating
application-oriented datasets and machine-learned interatomic potentials from
user-provided atomistic structures.

The current development focus is the first structure-generation layer:

1. read initial structures with ASE;
2. build supercells;
3. create perturbed structures using cell and atomic displacements;
4. write generated structures and a manifest for later DFT labeling.

## Current command flow

```bash
pesmaker validate examples/perturb.yaml
pesmaker generate examples/perturb.yaml
```

## Project direction

The intended full workflow is:

```text
initial structures
  -> structure generation and targeted sampling
  -> DFT SCF labeling
  -> dataset assembly
  -> NEP or MACE training
  -> deployable potential
```

PESMaker is designed to be user-structure-driven, foundation-potential-assisted,
and friendly to GPUMD/NEP and MACE workflows.
