# DOE HP sizing

Research data and Quarto notebooks for heat pump sizing. The data are
thermostat logs from individual houses, stored as CSVs under `data/`. The
notebooks under `notebooks/` do exploratory analysis on them. This is not a
Python package; it is a small, self-contained repo for holding data and
rendering a few reports.

The only tools you install yourself are `git`, `uv`, and `just`. Everything
else is pinned in `uv.lock` and installed into the repo's `.venv` by
`just setup`: Python 3.12, every Python package, and Quarto, which includes
the Typst engine that makes the PDFs. Nothing uses a Python, Quarto, or LaTeX
installed elsewhere on your computer. The PDF font, TeX Gyre Termes, is
committed under `fonts/`.

## Setup

You only do this once. Pick your operating system, open a terminal, and paste
each block in order. If a command asks for your password or to confirm, say
yes.

### Mac

Open **Terminal** (press `Cmd + Space`, type `Terminal`, press Enter).

```sh
# 1. Install Homebrew, a tool that installs other tools
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install the tools this repo uses
brew install git uv just

# 3. Download this repo and move into it
git clone https://github.com/alexhyunminlee/DOE_HP_sizing.git
cd DOE_HP_sizing

# 4. Set up the environment
just setup
```

### Windows

Open **PowerShell** (press the Windows key, type `PowerShell`, press Enter).

```powershell
# 1. Install the tools this repo uses
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
winget install --id Casey.Just -e
```

Close PowerShell and open it again so the new tools are found, then:

```powershell
# 2. Download this repo and move into it
git clone https://github.com/alexhyunminlee/DOE_HP_sizing.git
cd DOE_HP_sizing

# 3. Set up the environment
just setup
```

The commands in this repo use Unix-style shell syntax. Git for Windows (step 1)
includes a shell that understands it, and `just` finds and uses it
automatically, so the recipes work from PowerShell.

### Linux (Ubuntu / Debian)

```sh
# 1. Install the tools this repo uses
sudo apt update && sudo apt install -y git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
```

Close the terminal and open a new one so the new tools are found, then:

```sh
# 2. Download this repo and move into it
git clone https://github.com/alexhyunminlee/DOE_HP_sizing.git
cd DOE_HP_sizing

# 3. Set up the environment
just setup
```

## Viewing the results

After setup, from inside the `DOE_HP_sizing` folder (there is nothing to
activate first; the `just` commands use the project's environment on their
own):

```sh
just thermostat-eda 52
```

This builds the thermostat report for house `00052` and saves it as
`output/house_00052/house_00052_eda.pdf`. The terminal prints the location when
it finishes.
Double-click the PDF to open it.

Swap `52` for any other house number that has a folder under `data/thermostat/`.

To estimate the heating design load for a house:

```sh
just thermostat-design-load 52
```

This saves `output/house_00052/house_00052_design_load.pdf`.

To explore one house's utility bills against thermostat temperatures:

```sh
just bill-eda 1
```

This saves `output/house_00001/house_00001_bill_eda.pdf`.

If you come back later and the repo has changed, run `git pull` inside the
folder to get the latest version, then `just setup` again.

## Data

All data are plain CSVs in `data/`.

### `data/metadata/survey.csv`

One row per house (74 houses) with the homeowner survey responses. The
`house_id` is a zero-padded five-digit string (for example `00052`) and is the
key that links to the thermostat folders below. Every other column is prefixed
`survey.` to mark its source:

| Column                               | Meaning                                                                       |
| ------------------------------------ | ----------------------------------------------------------------------------- |
| `house_id`                           | Zero-padded five-digit house ID                                               |
| `survey.city`, `survey.state`        | Location of the house                                                         |
| `survey.conditioned_floor_area_sqft` | Conditioned floor area reported by the homeowner, ft²                         |
| `survey.original_construction_year`  | Year the house was built                                                      |
| `survey.n_floors`                    | Number of floors (`1`, `1.5`, `2`, or `3`)                                    |
| `survey.house_type`                  | Housing type, for example `Single Family Detached`; `Unknown` if not reported |

### `data/thermostat/house_<house_id>/`

One folder per house, named with the same zero-padded ID
(`data/thermostat/house_00052/`). Each folder holds that house's thermostat
logs, for example `thermostat_data_1.csv`. Readings are at a 5-minute timestep.
Currently only house `00052` has data (135,648 rows, about 15 months).

The columns have been normalized to `snake_case` with units in the name:

