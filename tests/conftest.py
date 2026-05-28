"""Shared fixtures: a small, fast fab + sim config."""
import pytest

from fabflow.config import load_config


@pytest.fixture(scope="session")
def cfg():
    c = load_config("configs/config.yaml")
    # shrink for fast tests
    c.sim.horizon_hours = 600.0
    c.sim.warmup_hours = 72.0
    c.sim.conwip_level = 16
    c.sim.reps = 2
    return c


@pytest.fixture(scope="session")
def spec(cfg):
    from fabflow.data.synthetic_fab import build_fab
    return build_fab(cfg.fab, cfg.sim.wafers_per_lot)
