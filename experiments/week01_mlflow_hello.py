"""Week 1 — MLflow 최소 동작 확인.

목표는 모델을 돌리는 것이 아니라, 앞으로 24주 동안 모든 실험이 통과할
'기록 경로'가 실제로 동작하는지 확인하는 것이다.

    config 로드 → run 시작 → param 기록 → metric 기록 → artifact 저장 → UI 확인

실행:
    uv run experiments/week01_mlflow_hello.py
    uv run mlflow ui --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlartifacts

주의: MLflow 3.x부터 파일 기반 tracking store(./mlruns)는 maintenance mode다.
로컬 SQLite(mlflow.db)를 쓰면 서버/Docker 없이도 최신 기능을 그대로 쓸 수 있다.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime

import mlflow
import yaml
from _bootstrap import REPO_ROOT  # sys.path + UTF-8 stdout. 첫 import여야 한다

CONFIG_PATH = REPO_ROOT / "configs" / "base.yaml"
TRACKING_URI = f"sqlite:///{REPO_ROOT / 'mlflow.db'}"
ARTIFACT_ROOT = REPO_ROOT / "mlartifacts"
EXPERIMENT_NAME = "week01_test"


def git_commit() -> str:
    """현재 commit hash. 모든 실험 결과는 코드 상태와 함께 기록되어야 한다."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def git_is_dirty() -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return True


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    mlflow.set_tracking_uri(TRACKING_URI)
    if mlflow.get_experiment_by_name(EXPERIMENT_NAME) is None:
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        mlflow.create_experiment(EXPERIMENT_NAME, artifact_location=ARTIFACT_ROOT.as_uri())
    mlflow.set_experiment(EXPERIMENT_NAME)

    with mlflow.start_run(run_name="hello-world") as run:
        # --- params: 무엇을, 어떤 코드로, 어떤 데이터로 돌렸는가 ---
        mlflow.log_params(
            {
                "model": config["model"]["name"],  # none
                "dataset": config["dataset"]["name"],  # pilot
                "dataset_version": config["dataset"]["version"],
                "split": config["dataset"]["split"],
                "seed": config["experiment"]["seed"],
                "git_commit": git_commit(),
                "git_dirty": git_is_dirty(),
                "primary_metric": config["evaluation"]["primary_metric"],
            }
        )

        # --- metrics: 오늘은 배관 확인용 더미 값 ---
        mlflow.log_metric("dummy_f1", 0.5)

        # --- artifacts: config 사본 + 실행 요약 ---
        mlflow.log_artifact(str(CONFIG_PATH), artifact_path="config")

        summary = {
            "purpose": "Week 1 MLflow plumbing check",
            "logged_at": datetime.now(UTC).isoformat(),
            "note": "실제 지표 아님. 기록 경로 동작 확인용 더미 run.",
            "next": "Week 4에서 evaluation pipeline을 붙인다.",
        }
        summary_path = ARTIFACT_ROOT / "_week01_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        mlflow.log_artifact(str(summary_path), artifact_path="summary")
        summary_path.unlink()

        print("MLflow run 기록 완료")
        print(f"  experiment : {EXPERIMENT_NAME}")
        print(f"  run_id     : {run.info.run_id}")
        print(f"  tracking   : {TRACKING_URI}")
        print()
        print("UI 확인:")
        print(
            "  uv run mlflow ui --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlartifacts"
        )
        print("  http://127.0.0.1:5000")


if __name__ == "__main__":
    main()
