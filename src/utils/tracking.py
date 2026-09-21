"""실험 기록 공통 (docs/adr/0007). 로컬 SQLite MLflow + git commit + config 사본."""

from __future__ import annotations

import subprocess
from pathlib import Path

import mlflow

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKING_URI = f"sqlite:///{REPO_ROOT / 'mlflow.db'}"
ARTIFACT_ROOT = REPO_ROOT / "mlartifacts"


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip()


def git_commit() -> str:
    return _git("rev-parse", "HEAD") or "unknown"


def git_is_dirty() -> bool:
    status = _git("status", "--porcelain")
    return status is None or bool(status)  # 확인 불가면 dirty로 본다


def start_experiment(name: str) -> None:
    mlflow.set_tracking_uri(TRACKING_URI)
    if mlflow.get_experiment_by_name(name) is None:
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        mlflow.create_experiment(name, artifact_location=ARTIFACT_ROOT.as_uri())
    mlflow.set_experiment(name)
