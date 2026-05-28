from typer.testing import CliRunner

from fabflow.cli import app


def test_help():
    r = CliRunner().invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "study" in r.stdout
    assert "report" in r.stdout


def test_simulate_baseline():
    r = CliRunner().invoke(app, ["simulate", "--scenario", "baseline"])
    assert r.exit_code == 0
    assert "mean_CT" in r.stdout
