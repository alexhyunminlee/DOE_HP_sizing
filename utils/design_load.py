"""Heating design load estimated from nighttime setback periods.

The pipeline has four steps, each a function below:

1. ``load_design_load_data``: read one thermostat CSV and derive heat supply.
2. ``nighttime_daily_averages``: extract each night's setback and recovery
   period and average it by day.
3. ``fit_1r1c``: fit heat supply = UA x (indoor - outdoor temperature) -
   internal gains by non-negative least squares.
4. ``predict_design_load``: extrapolate the fit to the design temperature
   difference with a prediction interval.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy import stats
from scipy.optimize import lsq_linear

from utils.utils import (
    BTUH_TO_KW,
    INDOOR_TEMP_COLOR,
    KW_TO_BTUH,
    SETPOINT_COLOR,
    fahrenheit_to_celsius,
    r_squared,
)

DESIGN_COLOR = "darkorange"


def load_design_load_data(
    path: Path,
    timestep_secs: float,
    q_max_btuh: float,
    heater_startup_secs: float,
) -> pd.DataFrame:
    """Indoor and outdoor temperature, runtime fraction, and heat supply.

    The runtime fraction (``rtf``) excludes the heater's start-up seconds from
    each interval in which the heat stage ran, and the heat supply in kW is
    that fraction of the stage's rated capacity. Duplicate timestamps and rows
    with missing values are dropped.

    Raises ValueError if no complete rows remain.
    """
    thermostat = pd.read_csv(path, parse_dates=["timestamp"])
    runtime_secs = thermostat["heat_stage_1_sec"]
    effective_secs = (runtime_secs - heater_startup_secs).clip(lower=0)
    rtf = effective_secs.where(runtime_secs > 0, 0.0) / timestep_secs
    data = pd.DataFrame(
        {
            "indoor_temp_c": fahrenheit_to_celsius(
                thermostat["indoor_temp_f"]
            ).to_numpy(),
            "outdoor_temp_c": fahrenheit_to_celsius(
                thermostat["outdoor_temp_f"]
            ).to_numpy(),
            "rtf": rtf.to_numpy(),
            "heat_supply_kw": (rtf * q_max_btuh * BTUH_TO_KW).to_numpy(),
        },
        index=pd.DatetimeIndex(thermostat["timestamp"], name="timestamp"),
    )
    data = data.loc[~data.index.duplicated(keep="first")].sort_index().dropna()
    if data.empty:
        message = f"{path.name} has no complete rows."
        raise ValueError(message)
    return data


def _minutes_of_day(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def nighttime_daily_averages(
    data: pd.DataFrame,
    setback_start: str = "21:00",
    setback_end: str = "13:00",
    minimum_rows_per_day: int = 60,
    minimum_rtf: float = 0.05,
    minimum_days: int = 4,
) -> pd.DataFrame:
    """Daily averages over each night's setback and recovery period.

    A night starts at the first interval at or after ``setback_start`` in
    which the heater is off, and runs until the first interval after
    ``setback_end`` the next day. The extracted rows are averaged by calendar
    day. Days with fewer than ``minimum_rows_per_day`` rows or an average
    runtime fraction at or below ``minimum_rtf`` are dropped.

    Raises ValueError if fewer than ``minimum_days`` days remain.
    """
    start_minute = _minutes_of_day(setback_start)
    end_minute = _minutes_of_day(setback_end)
    minutes = (data.index.hour * 60 + data.index.minute).to_numpy()
    rtf = data["rtf"].to_numpy()
    n_rows = len(data)

    evening = data.index[minutes >= start_minute]
    segments = []
    for day in evening.normalize().unique()[:-1]:
        position = data.index.get_loc(evening[evening.normalize() == day][0])
        while position < n_rows and rtf[position] > 0:
            position += 1
        start = position
        while position < n_rows and (
            minutes[position] <= end_minute or minutes[position] >= start_minute
        ):
            position += 1
        if position >= n_rows:
            break
        segments.append(data.iloc[start : position + 1])
    if not segments:
        message = "No nighttime setback periods were found."
        raise ValueError(message)

    nights = pd.concat(segments)
    by_day = nights.groupby(nights.index.normalize())
    daily = by_day.mean().loc[by_day.size() >= minimum_rows_per_day]
    daily = daily.loc[daily["rtf"] > minimum_rtf]
    daily.index.name = "day"
    if len(daily) < minimum_days:
        message = (
            f"Only {len(daily)} usable days after preprocessing; "
            f"at least {minimum_days} are needed."
        )
        raise ValueError(message)
    return daily


@dataclass(frozen=True)
class Fit1R1C:
    """Heat supply (kW) = ua_kw_per_k x temperature difference - internal_gain_kw."""

    ua_kw_per_k: float
    internal_gain_kw: float
    delta_temp_c: np.ndarray
    heat_supply_kw: np.ndarray
    r_squared: float
    f_value: float
    f_critical: float

    @property
    def n_days(self) -> int:
        return len(self.delta_temp_c)

    @property
    def degrees_of_freedom(self) -> int:
        return self.n_days - 2

    @property
    def r_value_k_per_kw(self) -> float:
        return 1 / self.ua_kw_per_k

    @property
    def internal_gain_btuh(self) -> float:
        return self.internal_gain_kw * KW_TO_BTUH

    @property
    def is_significant(self) -> bool:
        return self.f_value > self.f_critical

    @property
    def coefficients(self) -> np.ndarray:
        return np.array([self.ua_kw_per_k, self.internal_gain_kw])

    def design_matrix(self, delta_temp_c: np.ndarray) -> np.ndarray:
        return np.column_stack([delta_temp_c, -np.ones(len(delta_temp_c))])

    def predict_kw(self, delta_temp_c: np.ndarray) -> np.ndarray:
        return self.design_matrix(delta_temp_c) @ self.coefficients

    def prediction_std_kw(self, delta_temp_c: np.ndarray) -> np.ndarray:
        """Standard error of a new day's heat supply at each temperature difference."""
        fitted = self.design_matrix(self.delta_temp_c)
        residuals = self.heat_supply_kw - fitted @ self.coefficients
        mse = float(np.sum(residuals**2)) / self.degrees_of_freedom
        points = self.design_matrix(np.atleast_1d(delta_temp_c))
        inverse_gram = np.linalg.inv(fitted.T @ fitted)
        leverage = np.einsum("ij,jk,ik->i", points, inverse_gram, points)
        return np.sqrt(mse * (1 + leverage))

    def prediction_interval_kw(
        self, delta_temp_c: np.ndarray, confidence: float
    ) -> tuple[np.ndarray, np.ndarray]:
        """Lower and upper prediction bounds for a new day's heat supply."""
        t_value = float(stats.t.ppf(1 - (1 - confidence) / 2, self.degrees_of_freedom))
        center = self.predict_kw(np.atleast_1d(delta_temp_c))
        half_width = t_value * self.prediction_std_kw(delta_temp_c)
        return center - half_width, center + half_width


