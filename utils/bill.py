"""Balance-point exploration of monthly utility-bill heat supply.

Split monthly points at the temperature difference that minimizes the overall
RMSE of a piecewise model (constant mean below the threshold, linear
regression above it), then plot average heat supply against average
indoor-outdoor temperature difference.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from utils.utils import (
    BTUH_TO_KW,
    INDOOR_TEMP_COLOR,
    SETPOINT_COLOR,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    load_utility_bill,
    load_weather,
    thermostat_dir,
)

MEAN_COLOR = "seagreen"
REGRESSION_COLOR = "darkorange"
DEFAULT_INDOOR_TEMP_F = 70.0


@dataclass(frozen=True)
class ThresholdFit:
    """Best split of monthly bill points, plus the per-hour series used to plot."""

    threshold_c: float
    total_rmse: float
    delta_temp_c: np.ndarray
    heat_supply_kw: np.ndarray
    lower_mean_kw: float
    intercept_kw: float | None
    slope_kw_per_k: float | None
    indoor_temp_c: float
    indoor_from_thermostat: bool


def mean_indoor_temperature(house_id: int) -> tuple[float, bool]:
    """Mean indoor temperature (°C) from thermostat ``data.csv``, or 70 °F."""
    path = thermostat_dir(house_id) / "data.csv"
    if not path.is_file():
        return fahrenheit_to_celsius(DEFAULT_INDOOR_TEMP_F), False
    indoor_f = pd.to_numeric(
        pd.read_csv(path, usecols=["indoor_temp_f"])["indoor_temp_f"],
        errors="coerce",
    ).dropna()
    if indoor_f.empty:
        return fahrenheit_to_celsius(DEFAULT_INDOOR_TEMP_F), False
    return float(fahrenheit_to_celsius(float(indoor_f.mean()))), True


def indoor_temperature_note(fit: ThresholdFit) -> str:
    """Markdown stating how indoor and outdoor temperatures were obtained."""
    indoor_f = celsius_to_fahrenheit(fit.indoor_temp_c)
    if fit.indoor_from_thermostat:
        indoor_source = (
            "Indoor temperature is the mean of `indoor_temp_f` in the house "
            f"thermostat `data.csv` ({indoor_f:.1f} °F / {fit.indoor_temp_c:.1f} °C)."
        )
    else:
        indoor_source = (
            "No thermostat `data.csv` was found, so indoor temperature is assumed "
            f"to be {DEFAULT_INDOOR_TEMP_F:.0f} °F ({fit.indoor_temp_c:.1f} °C)."
        )
    return (
        f"{indoor_source} Outdoor temperature is `temperature (degC)` in "
        "`weather_data.csv`.\n"
    )


def bill_period_features(
    bill: pd.DataFrame, indoor_c: float, outdoor: pd.Series
) -> pd.DataFrame:
    """Degree-hours and billed hours for each period with outdoor weather.

    Indoor temperature is a single value: the mean of thermostat ``data.csv``,
    or 70 °F if that file is missing. Outdoor temperature is
    ``temperature (degC)`` from ``weather_data.csv``. ``HeatSupply`` is billed
    energy in BTU. ``deltaTemp`` is the indoor-outdoor temperature difference
    times billed hours, so dividing both by ``TotalHours`` recovers average kW
    and average ΔT, as in ``dev/BillPreprocess.py``.
    """
    rows: list[dict[str, object]] = []
    for row in bill.itertuples(index=False):
        start = pd.Timestamp(row.start_date)
        end = pd.Timestamp(row.end_date)
        hours = (end + pd.Timedelta(days=1) - start) / pd.Timedelta(hours=1)
        if hours <= 0:
            continue
        outdoor_period = outdoor.loc[
            (outdoor.index >= start) & (outdoor.index < end + pd.Timedelta(days=1))
        ]
        if outdoor_period.empty:
            continue
        delta_c = indoor_c - float(outdoor_period.mean())
        rows.append(
            {
                "start_date": start,
                "end_date": end,
                "HeatSupply": float(row.consumption_btu),
                "TotalHours": float(hours),
                "deltaTemp": delta_c * hours,
            }
        )
    if not rows:
        message = "No billing periods overlap weather_data.csv."
        raise ValueError(message)
    return pd.DataFrame(rows)


def _rmse(observed: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((observed - predicted) ** 2)))


def _linear_coefficients(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(len(x)), x])
    return np.linalg.lstsq(design, y, rcond=None)[0]


def find_optimal_threshold(
    periods: pd.DataFrame, indoor_temp_c: float, indoor_from_thermostat: bool
) -> ThresholdFit:
    """Threshold that minimizes overall RMSE of the piecewise model.

    For each candidate split, months at or below the threshold are predicted
    by their mean and months above it by a linear fit. The score is RMSE over
    every month, not the sum of the two group RMSEs.
    """
    frame = periods.sort_values("deltaTemp").reset_index(drop=True)
    delta_temp = frame["deltaTemp"].to_numpy()
    heat_supply = frame["HeatSupply"].to_numpy()
    best_threshold = None
    best_rmse = float("inf")

    for index, threshold in enumerate(delta_temp):
        predicted = np.empty(len(heat_supply))
        predicted[: index + 1] = heat_supply[: index + 1].mean()
        upper_x = delta_temp[index + 1 :]
        upper_y = heat_supply[index + 1 :]
        if len(upper_x) > 1:
            intercept, slope = _linear_coefficients(upper_x, upper_y)
            predicted[index + 1 :] = intercept + slope * upper_x
        else:
            predicted[index + 1 :] = upper_y
        rmse = _rmse(heat_supply, predicted)
        if rmse < best_rmse:
            best_rmse = rmse
            best_threshold = float(threshold)

    if best_threshold is None:
        message = "Could not find a temperature-difference threshold."
        raise ValueError(message)

    mean_hours = float(frame["TotalHours"].mean())
    threshold_c = best_threshold / mean_hours
    delta_temp_c = (frame["deltaTemp"] / frame["TotalHours"]).to_numpy()
    heat_supply_kw = (frame["HeatSupply"] / frame["TotalHours"] * BTUH_TO_KW).to_numpy()
    lower = heat_supply_kw[delta_temp_c <= threshold_c]
    upper_x = delta_temp_c[delta_temp_c > threshold_c]
    upper_y = heat_supply_kw[delta_temp_c > threshold_c]
    intercept_kw = slope_kw_per_k = None
    if len(upper_x) > 1:
        intercept_kw, slope_kw_per_k = (
            float(value) for value in _linear_coefficients(upper_x, upper_y)
        )
    return ThresholdFit(
        threshold_c=threshold_c,
        total_rmse=best_rmse,
        delta_temp_c=delta_temp_c,
        heat_supply_kw=heat_supply_kw,
        lower_mean_kw=float(lower.mean()) if len(lower) else float("nan"),
        intercept_kw=intercept_kw,
        slope_kw_per_k=slope_kw_per_k,
        indoor_temp_c=indoor_temp_c,
        indoor_from_thermostat=indoor_from_thermostat,
    )


def plot_threshold_fit(fit: ThresholdFit) -> Figure:
    """Scatter of monthly averages with the constant-mean / linear split."""
    x, y = fit.delta_temp_c, fit.heat_supply_kw
    figure, axis = plt.subplots(figsize=(12, 8))
    axis.scatter(x, y, s=60, color=INDOOR_TEMP_COLOR, zorder=3, label="Monthly average")
    axis.axvline(
        fit.threshold_c,
        color=SETPOINT_COLOR,
        linestyle="--",
        zorder=2,
        label=r"$\tau^*$",
    )
    y_top = axis.get_ylim()[1]
    axis.text(
        fit.threshold_c,
        y_top * 0.8,
        rf"$\tau^*$ = {fit.threshold_c:.1f} °C",
        color=SETPOINT_COLOR,
        fontsize=mpl.rcParams["axes.labelsize"],
        rotation=90,
        ha="right",
        va="center",
    )
    if np.isfinite(fit.lower_mean_kw) and (x <= fit.threshold_c).any():
        x_lower = np.linspace(float(x.min()), fit.threshold_c, 100)
        axis.plot(
            x_lower,
            np.full_like(x_lower, fit.lower_mean_kw),
            color=MEAN_COLOR,
            label="Mean below threshold",
        )
    if (
        fit.intercept_kw is not None
        and fit.slope_kw_per_k is not None
        and (x > fit.threshold_c).any()
    ):
        x_upper = np.linspace(fit.threshold_c, float(x.max()), 100)
        axis.plot(
            x_upper,
            fit.intercept_kw + fit.slope_kw_per_k * x_upper,
            color=REGRESSION_COLOR,
            label="Linear fit above threshold",
        )
    axis.set_xlabel("Monthly average indoor-outdoor temperature difference, ΔT (°C)")
    axis.set_ylabel("Monthly average heat supply (kW)")
    axis.spines["right"].set_visible(False)
    axis.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.04),
        ncol=2,
        borderaxespad=0,
        frameon=True,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.90), pad=2.0)
    return figure


def load_bill_threshold_fit(bill_path: Path, house_id: int) -> ThresholdFit:
    """Read one bill CSV, join indoor and weather temperatures, and fit the split."""
    bill = load_utility_bill(bill_path)
    indoor_c, from_thermostat = mean_indoor_temperature(house_id)
    outdoor = load_weather(house_id)
    periods = bill_period_features(bill, indoor_c, outdoor)
    return find_optimal_threshold(periods, indoor_c, from_thermostat)
