from __future__ import annotations

from pathlib import Path


def load_structure(path: str | Path):
    try:
        from ase.io import read
    except ImportError as exc:
        message = "Structure IO requires ASE. Install pesmaker with: pip install -e .[atomistic]"
        raise RuntimeError(message) from exc

    return read(Path(path))


def write_structure(atoms, path: str | Path, *, fmt: str | None = None) -> None:
    try:
        from ase.io import write
    except ImportError as exc:
        message = "Structure IO requires ASE. Install pesmaker with: pip install -e .[atomistic]"
        raise RuntimeError(message) from exc

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write(output_path, atoms, format=fmt)
