"""Hugging Face Spaces entrypoint - reuses the package Streamlit dashboard."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from fabflow.dashboard import app  # noqa: F401,E402
