# PESMaker Architecture

PESMaker is organized around replaceable workflow stages.

## Core objects

- `PESMakerConfig`: validated project configuration.
- `WorkflowPlan`: an executable summary of the requested workflow.
- `TaskManifest`: persistent record of generated structures, DFT jobs, parsed
  labels, datasets, and trained models.

## Stage interfaces

Each stage should eventually expose a small Python API:

```python
stage.prepare(config, manifest)
stage.run(config, manifest)
stage.collect(config, manifest)
```

This keeps command-line execution, Python API usage, and HPC execution aligned.

## State model

The first implementation should use a file-backed manifest, preferably SQLite or
JSON Lines. A database service should be optional, not mandatory.

## Dependency policy

The base package should stay light. Heavy scientific tools should be optional
extras or external executables:

- base: configuration, workflow planning, file manifests, CLI;
- atomistic extra: ASE and pymatgen;
- workflow extras: jobflow or AiiDA only if a user chooses those integrations;
- engines: VASP, CP2K, GPUMD, LAMMPS, MACE as external programs.

