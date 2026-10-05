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
    quarto render {{file}}

# Live-preview the notebooks in a browser
preview: setup
    quarto preview

# Delete rendered HTML and Quarto's execution cache
clean:
    rm -rf output .quarto
