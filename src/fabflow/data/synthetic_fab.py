"""Generate a synthetic but realistic wafer-fab specification.

Produces tool groups (work centers), parallel tool counts, and product routes
with a re-entrant character (steps revisit hot work centers like Litho/Etch).
Deterministic given a seed, so studies are reproducible.
"""
from __future__ import annotations

import numpy as np

from fabflow.config import FabCfg
from fabflow.model.entities import FabSpec, Product, Step, ToolGroup

# Canonical front-end work centers; the generator uses the first n_tool_groups.
WORK_CENTERS = [
    "Litho", "Etch", "CMP", "Implant", "Deposition",
    "Diffusion", "Metrology", "Clean", "Test", "Anneal",
]
# Hot work centers are revisited more often (re-entrancy) -> natural bottlenecks.
HOT = {"Litho", "Etch", "CMP"}


def build_fab(cfg: FabCfg, wafers_per_lot: int) -> FabSpec:
    rng = np.random.default_rng(cfg.seed)
    n_groups = min(cfg.n_tool_groups, len(WORK_CENTERS))
    names = WORK_CENTERS[:n_groups]

    tool_groups: dict[int, ToolGroup] = {}
    for gid, name in enumerate(names):
        lo, hi = cfg.tools_per_group_range
        # Hot centers get more parallel tools but remain capacity-tight on purpose.
        n = int(rng.integers(lo, hi + 1))
        if name in HOT:
            n = max(n, hi)
        tool_groups[gid] = ToolGroup(id=gid, name=name, n_tools=n)

    # Sampling weights bias routes toward hot work centers (re-entrant flow).
    weights = np.array([3.0 if names[g] in HOT else 1.0 for g in range(n_groups)])
    weights = weights / weights.sum()

    products: dict[int, Product] = {}
    for pid in range(cfg.n_products):
        rlo, rhi = cfg.route_length_range
        length = int(rng.integers(rlo, rhi + 1))
        steps = []
        for seq in range(length):
            gid = int(rng.choice(n_groups, p=weights))
            plo, phi = cfg.proc_time_range
            ptime = float(rng.uniform(plo, phi))
            steps.append(Step(seq=seq, tool_group_id=gid, proc_time=round(ptime, 3)))
        route = tuple(steps)
        rpt = sum(s.proc_time for s in route)
        # Planned cycle time = target flow factor (X-factor) * raw process time.
        planned = rpt * float(rng.uniform(2.5, 3.5))
        products[pid] = Product(id=pid, name=f"P{pid+1}", route=route,
                                planned_cycle_time=round(planned, 3))

    return FabSpec(name=cfg.name, tool_groups=tool_groups, products=products,
                   wafers_per_lot=wafers_per_lot)
