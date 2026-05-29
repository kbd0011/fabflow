"""Assemble a Hugging Face Space build tree for FabFlow and optionally deploy it.

FabFlow ships no data: the dashboard builds the DuckDB warehouse on first load by
running the study (a few seconds), so the Space only needs the package + config
plus the three HF files. Upload is via ``huggingface_hub`` for idempotent re-deploys.

Usage::

    python scripts/deploy_space.py --build
    python scripts/deploy_space.py --deploy --repo-id kbd0011/fabflow
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "space_build"
SPACE_SRC = REPO_ROOT / "huggingface" / "spaces"

INCLUDE = [
    "src/fabflow",
    "configs/config.yaml",
]


def build() -> Path:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)

    for name in ("app.py", "requirements.txt", "README.md"):
        shutil.copy2(SPACE_SRC / name, BUILD_DIR / name)

    for rel in INCLUDE:
        src = REPO_ROOT / rel
        dst = BUILD_DIR / rel
        if not src.exists():
            raise FileNotFoundError(f"manifest entry missing: {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)

    print(f"built {BUILD_DIR} ({sum(1 for _ in BUILD_DIR.rglob('*') if _.is_file())} files)")
    return BUILD_DIR


def deploy(repo_id: str) -> str:
    from huggingface_hub import HfApi, create_repo

    build()
    create_repo(repo_id, repo_type="space", space_sdk="streamlit", exist_ok=True)
    HfApi().upload_folder(
        folder_path=str(BUILD_DIR),
        repo_id=repo_id,
        repo_type="space",
        commit_message="Deploy FabFlow demo",
    )
    url = f"https://huggingface.co/spaces/{repo_id}"
    print(f"deployed -> {url}")
    return url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--repo-id", default="kbd0011/fabflow")
    args = ap.parse_args()
    if args.deploy:
        deploy(args.repo_id)
    else:
        build()


if __name__ == "__main__":
    main()
