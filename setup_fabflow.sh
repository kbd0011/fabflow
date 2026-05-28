#!/usr/bin/env bash
# FabFlow-Cortex bootstrap for macOS / Linux.
set -euo pipefail

echo "==> FabFlow-Cortex setup"

if ! command -v uv >/dev/null 2>&1; then
  echo "==> Installing uv (fast Python package manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

echo "==> Creating virtual environment (.venv) with Python 3.12..."
uv venv --python 3.12

echo "==> Installing fabflow + dev dependencies..."
uv pip install -e ".[dev]"

echo "==> Verifying..."
.venv/bin/python -c "import fabflow, simpy, duckdb; print('fabflow', fabflow.__version__, '| simpy', simpy.__version__, '| duckdb', duckdb.__version__)"

echo "==> Running tests..."
.venv/bin/pytest -q -m "not slow"

cat <<'DONE'

==> Setup complete.

  Activate:   source .venv/bin/activate
  Pipeline:   make run
  Dashboard:  make dashboard
  BI data:    artifacts/bi_export/  (point Tableau Public here; see docs/tableau_guide.md)

DONE