def fit_1r1c(daily: pd.DataFrame, alpha: float = 0.05) -> Fit1R1C:
    """Fit the 1R1C model once to every day from ``nighttime_daily_averages``.

    The F-test compares the fit against predicting the mean heat supply at
    significance ``alpha``.
    """
    delta_temp_c = (daily["indoor_temp_c"] - daily["outdoor_temp_c"]).to_numpy()
    heat_supply_kw = daily["heat_supply_kw"].to_numpy()
    if len(daily) <= 2 or np.ptp(delta_temp_c) == 0:
        message = "Not enough variation in the daily data to fit the model."
        raise ValueError(message)
    design = np.column_stack([delta_temp_c, -np.ones(len(daily))])
    coefficients = lsq_linear(design, heat_supply_kw, bounds=(0, np.inf)).x
    predicted = design @ coefficients
    dof = len(daily) - 2
    sse_mean_only = float(np.sum((heat_supply_kw - heat_supply_kw.mean()) ** 2))
    sse_model = float(np.sum((heat_supply_kw - predicted) ** 2))
    return Fit1R1C(
        ua_kw_per_k=float(coefficients[0]),
        internal_gain_kw=float(coefficients[1]),
        delta_temp_c=delta_temp_c,
        heat_supply_kw=heat_supply_kw,
        r_squared=r_squared(predicted, heat_supply_kw),
        f_value=(sse_mean_only - sse_model) / (sse_model / dof),
        f_critical=float(stats.f.ppf(1 - alpha, 1, dof)),
    )


