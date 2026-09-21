"""Week 2 — 평가 레일 점검 (#40).

    metadata.jsonl → schema 검증 → dummy score → val 정상으로 threshold 조정 → test 판정 → 평가 → MLflow

모델은 seed 고정 random score다. **지표 숫자는 의미가 없고 인용하지 않는다.**
확인하는 것은 이후 모든 모델이 같은 loader / 평가 코드 / 기록 형식을 지나가는지다.

실행 (metadata.jsonl이 먼저 있어야 한다):
    uv run experiments/build_metadata.py mvtec_ad
    uv run experiments/week02_pipeline_check.py
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
# `uv run experiments/x.py`에서 `src` import (pytest의 pythonpath=["."]와 같은 규약)
sys.path.insert(0, str(REPO_ROOT))

from src.evaluation.metrics import calibrate, decide, evaluate  # noqa: E402
from src.utils.metadata import find_errors, read_jsonl  # noqa: E402
from src.utils.paths import SHARED_ROOT  # noqa: E402
from src.utils.tracking import git_commit, git_is_dirty, start_experiment  # noqa: E402

CONFIG_PATH = REPO_ROOT / "configs" / "week02_pipeline_check.yaml"
REGISTRY_PATH = REPO_ROOT / "datasets" / "registry.yaml"
# 예측 레코드(sample_id ~ latency_ms) + 실패 분석용 ground truth 열
PRED_COLUMNS = (
    "sample_id", "decision", "anomaly_score", "predicted_label_id", "latency_ms",
    "image_path", "normal_or_defect", "defect_type",
)  # fmt: skip


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def score_all(rows: list[dict], rng: np.random.Generator) -> list[dict]:
    """모델 자리. 판정 전 score와 latency만 낸다."""
    preds = []
    for row in rows:
        start = time.perf_counter()
        score = float(rng.random())  # dummy model
        latency_ms = (time.perf_counter() - start) * 1000
        preds.append(
            {
                "sample_id": row["sample_id"],
                "anomaly_score": score,
                "predicted_label_id": None,
                "latency_ms": latency_ms,
            }
        )
    return preds


def flat_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    """MLflow용. 비율 지표는 value/k/n/ci95 로 펼친다. 정의되지 않은 값(None)은 뺀다."""
    out: dict[str, float] = {}
    for name, v in metrics.items():
        if isinstance(v, dict) and "k" in v:
            out |= {f"{name}_k": v["k"], f"{name}_n": v["n"]}
            if v["value"] is not None:
                out |= {name: v["value"], f"{name}_ci95_low": v["ci95"][0]}
                out[f"{name}_ci95_high"] = v["ci95"][1]
        elif isinstance(v, int | float):
            out[name] = v
    return out


def write_predictions(path: Path, rows: list[dict], preds: list[dict]) -> None:
    by_id = {r["sample_id"]: r for r in rows}
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PRED_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(by_id[p["sample_id"]] | p for p in preds)


def main() -> None:
    cfg = load_yaml(CONFIG_PATH)
    ds = cfg["dataset"]
    reg = load_yaml(REGISTRY_PATH)[ds["name"]]

    rows = [
        r for r in read_jsonl(SHARED_ROOT / reg["metadata"]) if r["product_id"] == ds["category"]
    ]
    if errors := find_errors(rows, image_root=SHARED_ROOT / reg["root"]):
        raise ValueError(f"metadata 검증 실패 {len(errors)}건: {errors[:5]}")
    dec = cfg["decision"]
    val = [r for r in rows if r["split"] == dec["calibration_split"]]
    test = [r for r in rows if r["split"] == ds["split"]]
    if not val or not test:
        raise ValueError(
            f"{ds['category']} val/test 샘플이 없다 — build_metadata.py로 metadata 재생성"
        )

    rng = np.random.default_rng(cfg["experiment"]["seed"])
    val_scores = [
        p["anomaly_score"]
        for r, p in zip(val, score_all(val, rng), strict=True)
        if r["normal_or_defect"] == "normal"
    ]
    t_ok, t_ng = calibrate(val_scores, dec["normal_ng_rate"], dec["normal_review_rate"])
    preds = [p | {"decision": decide(p["anomaly_score"], t_ok, t_ng)} for p in score_all(test, rng)]
    metrics = evaluate(test, preds)

    start_experiment(cfg["tracking"]["experiment_name"])
    with mlflow.start_run(run_name=f"dummy-{ds['category']}") as run:
        mlflow.set_tags({"purpose": "pipeline_check", "citable": "false"})
        mlflow.log_params(
            {
                "git_commit": git_commit(),
                "git_dirty": git_is_dirty(),
                "config_path": CONFIG_PATH.relative_to(REPO_ROOT).as_posix(),
                "dataset_name": ds["name"],
                "dataset_version": reg["version"],
                "dataset_sha256": reg["sha256"],
                "dataset_schema": reg["schema"],
                "dataset_category": ds["category"],
                "split": ds["split"],
                "model_name": cfg["model"]["name"],
                "threshold_ok": t_ok,
                "threshold_ng": t_ng,
                "threshold_source": f"{dec['calibration_split']} normal quantile (n={len(val_scores)})",
                "normal_ng_rate": dec["normal_ng_rate"],
                "normal_review_rate": dec["normal_review_rate"],
                "seed": cfg["experiment"]["seed"],
                "device": cfg["latency"]["device"],
                "num_train": sum(r["split"] == "train" for r in rows),
                "num_val": len(val),
                "num_test": len(test),
                "review_policy": metrics["review_policy"],
            }
        )
        mlflow.log_metrics(flat_metrics(metrics))
        mlflow.log_artifact(str(CONFIG_PATH), artifact_path="config")
        mlflow.log_artifact(str(REGISTRY_PATH), artifact_path="config")
        with tempfile.TemporaryDirectory() as tmp:
            write_predictions(Path(tmp) / "predictions.csv", test, preds)
            (Path(tmp) / "metrics.json").write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            mlflow.log_artifacts(tmp)

    der, cder = metrics["defect_escape_rate"], metrics["critical_defect_escape_rate"]
    print(f"run_id : {run.info.run_id}  ({cfg['tracking']['experiment_name']})")
    print(f"thresh : ok={t_ok:.3f} ng={t_ng:.3f}  (val 정상 {len(val_scores)}장 분위수)")
    print(f"test   : {len(test)} samples  confusion {metrics['confusion']}")
    print(f"DER    : {der['k']} / {der['n']} escaped = {der['value']:.2%}  95% CI {der['ci95']}")
    print(f"CDER   : {'N/A (Recipe severity 없음)' if cder['value'] is None else cder}")
    print(f"Review : {metrics['review_rate']['value']:.2%}   AUROC {metrics['auroc']:.3f}")
    print("※ dummy random score — 숫자는 의미 없음")


if __name__ == "__main__":
    main()
