# DOE HP sizing

Research CSVs and a few Quarto notebooks. This is not a Python package. Drop data in `data/`, then render the notebooks.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [Quarto](https://quarto.org/docs/get-started/)
- [just](https://just.systems/)

## Setup

```sh
just setup
source .venv/bin/activate
```

`just setup` creates `.venv`, installs the Python packages the notebooks need, and installs the pre-commit hooks. Activate that environment when you want to use Python directly. Rendering does not require the activation step; Quarto picks up `.venv` on its own.

## Notebooks

Put CSV files in `data/`. Render everything with:

```sh
just render
```

HTML is written to `output/`. Rendering always re-executes the notebooks, so updates in `data/` show up without editing the `.qmd` files. One notebook is included:

- `notebooks/eda.qmd` summarizes each CSV (shape, types, missing values, a numeric summary, and histograms).

Add another analysis by creating a `.qmd` file under `notebooks/` and running `just render` again. To render a single file:

```sh
just render-one notebooks/eda.qmd
```

`just preview` opens a live preview. `just clean` deletes `output/` and Quarto's cache.

`just check` checks that `uv.lock` matches `pyproject.toml`, then runs the pre-commit hooks (`uv run prek run -a`). Those hooks fix formatting and lint issues in place. If a hook changes a file, the command fails; run it again to confirm everything is clean. The same hooks run on `git commit` after `just setup`.

## Layout

| Path         | Purpose                                             |
| ------------ | --------------------------------------------------- |
| `data/`      | CSV inputs. Not generated.                          |
| `notebooks/` | Quarto source files.                                |
| `output/`    | Rendered HTML. Gitignored.                          |
| `Justfile`   | `setup`, `render`, `preview`, `check`, and `clean`. |
