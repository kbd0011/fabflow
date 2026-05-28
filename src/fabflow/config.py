"""Pydantic configuration for FabFlow-Cortex."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class FabCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    seed: int = 42
    n_tool_groups: int = Field(default=8, ge=2)
    n_products: int = Field(default=3, ge=1)
    route_length_range: tuple[int, int] = (10, 18)
    tools_per_group_range: tuple[int, int] = (1, 4)
    proc_time_range: tuple[float, float] = (1.0, 4.0)
    proc_time_cv: float = Field(default=0.25, ge=0)
    setup_time_frac: float = Field(default=0.10, ge=0)
    mtbf_hours: float = 200.0
    mttr_hours: float = 8.0
    availability_target: float = 0.92


class SimCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warmup_hours: float = 168.0
    horizon_hours: float = 1512.0
    release_policy: str = "conwip"
    conwip_level: int = 40
    uniform_interarrival_hours: float = 6.0
    wafers_per_lot: int = 25
    reps: int = 5


class DispatchingCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule: str = "fifo"


class ScenarioCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dispatching: str = "fifo"
    add_tool_at_bottleneck: int = 0


class OutputCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_dir: Path
    warehouse: Path
    report_dir: Path
    bi_export_dir: Path


class FabFlowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fab: FabCfg
    sim: SimCfg
    dispatching: DispatchingCfg
    scenarios: dict[str, ScenarioCfg]
    output: OutputCfg


def load_config(path: str | Path = "configs/config.yaml") -> FabFlowConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open() as fh:
        raw = yaml.safe_load(fh)
    return FabFlowConfig.model_validate(raw)