| Column                                      | Meaning                                                   |
| ------------------------------------------- | --------------------------------------------------------- |
| `timestamp`                                 | Reading time, `YYYY-MM-DD HH:MM:SS`                       |
| `system_setting`, `system_mode`             | Thermostat setting (e.g. `heat`) and current mode         |
| `program_mode`                              | Schedule state: `Home`, `Sleep`, `Away`                   |
| `heat_setpoint_f`, `cool_setpoint_f`        | Setpoints, °F                                             |
| `indoor_temp_f`, `indoor_humidity_pct`      | Indoor conditions at the thermostat                       |
| `outdoor_temp_f`, `wind_speed_kmh`          | Outdoor weather                                           |
| `heat_stage_1_sec`, `cool_stage_1_sec`      | Seconds the stage ran during the 5-minute interval        |
| `fan_sec`                                   | Seconds the fan ran during the interval                   |
| `thermostat_temp_f`, `thermostat_motion`, … | Thermostat sensor readings (humidity, VOC, CO₂, pressure) |
| `family_room_temp_f`, `bedroom_temp_f`, …   | Remote room sensor temperatures, °F                       |

To add a house, create `data/thermostat/house_<id>/` and drop its CSVs in. The
large-file check in the pre-commit hooks is turned off for `data/`, so files of
this size commit fine.

### `data/utility_bill/house_<house_id>/`

One folder per house, same `house_id` as the thermostat folders. Each folder
holds that house's gas-bill CSV as `data.csv`, with one row per billing
period, and hourly outdoor weather as `weather_data.csv` (ERA5
`temperature (degC)`):

| Column                                    | Meaning                                    |
| ----------------------------------------- | ------------------------------------------ |
| `start_date`, `end_date`                  | Inclusive first and last day of the period |
| `consumption_therms` or `consumption_ccf` | Billed use in the original unit            |
| `consumption_btu`                         | The same use converted to BTU              |

## Notebooks

Quarto notebooks (`.qmd`) live under `notebooks/`. Rendering runs the Python in
each one and writes HTML to `output/` (gitignored). Rendering always
re-executes the code, so new data show up without editing the notebooks.

| Notebook                               | What it does                                                                                                                                                                                                                                                                                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `notebooks/eda.qmd`                    | Generic summary of every CSV directly inside `data/`: shape, column types, missing values, numeric summary, and histograms.                                                                                                                                                                                                                       |
| `notebooks/thermostat/eda.qmd`         | Thermostat exploration for one house. Converts temperatures to °C, computes heat-stage runtime fraction per interval, splits out `Sleep` and `Away` periods, and plots about three days of heat setpoint vs. indoor temperature to show nighttime setback patterns.                                                                               |
| `notebooks/thermostat/design_load.qmd` | Heating design load for one house. Extracts each nighttime setback and recovery period, averages by day, fits a 1R1C model once by non-negative least squares, and extrapolates to design conditions with a 95% prediction interval.                                                                                                              |
| `notebooks/bill/eda.qmd`               | Utility-bill exploration for one house. Joins each billing period to the mean thermostat indoor temperature (or 70 °F if `data.csv` is missing) and ERA5 outdoor `temperature (degC)` from `weather_data.csv`, finds the $\Delta T$ threshold that splits baseload from heating months, and plots monthly average heat supply against $\Delta T$. |

The thermostat and bill notebooks read the house number from the `HOUSE_ID`
environment variable (set for you by `just thermostat-eda <id>`,
`just thermostat-design-load <id>`, and `just bill-eda <id>`) and process every
CSV in that house's folder, each on its own page.

## For contributors

These commands are for developing the notebooks. The report commands above
are the only ones meant for people viewing results.

| Command                      | What it does                                           |
| ---------------------------- | ------------------------------------------------------ |
| `just`                       | List all commands                                      |
| `just render`                | Build the general data-summary report into `output/`   |
| `just render-one <file.qmd>` | Build one notebook                                     |
| `just preview`               | Live preview that rebuilds when a notebook changes     |
| `just check`                 | Format and lint everything (also runs on `git commit`) |
| `just clean`                 | Delete built reports and caches                        |

`just render` skips the thermostat and bill notebooks because they need a house
number.
To add an analysis, create a new `.qmd` under `notebooks/` and run
`just render`. File paths inside notebooks are relative to the repo root, so
`Path("data") / ...` works from any subfolder.

`just check` fixes files in place. If it reports a failure because it changed
something, run it again to confirm the tree is clean.

### Layout

| Path                      | Purpose                                                      |
| ------------------------- | ------------------------------------------------------------ |
| `data/metadata/`          | Homeowner survey responses (one row per house).              |
| `data/thermostat/`        | Per-house thermostat CSVs, one folder per `house_id`.        |
| `data/utility_bill/`      | Per-house gas-bill CSVs, one folder per `house_id`.          |
| `notebooks/`              | Quarto notebooks.                                            |
| `output/`                 | Built reports. Not committed.                                |
| `Justfile`                | The `just` commands listed above.                            |
| `fonts/`                  | TeX Gyre Termes, the font used in every PDF and figure.      |
| `pyproject.toml`          | Python version and dependencies, including Quarto.           |
| `uv.lock`                 | Exact dependency versions. Commit changes to it.             |
| `_quarto.yml`             | Quarto project settings.                                     |
| `.pre-commit-config.yaml` | Formatting and lint hooks run by `just check` and on commit. |
