"""Build tidy fact/dim tables from a simulation run and load a DuckDB star schema.

Star schema
-----------
fact_step    : one row per lot-step (the grain) - queue/start/end/proc/wait times
fact_lot     : one row per completed lot - cycle time, X-factor, tardiness
dim_tool_group, dim_product, dim_scenario : descriptive dimensions
This is the single source of truth that both the report and the BI export read.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from fabflow.model.entities import FabSpec


def run_to_frames(run: dict, spec: FabSpec, scenario: str, rep: int,
                  warmup_hours: float) -> dict[str, pd.DataFrame]:
    """Convert a FabSim.run() output into tidy DataFrames, excluding warmup lots."""
    # --- fact_step: one row per lot-step ---
    step_rows = []
    for lot in run["lots"].values():
        if lot.release_time < warmup_hours:
            continue
        for h in lot.history:
            if h["start_time"] is None or h["end_time"] is None:
                continue
            wait = h["start_time"] - h["enqueue_time"]
            step_rows.append({
                "scenario": scenario, "rep": rep, "lot_id": lot.id,
                "product_id": lot.product_id, "step": h["step"],
                "tool_group_id": h["tool_group"],
                "enqueue_time": h["enqueue_time"], "start_time": h["start_time"],
                "end_time": h["end_time"], "wait_time": round(wait, 4),
                "proc_time": h["proc_time"], "setup_time": h["setup_time"],
                "repair_time": h.get("repair_time", 0.0),
            })
    fact_step = pd.DataFrame(step_rows)

    # --- fact_lot: one row per completed lot (post-warmup) ---
    lot_rows = []
    for lot in run["lots"].values():
        if lot.completion_time is None or lot.release_time < warmup_hours:
            continue
        product = spec.products[lot.product_id]
        ct = lot.completion_time - lot.release_time
        rpt = product.raw_process_time
        lot_rows.append({
            "scenario": scenario, "rep": rep, "lot_id": lot.id,
            "product_id": lot.product_id, "release_time": lot.release_time,
            "completion_time": lot.completion_time, "cycle_time": round(ct, 4),
            "raw_process_time": rpt, "x_factor": round(ct / rpt, 4) if rpt else None,
            "wafers": lot.wafers, "due_date": lot.due_date,
            "tardy": int(lot.completion_time > lot.due_date),
            "lateness": round(lot.completion_time - lot.due_date, 4),
        })
    fact_lot = pd.DataFrame(lot_rows)

    # --- dimensions ---
    dim_tool_group = pd.DataFrame([
        {"tool_group_id": g, "name": tg.name}
        for g, tg in spec.tool_groups.items()
    ])
    dim_product = pd.DataFrame([
        {"product_id": p.id, "name": p.name, "route_length": len(p.route),
         "raw_process_time": p.raw_process_time, "planned_cycle_time": p.planned_cycle_time}
        for p in spec.products.values()
    ])

    # --- tool-group busy/repair time for utilization ---
    util_rows = []
    for g in spec.tool_groups:
        util_rows.append({
            "scenario": scenario, "rep": rep, "tool_group_id": g,
            "busy_time": round(run["busy_time"][g], 4),
            "repair_time": round(run["repair_time"][g], 4),
            "n_tools": run["tool_counts"][g],
        })
    fact_util = pd.DataFrame(util_rows)

    # --- wip trace ---
    wip = pd.DataFrame(run["wip_trace"], columns=["time", "wip"])
    wip = wip[wip["time"] >= warmup_hours].copy()
    wip["scenario"] = scenario
    wip["rep"] = rep

    return {"fact_step": fact_step, "fact_lot": fact_lot, "fact_util": fact_util,
            "dim_tool_group": dim_tool_group, "dim_product": dim_product, "wip_trace": wip}


def load_warehouse(frames_by_run: list[dict[str, pd.DataFrame]], db_path: Path) -> None:
    """Concatenate per-run frames and write them as DuckDB tables (star schema)."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    combined: dict[str, pd.DataFrame] = {}
    for frames in frames_by_run:
        for name, df in frames.items():
            combined.setdefault(name, []).append(df)
    merged = {name: pd.concat(parts, ignore_index=True) for name, parts in combined.items()}
    # dims are repeated across runs -> dedupe
    for d in ("dim_tool_group", "dim_product"):
        if d in merged:
            merged[d] = merged[d].drop_duplicates().reset_index(drop=True)

    con = duckdb.connect(str(db_path))
    try:
        for name, df in merged.items():
            con.register("tmp_df", df)
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM tmp_df")
            con.unregister("tmp_df")
    finally:
        con.close()


def export_parquet(db_path: Path, out_dir: Path) -> list[Path]:
    """Export every warehouse table to Parquet for Tableau / Power BI."""
    db_path, out_dir = Path(db_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    con = duckdb.connect(str(db_path))
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for t in tables:
            p = out_dir / f"{t}.parquet"
            con.execute(f"COPY {t} TO '{p}' (FORMAT PARQUET)")
            written.append(p)
    finally:
        con.close()
    return written
