from pathlib import Path

import pytest
import yaml

from fabflow.config import FabFlowConfig, load_config


def test_load_config():
    c = load_config("configs/config.yaml")
    assert isinstance(c, FabFlowConfig)
    assert "baseline" in c.scenarios
    assert c.sim.reps >= 1


def test_rejects_extra(tmp_path):
    raw = yaml.safe_load(Path("configs/config.yaml").read_text())
    raw["bogus"] = 1
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw))
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        load_config(p)
