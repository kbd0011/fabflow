import numpy as np

from fabflow.model.fab import FabSim


def test_sim_runs_and_completes_lots(cfg, spec):
    sim = FabSim(spec, cfg.fab, cfg.sim, "fifo", seed=1)
    out = sim.run()
    assert out["events"]
    done = [lot for lot in out["lots"].values() if lot.completion_time is not None]
    assert len(done) > 0
    # cycle times are positive; processing time is stochastic so an individual
    # lucky lot can dip just under nominal RPT, but the mean X-factor must be >= 1.
    xfactors = []
    for lot in done:
        ct = lot.completion_time - lot.release_time
        rpt = spec.products[lot.product_id].raw_process_time
        assert ct > 0
        xfactors.append(ct / rpt)
    assert np.mean(xfactors) >= 1.0


def test_conwip_caps_wip(cfg, spec):
    sim = FabSim(spec, cfg.fab, cfg.sim, "fifo", seed=2)
    out = sim.run()
    max_wip = max(w for _, w in out["wip_trace"])
    assert max_wip <= cfg.sim.conwip_level


def test_extra_tool_increases_count(cfg, spec):
    base = FabSim(spec, cfg.fab, cfg.sim, "fifo", seed=3).run()
    plus = FabSim(spec, cfg.fab, cfg.sim, "fifo", extra_tools={0: 1}, seed=3).run()
    assert plus["tool_counts"][0] == base["tool_counts"][0] + 1


def test_seed_reproducibility(cfg, spec):
    a = FabSim(spec, cfg.fab, cfg.sim, "fifo", seed=7).run()
    b = FabSim(spec, cfg.fab, cfg.sim, "fifo", seed=7).run()
    cta = [lot.completion_time for lot in a["lots"].values() if lot.completion_time]
    ctb = [lot.completion_time for lot in b["lots"].values() if lot.completion_time]
    assert cta == ctb
