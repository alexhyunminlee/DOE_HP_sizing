# Python, Quarto (with its bundled Typst PDF engine), and every package come
# from .venv, pinned in uv.lock. These variables stop Quarto and Jupyter from
# picking up a Python or kernel installed elsewhere on the machine.

venv_python := justfile_directory() / if os_family() == "windows" { ".venv/Scripts/python.exe" } else { ".venv/bin/python" }
export QUARTO_PYTHON := venv_python
export JUPYTER_PATH := justfile_directory() / ".venv" / "share" / "jupyter"

# List available commands
default:
    @just --list

# Create .venv with the pinned Python and packages, and install pre-commit hooks
setup:
    uv sync --locked
    uv run --locked prek install --install-hooks

# Render every notebook to HTML under output/
render: setup
    uv run --locked quarto render

# Render one notebook. Usage: just render-one notebooks/eda.qmd
render-one file: setup
    uv run --locked quarto render {{ file }}

# Live-preview the notebooks in a browser
preview: setup
    uv run --locked quarto preview

# Render one house's thermostat report to output/house_#####/. Usage: just thermostat-eda 52
thermostat-eda house_id: setup
    @just _render-house {{ house_id }} eda

# Estimate one house's heating design load to output/house_#####/. Usage: just thermostat-design-load 52
thermostat-design-load house_id: setup
    @just _render-house {{ house_id }} design_load

# Render one house's utility-bill report to output/house_#####/. Usage: just bill-eda 1
bill-eda house_id: setup
    @just _render-bill {{ house_id }} eda

# Render notebooks/thermostat/<notebook>.qmd for one house to output/house_#####/house_#####_<notebook>.pdf
_render-house house_id notebook:
    #!/usr/bin/env bash
    set -euo pipefail
    house="house_$(printf '%05d' {{ house_id }})"
    mkdir -p "output/$house"
    HOUSE_ID={{ house_id }} uv run --locked quarto render notebooks/thermostat/{{ notebook }}.qmd --to typst --no-clean
    mv notebooks/thermostat/{{ notebook }}.pdf "output/$house/${house}_{{ notebook }}.pdf"
    rm -rf output/notebooks/thermostat
    echo ""
    echo "Done. The report is at: output/$house/${house}_{{ notebook }}.pdf"

# Render notebooks/bill/<notebook>.qmd for one house to output/house_#####/house_#####_bill_<notebook>.pdf
_render-bill house_id notebook:
    #!/usr/bin/env bash
    set -euo pipefail
    house="house_$(printf '%05d' {{ house_id }})"
    mkdir -p "output/$house"
    HOUSE_ID={{ house_id }} uv run --locked quarto render notebooks/bill/{{ notebook }}.qmd --to typst --no-clean
    mv notebooks/bill/{{ notebook }}.pdf "output/$house/${house}_bill_{{ notebook }}.pdf"
    rm -rf output/notebooks/bill
    echo ""
    echo "Done. The report is at: output/$house/${house}_bill_{{ notebook }}.pdf"

# Run code quality tools
check: setup
    echo "🚀 Checking lock file consistency with 'pyproject.toml'"
    uv lock --locked
    echo "🚀 Linting and formatting code"
    uv run prek run -a

# Delete rendered HTML, Quarto's execution cache, and Ruff's cache
clean:
    rm -rf output .quarto .ruff_cache
