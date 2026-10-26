"""Week 2 — 평가 레일 점검 (#40). latency 측정 레일은 #38.

    metadata.jsonl → schema 검증 → dummy score → val 정상으로 threshold 조정 → test 판정 → 평가 → MLflow

모델은 seed 고정 random score다. **지표 숫자는 의미가 없고 인용하지 않는다.**
확인하는 것은 이후 모든 모델이 같은 loader / 평가 코드 / 기록 형식을 지나가는지다.

실행 (metadata.jsonl이 먼저 있어야 한다):
    uv run experiments/build_metadata.py mvtec_ad
    uv run experiments/week02_pipeline_check.py
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import yaml
from _bootstrap import REPO_ROOT  # sys.path + UTF-8 stdout. 첫 import여야 한다

from src.evaluation.latency import Stage, environment, measure, summarize
from src.evaluation.metrics import REVIEW_POLICY, calibrate, decide
from src.evaluation.scenarios import evaluate_scenarios
from src.utils.metadata import find_errors, read_jsonl
from src.utils.paths import SHARED_ROOT
from src.utils.tracking import (
    flat_metrics,
    flat_scenario_metrics,
    git_commit,
    git_is_dirty,
    start_experiment,
    write_predictions,
)

CONFIG_PATH = REPO_ROOT / "configs" / "week02_pipeline_check.yaml"
REGISTRY_PATH = REPO_ROOT / "datasets" / "registry.yaml"


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


def dummy_pipeline(_row: dict, stage: Stage) -> None:
    """latency 측정용 제품 1개 처리. 모델이 생기면 구간마다 실제 처리가 들어간다."""
    with stage("anomaly"):
        pass


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
    val_scores = [p["anomaly_score"] for p in score_all(val, rng)]
    t_ok, t_ng = calibrate(val, val_scores, dec["normal_ng_rate"], dec["normal_review_rate"])
    n_val_normal = sum(r["normal_or_defect"] == "normal" for r in val)
    preds = [p | {"decision": decide(p["anomaly_score"], t_ok, t_ng)} for p in score_all(test, rng)]
    metrics = evaluate_scenarios(test, preds)  # public track은 E1뿐이다
    lat_cfg = cfg["latency"]
    # 제품 1개 = test 샘플 1개 (public track은 L=1). dummy라 anomaly 구간만 있다
    latency = summarize(
        measure(
            dummy_pipeline,
            test,
            warmup=lat_cfg["warmup_iters"],
            iters=lat_cfg["measure_iters"],
        )
    )

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
                "threshold_source": f"{dec['calibration_split']} normal quantile (n={n_val_normal})",
                "normal_ng_rate": dec["normal_ng_rate"],
                "normal_review_rate": dec["normal_review_rate"],
                "seed": cfg["experiment"]["seed"],
                "num_train": sum(r["split"] == "train" for r in rows),
                "num_val": len(val),
                "num_test": len(test),
                "review_policy": REVIEW_POLICY,
            }
            | environment(
                lat_cfg["device"],
                lat_cfg["batch_size"],
                lat_cfg["resolution"],
                lat_cfg["precision"],
            )
        )
        mlflow.log_metrics(flat_scenario_metrics(metrics) | flat_metrics(latency))
        mlflow.log_artifact(str(CONFIG_PATH), artifact_path="config")
        mlflow.log_artifact(str(REGISTRY_PATH), artifact_path="config")
        with tempfile.TemporaryDirectory() as tmp:
            write_predictions(Path(tmp) / "predictions.csv", test, preds)
            (Path(tmp) / "metrics.json").write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (Path(tmp) / "latency.json").write_text(json.dumps(latency, indent=2), encoding="utf-8")
            mlflow.log_artifacts(tmp)

    e1 = metrics["E1"]
    der, cder = e1["defect_escape_rate"], e1["critical_defect_escape_rate"]
    print(f"run_id : {run.info.run_id}  ({cfg['tracking']['experiment_name']})")
    print(f"thresh : ok={t_ok:.3f} ng={t_ng:.3f}  (val 정상 {n_val_normal}장 분위수)")
    print(f"test   : {len(test)} samples  confusion {e1['confusion']}")
    print(f"DER    : {der['k']} / {der['n']} escaped = {der['value']:.2%}  95% CI {der['ci95']}")
    print(f"CDER   : {'N/A (Recipe severity 없음)' if cder['value'] is None else cder}")
    print(f"Review : {e1['review_rate']['value']:.2%}   AUROC {e1['auroc']:.3f}")
    print(
        f"Latency: P50 {latency['latency_p50']:.3f} / P95 {latency['latency_p95']:.3f} ms  {latency['latency_bands']}"
    )
    print("※ dummy random score — 숫자는 의미 없음")


if __name__ == "__main__":
    main()
