from fabflow.analysis.study import run_study
from fabflow.data.warehouse import export_parquet


def test_parquet_export(cfg, tmp_path):
    cfg.output.warehouse = tmp_path / "wh.duckdb"
    db = run_study(cfg)
    out = tmp_path / "bi"
    written = export_parquet(db, out)
    assert any(p.name == "fact_lot.parquet" for p in written)
    for p in written:
        assert p.exists() and p.stat().st_size > 0
