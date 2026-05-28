.PHONY: install env test lint format clean simulate analyze report dashboard bi-export run study demo

PYTHON := python
UV := uv

install:
	@command -v uv >/dev/null 2>&1 || { echo "Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }
	$(UV) venv --python 3.12
	$(UV) pip install -e ".[dev]"
	@echo ""
	@echo "  Done. Activate with:  source .venv/bin/activate"
	@echo ""

env:
	@$(PYTHON) -c "import fabflow, simpy, duckdb; print('fabflow', fabflow.__version__, '| simpy', simpy.__version__, '| duckdb', duckdb.__version__)"

test:
	pytest -m "not slow" -v

test-all:
	pytest -v

lint:
	ruff check src tests

format:
	ruff format src tests

clean:
	rm -rf .pytest_cache .ruff_cache dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# === Pipeline ===

# Run a single scenario simulation -> event log parquet
simulate:
	$(PYTHON) -m fabflow.cli simulate --scenario baseline

# Build the DuckDB warehouse (star schema) from the latest run
analyze:
	$(PYTHON) -m fabflow.cli analyze

# Render the HTML improvement report
report:
	$(PYTHON) -m fabflow.cli report

# Export the star schema to Parquet for Tableau / Power BI
bi-export:
	$(PYTHON) -m fabflow.cli bi-export

dashboard:
	streamlit run src/fabflow/dashboard/app.py

# === Full pre/post improvement study (baseline + scenarios, multi-seed) ===
study:
	$(PYTHON) -m fabflow.cli study

# End-to-end: study -> warehouse -> report -> bi-export
run: study analyze report bi-export
	@echo ""
	@echo "  PIPELINE COMPLETE."
	@echo "  Report:    artifacts/reports/  (open the newest .html)"
	@echo "  Dashboard: make dashboard"
	@echo "  BI data:   artifacts/bi_export/  (point Tableau Public here)"

demo: run
