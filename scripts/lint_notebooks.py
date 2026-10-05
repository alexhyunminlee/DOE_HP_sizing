"""Lint Python cells in Quarto notebooks with Ruff.

`ruff format` formats those cells, but `ruff check` skips them. Cells in one
notebook share a scope, so each notebook is checked as a single Python file.
Blank lines stand in for the Markdown so a finding points at the original line.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def python_cells(source: str) -> str:
    rendered: list[str] = []
    in_cell = False
    for line in source.splitlines():
        fence = line.strip()
        if not in_cell and fence.startswith("```{python"):
            in_cell = True
            rendered.append("")
        elif in_cell and fence.startswith("```"):
            in_cell = False
            rendered.append("")
        elif in_cell:
            rendered.append(line)
        else:
            rendered.append("")
    return "\n".join(rendered) + "\n"


def main() -> int:
    notebooks = sorted((ROOT / "notebooks").glob("*.qmd"))
    if not notebooks:
        print("No Quarto notebooks found.")
        return 0

    status = 0
    for path in notebooks:
        relative = path.relative_to(ROOT)
        reported_as = relative.with_suffix(".py")
        completed = subprocess.run(
            ["ruff", "check", "--stdin-filename", str(reported_as), "-"],
            input=python_cells(path.read_text()),
            text=True,
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        sys.stdout.write(completed.stdout.replace(str(reported_as), str(relative)))
        sys.stderr.write(completed.stderr.replace(str(reported_as), str(relative)))
        status = max(status, completed.returncode)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
