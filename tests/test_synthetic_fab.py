from fabflow.data.synthetic_fab import build_fab


def test_build_fab_structure(cfg, spec):
    assert len(spec.tool_groups) == cfg.fab.n_tool_groups
    assert len(spec.products) == cfg.fab.n_products
    for p in spec.products.values():
        assert len(p.route) >= cfg.fab.route_length_range[0]
        assert p.raw_process_time > 0
        assert p.planned_cycle_time > p.raw_process_time   # flow factor > 1


def test_build_fab_deterministic(cfg):
    a = build_fab(cfg.fab, cfg.sim.wafers_per_lot)
    b = build_fab(cfg.fab, cfg.sim.wafers_per_lot)
    assert [t.n_tools for t in a.tool_groups.values()] == [t.n_tools for t in b.tool_groups.values()]
    assert a.products[0].raw_process_time == b.products[0].raw_process_time
