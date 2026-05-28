"""Run the pre/post improvement study: baseline + scenarios, multiple reps.

The bottleneck for capacity-addition scenarios is identified from a quick
baseline probe, so 'add_tool_at_bottleneck' targets the real constraint rather
than a guess.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from fabflow.config import FabFlowConfig
from fabflow.data.synthetic_fab import build_fab
from fabflow.data.warehouse import load_warehouse, run_to_frames
from fabflow.model.fab import FabSim


def _probe_bottleneck(cfg: FabFlowConfig, spec) -> int:
    """One quick baseline rep to find the highest-utilization tool group."""
    sim = FabSim(spec, cfg.fab, cfg.sim, dispatching_rule="fifo", seed=cfg.fab.seed)
    out = sim.run()
    # busy_time is accumulated post-warmup only, so divide by post-warmup hours to match.
    avail = cfg.sim.horizon_hours - cfg.sim.warmup_hours
    util = {g: out["busy_time"][g] / (out["tool_counts"][g] * avail)
            for g in spec.tool_groups}
    bn = max(util, key=util.get)
    logger.info(f"Bottleneck probe: {spec.tool_groups[bn].name} "
                f"(util={util[bn]:.2f}, {out['tool_counts'][bn]} tools)")
    return bn


def run_study(cfg: FabFlowConfig) -> Path:
    """Execute all scenarios x reps, build the DuckDB warehouse. Returns db path."""
    spec = build_fab(cfg.fab, cfg.sim.wafers_per_lot)
    bottleneck = _probe_bottleneck(cfg, spec)

    frames_by_run = []
    for scen_name, scen in cfg.scenarios.items():
        extra = {bottleneck: scen.add_tool_at_bottleneck} if scen.add_tool_at_bottleneck else None
        for rep in range(cfg.sim.reps):
            seed = cfg.fab.seed + 1000 * rep
            sim = FabSim(spec, cfg.fab, cfg.sim, dispatching_rule=scen.dispatching,
                         extra_tools=extra, seed=seed)
            out = sim.run()
            frames = run_to_frames(out, spec, scenario=scen_name, rep=rep,
                                   warmup_hours=cfg.sim.warmup_hours)
            frames_by_run.append(frames)
        logger.info(f"Scenario '{scen_name}' ({scen.dispatching}, "
                    f"+{scen.add_tool_at_bottleneck} tool@bottleneck): {cfg.sim.reps} reps done")

    load_warehouse(frames_by_run, cfg.output.warehouse)
    logger.info(f"Warehouse written: {cfg.output.warehouse}")
    return Path(cfg.output.warehouse)
