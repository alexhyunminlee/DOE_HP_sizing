# List available commands
default:
    @just --list

# Create .venv, install Python packages, and install pre-commit hooks
setup:
    uv sync
    uv run prek install --install-hooks

# Render every notebook to HTML under output/
render: setup
    quarto render

# Render one notebook. Usage: just render-one notebooks/eda.qmd
render-one file: setup
    quarto render {{ file }}

# Live-preview the notebooks in a browser
preview: setup
    quarto preview

# Run code quality tools
check: setup
    echo "🚀 Checking lock file consistency with 'pyproject.toml'"
    uv lock --locked
    echo "🚀 Linting and formatting code"
    uv run prek run -a

# Delete rendered HTML, Quarto's execution cache, and Ruff's cache
clean:
    rm -rf output .quarto .ruff_cache
