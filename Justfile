# List available commands
default:
    @just --list

# Create .venv, install Python packages, and install pre-commit hooks
setup:
    uv sync
    uv run prek install --install-hooks

# Render every notebook to HTML under output/
render: setup
    uv run quarto render

# Render one notebook. Usage: just render-one notebooks/eda.qmd
render-one file: setup
    uv run quarto render {{ file }}

# Live-preview the notebooks in a browser
preview: setup
    uv run quarto preview

# Render one house's thermostat report to output/house_#####/. Usage: just thermostat-eda 52
thermostat-eda house_id: setup
    @just _render-house {{ house_id }} eda

# Estimate one house's heating design load to output/house_#####/. Usage: just thermostat-design-load 52
thermostat-design-load house_id: setup
    @just _render-house {{ house_id }} design_load

# Render notebooks/thermostat/<notebook>.qmd for one house to output/house_#####/house_#####_<notebook>.pdf
_render-house house_id notebook:
    #!/usr/bin/env bash
    set -euo pipefail
    house="house_$(printf '%05d' {{ house_id }})"
    mkdir -p "output/$house"
    HOUSE_ID={{ house_id }} uv run quarto render notebooks/thermostat/{{ notebook }}.qmd --to pdf --no-clean
    mv notebooks/thermostat/{{ notebook }}.pdf "output/$house/${house}_{{ notebook }}.pdf"
    rm -rf output/notebooks/thermostat
    echo ""
    echo "Done. The report is at: output/$house/${house}_{{ notebook }}.pdf"

# Run code quality tools
check: setup
    echo "🚀 Checking lock file consistency with 'pyproject.toml'"
    uv lock --locked
    echo "🚀 Linting and formatting code"
    uv run prek run -a

# Delete rendered HTML, Quarto's execution cache, and Ruff's cache
clean:
    rm -rf output .quarto .ruff_cache
