"""Compare improvement scenarios against the baseline and quantify the deltas."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from fabflow.analysis.kpis import scenario_kpis

# Higher-is-better vs lower-is-better, for signing the improvement.
_LOWER_BETTER = {"mean_cycle_time_h", "p95_cycle_time_h", "mean_x_factor", "cycle_time_cv"}
_HIGHER_BETTER = {"lots_out_per_week", "wafers_out_per_week", "on_time_delivery"}
# Deltas are computed on the point-estimate metrics only (not the _std/_ci95 columns).
_DELTA_METRICS = _LOWER_BETTER | _HIGHER_BETTER


def improvement_deltas(db_path: Path, horizon_hours: float, warmup_hours: float,
                       baseline: str = "baseline") -> pd.DataFrame:
    """Signed % improvement of each scenario vs baseline (positive = better)."""
    kpi = scenario_kpis(db_path, horizon_hours, warmup_hours)
    base = kpi.loc[baseline]
    metric_cols = [c for c in kpi.columns if c in _DELTA_METRICS]
    out = {}
    for scen in kpi.index:
        if scen == baseline:
            continue
        row = {}
        for col in metric_cols:
            b, v = base[col], kpi.loc[scen, col]
            if b == 0:
                row[col] = 0.0
                continue
            pct = (v - b) / abs(b) * 100
            # sign so that positive always means "better"
            if col in _LOWER_BETTER:
                pct = -pct
            row[col] = round(pct, 2)
        out[scen] = row
    return pd.DataFrame(out).T
