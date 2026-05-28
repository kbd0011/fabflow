"""Typer CLI for FabFlow-Cortex."""
from __future__ import annotations

from pathlib import Path

import typer

from fabflow.config import load_config

app = typer.Typer(help="FabFlow-Cortex: SimPy wafer-fab digital twin + DuckDB analytics + improvement study.")
CONFIG_PATH = Path("configs/config.yaml")


@app.command()
def simulate(scenario: str = "baseline", seed: int | None = None):
    """Run a single scenario simulation and print summary KPIs (no warehouse)."""
    import numpy as np

    from fabflow.data.synthetic_fab import build_fab
    from fabflow.model.fab import FabSim

    cfg = load_config(CONFIG_PATH)
    if scenario not in cfg.scenarios:
        typer.echo(f"Unknown scenario '{scenario}'. Options: {list(cfg.scenarios)}")
        raise typer.Exit(1)
    scen = cfg.scenarios[scenario]
    spec = build_fab(cfg.fab, cfg.sim.wafers_per_lot)

    # find bottleneck for capacity scenarios
    extra = None
    if scen.add_tool_at_bottleneck:
        probe = FabSim(spec, cfg.fab, cfg.sim, "fifo", seed=cfg.fab.seed).run()
        avail = cfg.sim.horizon_hours - cfg.sim.warmup_hours
        util = {g: probe["busy_time"][g] / (probe["tool_counts"][g] * avail)
                for g in spec.tool_groups}
        bn = max(util, key=util.get)
        extra = {bn: scen.add_tool_at_bottleneck}

    sim = FabSim(spec, cfg.fab, cfg.sim, scen.dispatching, extra_tools=extra,
                 seed=seed or cfg.fab.seed)
    out = sim.run()
    done = [lot for lot in out["lots"].values()
            if lot.completion_time is not None and lot.release_time >= cfg.sim.warmup_hours]
    cts = np.array([lot.completion_time - lot.release_time for lot in done])
    typer.echo(f"scenario={scenario} rule={scen.dispatching} lots_out={len(done)} "
               f"mean_CT={cts.mean():.1f}h X-factor~{cts.mean()/spec.products[0].raw_process_time:.2f}")


@app.command()
def study():
    """Run the full pre/post study (all scenarios x reps) and build the DuckDB warehouse."""
    from fabflow.analysis.study import run_study
    cfg = load_config(CONFIG_PATH)
    db = run_study(cfg)
    typer.echo(f"Warehouse built: {db}")


@app.command()
def analyze():
    """Print KPI summary + improvement deltas from the warehouse."""
    import pandas as pd
    from tabulate import tabulate

    from fabflow.analysis.compare import improvement_deltas
    from fabflow.analysis.kpis import identify_bottleneck, scenario_kpis

    cfg = load_config(CONFIG_PATH)
    db = cfg.output.warehouse
    if not Path(db).exists():
        typer.echo("No warehouse. Run `fabflow study` first.")
        raise typer.Exit(1)
    kpi = scenario_kpis(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    bn = identify_bottleneck(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    deltas = improvement_deltas(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    typer.echo(f"\nBottleneck (baseline): {bn.get('name')} @ {bn.get('utilization', 0)*100:.1f}% "
               f"util, {bn.get('n_tools')} tools\n")

    # Headline KPIs with 95% t-CI half-widths (mean +/- ci95 across reps).
    headline = ["mean_cycle_time_h", "mean_x_factor", "wafers_out_per_week", "on_time_delivery"]
    ci_tbl = pd.DataFrame({
        m: kpi.apply(lambda r, m=m: f"{r[m]:.3f} +/- {r[m + '_ci95']:.3f}", axis=1)
        for m in headline
    })
    typer.echo("Headline KPIs (mean +/- 95% CI across reps; OTD is a pooled ratio):")
    typer.echo(tabulate(ci_tbl, headers="keys", tablefmt="github"))

    point_cols = [c for c in kpi.columns if not c.endswith(("_std", "_ci95"))]
    typer.echo("\nKPI summary (point estimates, mean across reps):")
    typer.echo(tabulate(kpi[point_cols].round(3), headers="keys", tablefmt="github"))
    typer.echo("\nImprovement vs baseline (%, + = better):")
    typer.echo(tabulate(deltas.round(2), headers="keys", tablefmt="github"))


@app.command()
def report():
    """Render the HTML improvement report."""
    from fabflow.reports.improvement_report import render
    cfg = load_config(CONFIG_PATH)
    db = cfg.output.warehouse
    if not Path(db).exists():
        typer.echo("No warehouse. Run `fabflow study` first.")
        raise typer.Exit(1)
    tdir = Path("src/fabflow/reports/templates")
    path = render(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours, tdir,
                  cfg.output.report_dir, cfg.fab.name)
    typer.echo(f"Report: {path}")


@app.command("bi-export")
def bi_export():
    """Export the warehouse star schema to Parquet for Tableau / Power BI."""
    from fabflow.data.warehouse import export_parquet
    cfg = load_config(CONFIG_PATH)
    db = cfg.output.warehouse
    if not Path(db).exists():
        typer.echo("No warehouse. Run `fabflow study` first.")
        raise typer.Exit(1)
    written = export_parquet(db, cfg.output.bi_export_dir)
    for p in written:
        typer.echo(f"  wrote {p}")
    typer.echo(f"\n{len(written)} Parquet tables in {cfg.output.bi_export_dir} "
               f"(point Tableau Public here; see docs/tableau_guide.md).")


@app.command()
def run():
    """Full pipeline: study -> analyze -> report -> bi-export."""
    study()
    analyze()
    report()
    bi_export()


if __name__ == "__main__":
    app()