@dataclass(frozen=True)
class DesignLoad:
    """Predicted heat supply at the design temperature difference, in kW."""

    delta_temp_c: float
    kw: float
    lower_kw: float
    upper_kw: float
    confidence: float

    @property
    def btuh(self) -> float:
        return self.kw * KW_TO_BTUH

    @property
    def lower_btuh(self) -> float:
        return self.lower_kw * KW_TO_BTUH

    @property
    def upper_btuh(self) -> float:
        return self.upper_kw * KW_TO_BTUH


def predict_design_load(
    fit: Fit1R1C, design_delta_temp_c: float, confidence: float = 0.95
) -> DesignLoad:
    """Extrapolate the fit to the design conditions with a prediction interval."""
    lower, upper = fit.prediction_interval_kw(design_delta_temp_c, confidence)
    return DesignLoad(
        delta_temp_c=design_delta_temp_c,
        kw=float(fit.predict_kw(np.array([design_delta_temp_c]))[0]),
        lower_kw=float(lower[0]),
        upper_kw=float(upper[0]),
        confidence=confidence,
    )


def plot_1r1c_fit(fit: Fit1R1C, design: DesignLoad) -> Figure:
    """Daily heat supply against temperature difference, following dev/Figure.py.

    Shows the regression line with its prediction band, and marks the design
    temperature difference with a bar spanning the prediction interval.
    """
    x, y = fit.delta_temp_c, fit.heat_supply_kw
    x_min = min(x.min(), design.delta_temp_c) - 0.5
    x_max = max(x.max(), design.delta_temp_c) + 0.5
    line_x = np.linspace(x_min, x_max, 100)
    lower, upper = fit.prediction_interval_kw(line_x, design.confidence)

    figure, axis = plt.subplots(figsize=(12, 8))
    axis.scatter(x, y, s=30, color=INDOOR_TEMP_COLOR, zorder=3, label="Nightly average")
    axis.plot(
        line_x,
        fit.predict_kw(line_x),
        color=SETPOINT_COLOR,
        linewidth=2,
        label=f"y = {fit.ua_kw_per_k:.2f}x - {fit.internal_gain_kw:.2f}",
    )
    axis.fill_between(
        line_x,
        lower,
        upper,
        color=SETPOINT_COLOR,
        alpha=0.2,
        linewidth=0,
        label=f"{design.confidence:.0%} prediction interval",
    )

    # Design point: a bar spanning the interval, with caps and a drop line.
    design_x = design.delta_temp_c
    design_style = {"color": DESIGN_COLOR, "linewidth": 5, "alpha": 0.75, "zorder": 2}
    cap = (x.max() - x.min()) * 0.015
    axis.plot([design_x, design_x], [design.lower_kw, design.upper_kw], **design_style)
    for level in (design.lower_kw, design.upper_kw):
        axis.plot([design_x - cap, design_x + cap], [level, level], **design_style)
    axis.plot(
        [design_x, design_x],
        [0, design.lower_kw],
        color=DESIGN_COLOR,
        linewidth=3,
        linestyle="dashed",
        zorder=2,
    )
    axis.text(
        design_x - (x.max() - x.min()) * 0.02,
        design.lower_kw / 2,
        f"Design ΔT = {design_x:.1f} °C",
        color=DESIGN_COLOR,
        fontsize=mpl.rcParams["axes.labelsize"],
        horizontalalignment="right",
        verticalalignment="center",
    )

    axis.set_xlabel("Indoor-outdoor temperature difference, ΔT (°C)")
    axis.set_ylabel("Nightly average heat supply (kW)")
    axis.set_xlim(x_min, x_max)
    axis.set_ylim(0, max(upper.max(), y.max()) * 1.05)
    axis.spines["right"].set_visible(False)
    axis.legend(loc="upper left")
    figure.tight_layout(pad=2.0)
    return figure
