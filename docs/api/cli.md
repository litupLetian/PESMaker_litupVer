# Command-Line Interface

PESMaker exposes a `pesmaker` command after installation.

## `pesmaker init`

Write a starter YAML configuration:

```bash
pesmaker init pesmaker.yaml
```

The command refuses to overwrite an existing file.

## `pesmaker validate`

Validate a YAML or TOML configuration file:

```bash
pesmaker validate examples/perturb.yaml
```

## `pesmaker plan`

Print a human-readable workflow plan:

```bash
pesmaker plan examples/perturb.yaml
```

## `pesmaker generate`

Generate supercells and perturbed structures:

```bash
pesmaker generate examples/perturb.yaml
```

The current implementation writes structure files and a `manifest.jsonl` file in
the configured `generation.output_dir`.
