"""Helpers shared by the notebooks."""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

# Figure style used across notebooks (matches dev/data_preprocessing_fig.py).
SETPOINT_COLOR = "crimson"
INDOOR_TEMP_COLOR = "mediumblue"
HIGHLIGHT_COLOR = "lightpink"
LINE_WIDTH = 3

# Unit conversions.
BTUH_TO_KW = 0.000293071
KW_TO_BTUH = 1 / BTUH_TO_KW


def apply_journal_style() -> None:
    """Serif fonts and open spines, in the style of a journal figure."""
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "STIXGeneral", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "axes.spines.top": False,
            "axes.labelsize": 22,
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "legend.fontsize": 20,
            "legend.framealpha": 1.0,
            "lines.linewidth": LINE_WIDTH,
            "figure.dpi": 150,
        }
    )


def first_complete_window(
    data: pd.DataFrame,
    duration: pd.Timedelta,
    step: pd.Timedelta,
    columns: list[str],
) -> pd.DataFrame | None:
    """Earliest slice spanning `duration` with no missing readings.

    Every `step` from the slice's first timestamp through one step before
    `duration` has elapsed must be present, and `columns` must be non-null
    there. Duplicate timestamps are ignored. Returns None when no slice
    qualifies, including when `duration` is shorter than one `step`.
    """
    if data.empty or duration < step:
        return None
    readings = int(duration // step)
    deduped = data.loc[~data.index.duplicated(keep="first")].sort_index()
    if len(deduped) < readings:
        return None
    index = deduped.index
    span = (readings - 1) * step
    starts = index[: len(index) - readings + 1]
    ends = index[readings - 1 :]
    span_ok = (ends - starts) == span
    filled = deduped[columns].notna().all(axis=1)
    filled_windows = filled.rolling(readings).sum().eq(readings).to_numpy()
    complete = np.asarray(span_ok) & filled_windows[readings - 1 :]
    if not complete.any():
        return None
    start = int(complete.argmax())
    return deduped.iloc[start : start + readings]


def contiguous_blocks(
    index: pd.DatetimeIndex, step: pd.Timedelta
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Start and end of each run of timestamps spaced no more than `step` apart.

    The end of a block is extended by one step so a shaded span covers the
    last interval, as in dev/data_preprocessing_fig.py.
    """
    if index.empty:
        return []
    gaps = index.to_series().diff().fillna(pd.Timedelta(0))
    block_ids = (gaps > step).cumsum()
    return [
        (block.index[0], block.index[-1] + step)
        for _, block in index.to_series().groupby(block_ids)
    ]


def project_root() -> Path:
    """Directory that contains pyproject.toml.

    Quarto sometimes executes a notebook from the notebook's own folder, so
    this checks the working directory, QUARTO_PROJECT_DIR, and their parents.
    """
    starts = [Path.cwd()]
    if project_dir := os.environ.get("QUARTO_PROJECT_DIR"):
        starts.append(Path(project_dir))
    for start in starts:
        for candidate in [start, *start.parents]:
            if (candidate / "pyproject.toml").is_file():
                return candidate
    message = "Could not find the project root (pyproject.toml)."
    raise FileNotFoundError(message)


def fahrenheit_to_celsius[T: (float, pd.Series)](temperature_f: T) -> T:
    return (temperature_f - 32) * 5 / 9


def celsius_to_fahrenheit[T: (float, pd.Series)](temperature_c: T) -> T:
    return temperature_c * 9 / 5 + 32


def thermostat_dir(house_id: int) -> Path:
    return project_root() / "data" / "thermostat" / f"house_{house_id:05d}"


def thermostat_csv_files(house_id: int) -> list[Path]:
    return sorted(
        path for path in thermostat_dir(house_id).glob("*.csv") if path.is_file()
    )


def load_thermostat(path: Path, timestep_secs: float) -> pd.DataFrame:
    """One thermostat CSV, with temperatures in Celsius and a runtime fraction.

    The runtime fraction is seconds the heat stage ran divided by the length of
    one timestep.
    """
    thermostat = pd.read_csv(path, parse_dates=["timestamp"])
    return pd.DataFrame(
        {
            "indoor_temp_c": fahrenheit_to_celsius(
                thermostat["indoor_temp_f"]
            ).to_numpy(),
            "outdoor_temp_c": fahrenheit_to_celsius(
                thermostat["outdoor_temp_f"]
            ).to_numpy(),
            "heat_setpoint_c": fahrenheit_to_celsius(
                thermostat["heat_setpoint_f"]
            ).to_numpy(),
            "runtime_fraction": (
                thermostat["heat_stage_1_sec"] / timestep_secs
            ).to_numpy(),
            "program_mode": thermostat["program_mode"].to_numpy(),
        },
        index=pd.DatetimeIndex(thermostat["timestamp"], name="timestamp"),
    )


def markdown_table(
    rows: list[list[str]], header: list[str], caption: str | None = None
) -> str:
    """Pipe-delimited table for printing into a Quarto document."""
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    if caption:
        lines.extend(["", f": {caption}"])
    return "\n".join(lines)


def r_squared(predicted: np.ndarray, observed: np.ndarray) -> float:
    residual_sum = float(np.sum((observed - predicted) ** 2))
    total_sum = float(np.sum((observed - observed.mean()) ** 2))
    return 1 - residual_sum / total_sum
