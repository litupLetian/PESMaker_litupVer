# `pesmaker status`

`status` shows what `next` would do, without writing files.
It is the place to inspect detailed flow/status/state information when the
normal `next` output is intentionally short.

## Use

```bash
pesmaker status run.yaml
```

## When To Use It

Use it before running `next` if you are not sure what PESMaker will do.
Use `pesmaker next run.yaml --verbose` if you want the same style of diagnostic
information during an actual run.

Example:

```text
Smart next
Inferred flow    : generate -> scf -> collect
Status           : status

Next action      : Generate structures from the configured inputs.
What you should do next:
  - Run: pesmaker next run.yaml
```

`status` is read-only. It does not create `generated/`, `labeling/`,
`.pesmaker/`, or dry-run logs.
