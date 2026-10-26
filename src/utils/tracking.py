"""실험 기록 공통 (docs/adr/0007). 로컬 SQLite MLflow + git commit + config 사본."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from typing import Any

import mlflow

from src.utils.paths import REPO_ROOT, SHARED_ROOT

TRACKING_URI = f"sqlite:///{SHARED_ROOT / 'mlflow.db'}"
ARTIFACT_ROOT = SHARED_ROOT / "mlartifacts"
# 예측 레코드(sample_id ~ latency_ms) + 실패 분석용 ground truth 열
PRED_COLUMNS = (
    "sample_id", "decision", "anomaly_score", "predicted_label_id", "barcode_result", "latency_ms",
    "image_path", "normal_or_defect", "defect_type",
)  # fmt: skip


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


def flat_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    """MLflow용. 비율 지표는 value/k/n/ci95 로 펼친다. 정의되지 않은 값(None)은 뺀다.

    `label_level` / `product_level`은 이름 뒤에 `_label` / `_product`를 붙인다 (protocol §9).
    """
    out: dict[str, float] = {}
    for name, v in metrics.items():
        if name.endswith("_level"):
            out |= {f"{k}_{name.removesuffix('_level')}": x for k, x in flat_metrics(v).items()}
        elif isinstance(v, dict) and "k" in v:
            out |= {f"{name}_k": v["k"], f"{name}_n": v["n"]}
            if v["value"] is not None:
                out |= {name: v["value"], f"{name}_ci95_low": v["ci95"][0]}
                out[f"{name}_ci95_high"] = v["ci95"][1]
        elif isinstance(v, int | float):
            out[name] = v
    return out


def flat_scenario_metrics(by_scenario: dict[str, dict[str, Any]]) -> dict[str, float]:
    """`evaluate_scenarios()` 결과 → 시나리오 접두사를 붙인 이름 (`e1_defect_escape_rate` …, §9)."""
    return {
        f"{s.lower()}_{k}": v for s, m in by_scenario.items() for k, v in flat_metrics(m).items()
    }


def write_predictions(path: Path, rows: list[dict], preds: list[dict]) -> None:
    by_id = {r["sample_id"]: r for r in rows}
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PRED_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(by_id[p["sample_id"]] | p for p in preds)
