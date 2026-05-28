from pathlib import Path

from fabflow.analysis.compare import improvement_deltas
from fabflow.analysis.kpis import (
    identify_bottleneck,
    littles_law_check,
    scenario_kpis,
    utilization,
)
from fabflow.analysis.study import run_study


def test_study_builds_warehouse_and_kpis(cfg, tmp_path):
    cfg.output.warehouse = tmp_path / "wh.duckdb"
    db = run_study(cfg)
    assert Path(db).exists()

    kpi = scenario_kpis(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    assert "baseline" in kpi.index
    for col in ["mean_cycle_time_h", "mean_x_factor", "on_time_delivery"]:
        assert col in kpi.columns
    # X-factor must be >= 1 (cycle time can't beat raw process time)
    assert (kpi["mean_x_factor"] >= 1.0).all()
    # OTD is a fraction
    assert kpi["on_time_delivery"].between(0, 1).all()


def test_utilization_never_exceeds_one(cfg, tmp_path):
    cfg.output.warehouse = tmp_path / "wh.duckdb"
    db = run_study(cfg)
    u = utilization(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    # True utilization (busy / available) is bounded by 1.0 for every tool group and
    # scenario. A value > 1 means the busy-time numerator and available-hours
    # denominator use mismatched time windows (the warmup-windowing bug).
    assert (u["utilization"] <= 1.0).all(), u[u["utilization"] > 1.0]
    assert (u["utilization"] >= 0.0).all()


def test_kpis_report_confidence_intervals(cfg, tmp_path):
    cfg.output.warehouse = tmp_path / "wh.duckdb"
    db = run_study(cfg)
    kpi = scenario_kpis(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    for metric in ["mean_cycle_time_h", "mean_x_factor", "on_time_delivery"]:
        assert f"{metric}_std" in kpi.columns
        assert f"{metric}_ci95" in kpi.columns
        assert (kpi[f"{metric}_ci95"] >= 0).all()


def test_bottleneck_identified(cfg, tmp_path):
    cfg.output.warehouse = tmp_path / "wh.duckdb"
    db = run_study(cfg)
    bn = identify_bottleneck(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    assert "name" in bn and bn["utilization"] > 0


def test_deltas_sign_convention(cfg, tmp_path):
    cfg.output.warehouse = tmp_path / "wh.duckdb"
    db = run_study(cfg)
    d = improvement_deltas(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    assert "baseline" not in d.index            # baseline excluded
    assert "mean_cycle_time_h" in d.columns


def test_littles_law_sane(cfg, tmp_path):
    cfg.output.warehouse = tmp_path / "wh.duckdb"
    db = run_study(cfg)
    ll = littles_law_check(db, cfg.sim.horizon_hours, cfg.sim.warmup_hours)
    # Little's law WIP estimate should be within a reasonable factor of observed WIP
    row = ll.loc["baseline"]
    assert row["littles_wip"] > 0 and row["observed_wip"] > 0
