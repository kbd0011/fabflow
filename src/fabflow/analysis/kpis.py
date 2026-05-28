"""Fab KPI computation from the DuckDB warehouse.

KPIs (the language a yield/IE engineer speaks):
- Cycle time (CT): release -> completion, mean and percentiles.
- X-factor (flow factor): CT / raw process time. The canonical fab metric; >=1,
  lower is better. ~1 is a perfectly flowing fab; 3+ means heavy queueing.
- Throughput: lots and wafer-outs completed per simulated week.
- WIP: time-average work in progress (Little's Law cross-check: WIP = TH * CT).
- Tool-group utilization: busy / available time; identifies the bottleneck.
- On-time delivery (OTD): fraction of lots completed by their due date.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

# KPI point estimates reported by scenario_kpis. The std/CI columns are derived
# from the per-rep spread of these same quantities (mean over reps +/- t-based CI).
_KPI_METRICS = [
    "lots_out_per_week",
    "wafers_out_per_week",
    "mean_cycle_time_h",
    "p95_cycle_time_h",
    "mean_x_factor",
    "on_time_delivery",
    "cycle_time_cv",
]


def _con(db_path: Path):
    return duckdb.connect(str(Path(db_path)), read_only=True)


def _ci_halfwidth(values: np.ndarray, confidence: float = 0.95) -> float:
    """t-distribution 95% confidence-interval half-width for a mean over `n` reps.

    Returns 0.0 with fewer than 2 reps (no spread to estimate). Uses the Student-t
    critical value (small-n correct) rather than the normal approximation.
    """
    values = np.asarray(values, dtype=float)
    n = values.size
    if n < 2:
        return 0.0
    sem = values.std(ddof=1) / np.sqrt(n)
    t_crit = stats.t.ppf(0.5 + confidence / 2.0, df=n - 1)
    return float(t_crit * sem)


def scenario_kpis(db_path: Path, horizon_hours: float, warmup_hours: float) -> pd.DataFrame:
    """One KPI row per scenario: point estimate (mean over reps) plus per-rep std and
    95% t-CI half-width for each metric (``<metric>_std`` and ``<metric>_ci95`` columns).

    On-time delivery uses a POOLED ratio (1 - total tardy / total lots across all reps)
    to match the BI definitions in ``export/bi_export.py`` and ``docs/tableau_guide.md``;
    its std/CI are still derived from the per-rep OTD ratios so the spread is reported.
    """
    span_weeks = (horizon_hours - warmup_hours) / (24 * 7)
    con = _con(db_path)
    try:
        lot = con.execute("SELECT * FROM fact_lot").df()
    finally:
        con.close()

    rows = []
    for scen, g in lot.groupby("scenario"):
        # per-rep aggregates; the point estimate is the mean across reps, and the
        # rep-to-rep spread gives the std and t-based CI half-width.
        per_rep = g.groupby("rep").agg(
            n_lots=("lot_id", "count"),
            mean_ct=("cycle_time", "mean"),
            p95_ct=("cycle_time", lambda s: np.percentile(s, 95)),
            mean_xf=("x_factor", "mean"),
            wafers=("wafers", "sum"),
            otd=("tardy", lambda s: 1.0 - s.mean()),
            ct_cv=("cycle_time", lambda s: s.std(ddof=1) / s.mean() if s.mean() else 0.0),
        ).reset_index()

        per_rep_metrics = {
            "lots_out_per_week": per_rep["n_lots"].to_numpy() / span_weeks,
            "wafers_out_per_week": per_rep["wafers"].to_numpy() / span_weeks,
            "mean_cycle_time_h": per_rep["mean_ct"].to_numpy(),
            "p95_cycle_time_h": per_rep["p95_ct"].to_numpy(),
            "mean_x_factor": per_rep["mean_xf"].to_numpy(),
            "on_time_delivery": per_rep["otd"].to_numpy(),
            "cycle_time_cv": per_rep["ct_cv"].to_numpy(),
        }

        row = {"scenario": scen}
        for metric, vals in per_rep_metrics.items():
            row[metric] = float(np.mean(vals))
            row[f"{metric}_std"] = float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0
            row[f"{metric}_ci95"] = _ci_halfwidth(vals)

        # Pooled OTD ratio for BI parity (overrides the per-rep mean point estimate).
        row["on_time_delivery"] = float(1.0 - g["tardy"].sum() / len(g))
        rows.append(row)

    kpi = pd.DataFrame(rows).set_index("scenario")
    return kpi


def utilization(db_path: Path, horizon_hours: float, warmup_hours: float) -> pd.DataFrame:
    """Per-(scenario, tool_group) utilization, averaged across reps."""
    avail_per_tool = horizon_hours - warmup_hours
    con = _con(db_path)
    try:
        util = con.execute("SELECT * FROM fact_util").df()
        tg = con.execute("SELECT * FROM dim_tool_group").df()
    finally:
        con.close()
    util = util.merge(tg[["tool_group_id", "name"]], on="tool_group_id", how="left")
    util["available"] = util["n_tools"] * avail_per_tool
    util["utilization"] = util["busy_time"] / util["available"]
    out = (util.groupby(["scenario", "tool_group_id", "name"])
              .agg(utilization=("utilization", "mean"),
                   n_tools=("n_tools", "first"),
                   repair_time=("repair_time", "mean"))
              .reset_index())
    return out


def identify_bottleneck(db_path: Path, horizon_hours: float, warmup_hours: float,
                        scenario: str = "baseline") -> dict:
    """Return the highest-utilization tool group for a scenario."""
    u = utilization(db_path, horizon_hours, warmup_hours)
    u = u[u["scenario"] == scenario].sort_values("utilization", ascending=False)
    if u.empty:
        return {}
    top = u.iloc[0]
    return {"tool_group_id": int(top["tool_group_id"]), "name": top["name"],
            "utilization": float(top["utilization"]), "n_tools": int(top["n_tools"])}


def wait_by_tool_group(db_path: Path) -> pd.DataFrame:
    """Mean queue wait time per (scenario, tool group) - where lots lose time."""
    con = _con(db_path)
    try:
        step = con.execute(
            "SELECT scenario, tool_group_id, AVG(wait_time) AS mean_wait, "
            "SUM(wait_time) AS total_wait, COUNT(*) AS n FROM fact_step "
            "GROUP BY scenario, tool_group_id"
        ).df()
        tg = con.execute("SELECT tool_group_id, name FROM dim_tool_group").df()
    finally:
        con.close()
    return step.merge(tg, on="tool_group_id", how="left")


def littles_law_check(db_path: Path, horizon_hours: float, warmup_hours: float) -> pd.DataFrame:
    """Cross-check WIP ~= throughput * cycle time (Little's Law) per scenario.

    Note: ``observed_wip`` is dominated by the CONWIP cap (lots in system are bounded
    by ``conwip_level``) and by the warmup filter, so it comes out similar across
    scenarios. This is a model sanity check (does TH * CT line up with observed WIP?),
    not a per-scenario improvement signal.
    """
    span = horizon_hours - warmup_hours
    con = _con(db_path)
    try:
        lot = con.execute("SELECT * FROM fact_lot").df()
        wip = con.execute("SELECT * FROM wip_trace").df()
    finally:
        con.close()
    rows = []
    for scen, g in lot.groupby("scenario"):
        th = g.groupby("rep")["lot_id"].count().mean() / span    # lots per hour
        ct = g["cycle_time"].mean()
        w = wip[wip["scenario"] == scen]
        time_avg_wip = w.groupby("rep")["wip"].mean().mean() if not w.empty else np.nan
        rows.append({"scenario": scen, "throughput_per_h": th, "mean_ct_h": ct,
                     "littles_wip": th * ct, "observed_wip": time_avg_wip})
    return pd.DataFrame(rows).set_index("scenario")
