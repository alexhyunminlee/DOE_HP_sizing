# List available commands
default:
    @just --list

# Create .venv and install Python packages
setup:
    uv sync

# Render every notebook to HTML under output/
render: setup
    quarto render

# Render one notebook. Usage: just render-one notebooks/eda.qmd
render-one file: setup
    quarto render {{ file }}

# Live-preview the notebooks in a browser
preview: setup
    quarto preview

# Lint and check formatting. Does not modify files.
check: setup
    uv run ruff check .
    uv run python scripts/lint_notebooks.py
    uv run ruff format --check .
    # `just --fmt` is still marked unstable; --unstable enables only this invocation.
    just --unstable --fmt --check

# Delete rendered HTML and Quarto's execution cache
clean:
    rm -rf output .quarto
