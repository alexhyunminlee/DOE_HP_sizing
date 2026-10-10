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

# Render one house's thermostat report to a PDF in output/. Usage: just thermostat-eda 52
thermostat-eda house_id: setup
    mkdir -p output
    HOUSE_ID={{ house_id }} uv run quarto render notebooks/thermostat/eda.qmd --to pdf --no-clean
    mv notebooks/thermostat/eda.pdf output/house_{{ house_id }}.pdf
    rm -rf output/notebooks/thermostat
    @echo ""
    @echo "Done. The report is at: output/house_{{ house_id }}.pdf"

# Run code quality tools
check: setup
    echo "🚀 Checking lock file consistency with 'pyproject.toml'"
    uv lock --locked
    echo "🚀 Linting and formatting code"
    uv run prek run -a

# Delete rendered HTML, Quarto's execution cache, and Ruff's cache
clean:
    rm -rf output .quarto .ruff_cache
