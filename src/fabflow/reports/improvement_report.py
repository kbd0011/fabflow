"""Render the HTML pre/post improvement report with embedded charts."""
from __future__ import annotations

import base64
import io
from datetime import datetime
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fabflow.analysis.kpis import (
    identify_bottleneck,
    scenario_kpis,
    utilization,
)


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=92, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _ct_distribution_png(db_path: Path) -> str:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        lot = con.execute("SELECT scenario, cycle_time FROM fact_lot").df()
    finally:
        con.close()
    fig, ax = plt.subplots(figsize=(8, 4))
    for scen, g in lot.groupby("scenario"):
        ax.hist(g["cycle_time"], bins=40, histtype="step", linewidth=1.8, label=scen, density=True)
    ax.set_xlabel("Cycle time (h)")
    ax.set_ylabel("density")
    ax.set_title("Cycle-time distribution by scenario")
    ax.legend(fontsize=8)
    return _png(fig)


def _util_png(db_path: Path, horizon, warmup) -> str:
    u = utilization(db_path, horizon, warmup)
    scenarios = list(u["scenario"].unique())
    groups = u.sort_values("tool_group_id")["name"].unique()
    fig, ax = plt.subplots(figsize=(9, 4))
    width = 0.8 / max(len(scenarios), 1)
    x = np.arange(len(groups))
    for i, scen in enumerate(scenarios):
        sub = u[u["scenario"] == scen].set_index("name").reindex(groups)
        ax.bar(x + i * width, sub["utilization"].values, width, label=scen)
    ax.set_xticks(x + width * (len(scenarios) - 1) / 2)
    ax.set_xticklabels(groups, rotation=30, ha="right", fontsize=8)
    ax.axhline(1.0, color="r", ls="--", lw=0.8)
    ax.set_ylabel("utilization")
    ax.set_title("Tool-group utilization by scenario")
    ax.legend(fontsize=8)
    return _png(fig)


def _kpi_bars_png(kpi: pd.DataFrame) -> str:
    metrics = ["mean_cycle_time_h", "mean_x_factor", "wafers_out_per_week", "on_time_delivery"]
    titles = ["Mean cycle time (h)", "Mean X-factor", "Wafers out / week", "On-time delivery"]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4))
    for ax, m, t in zip(axes, metrics, titles, strict=False):
        ax.bar(kpi.index, kpi[m], color="#3182ce")
        ax.set_title(t, fontsize=9)
        ax.tick_params(axis="x", rotation=40, labelsize=7)
    return _png(fig)


def render(db_path: Path, horizon_hours: float, warmup_hours: float,
           template_dir: Path, out_dir: Path, fab_name: str,
           baseline: str = "baseline") -> Path:
    from fabflow.analysis.compare import improvement_deltas

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    kpi = scenario_kpis(db_path, horizon_hours, warmup_hours)
    deltas = improvement_deltas(db_path, horizon_hours, warmup_hours, baseline)
    bottleneck = identify_bottleneck(db_path, horizon_hours, warmup_hours, baseline)

    # order scenarios with baseline first
    order = [baseline] + [s for s in kpi.index if s != baseline]
    kpi = kpi.reindex(order)

    # Split point-estimate columns from the derived _std/_ci95 columns. The main KPI
    # table shows point estimates; a separate headline block shows mean +/- 95% CI.
    point_cols = [c for c in kpi.columns if not c.endswith(("_std", "_ci95"))]
    kpi_point = kpi[point_cols]
    headline_metrics = ["mean_cycle_time_h", "mean_x_factor",
                        "wafers_out_per_week", "on_time_delivery"]
    headline_rows = [
        (s, [f"{kpi.loc[s, m]:.3f} &plusmn; {kpi.loc[s, m + '_ci95']:.3f}"
             for m in headline_metrics])
        for s in kpi.index
    ]

    env = Environment(loader=FileSystemLoader(template_dir),
                      autoescape=select_autoescape(["html", "xml"]))
    tmpl = env.get_template("improvement_report.html.j2")

    # find the best scenario by cycle-time improvement
    best_scen = None
    if not deltas.empty:
        best_scen = deltas["mean_cycle_time_h"].idxmax()

    html = tmpl.render(
        fab_name=fab_name,
        generated=datetime.now().isoformat(timespec="seconds"),
        kpi_cols=list(kpi_point.columns),
        kpi_rows=[(s, [round(kpi_point.loc[s, c], 3) for c in kpi_point.columns])
                  for s in kpi_point.index],
        headline_cols=headline_metrics,
        headline_rows=headline_rows,
        delta_cols=list(deltas.columns),
        delta_rows=[(s, [deltas.loc[s, c] for c in deltas.columns]) for s in deltas.index],
        bottleneck=bottleneck,
        best_scenario=best_scen,
        best_delta=(deltas.loc[best_scen].to_dict() if best_scen else {}),
        ct_dist_png=_ct_distribution_png(db_path),
        util_png=_util_png(db_path, horizon_hours, warmup_hours),
        kpi_bars_png=_kpi_bars_png(kpi),
        baseline=baseline,
    )
    path = out_dir / f"improvement_report_{datetime.now():%Y%m%d_%H%M%S}.html"
    path.write_text(html)
    logger.info(f"Wrote improvement report to {path}")
    return path
