"""Week 4 — Month 1 Gate 점검 (#39).

    Pilot metadata → 검증 → dummy score·identity → 제품별 val 분위수 threshold → test 판정
    → 3-level 평가 → 재현성 확인 → MLflow (protocol §9 보고 세트)

모델은 seed 고정 random이다. **지표 숫자는 의미가 없고 인용하지 않는다.**
확인하는 것은 Gate 조건이다: Pilot에서 모든 지표가 실제로 계산되는가, 같은 입력에 같은 숫자가
나오는가, §9의 params / metrics / artifacts가 MLflow에 전부 남는가.

실행 (Pilot이 먼저 있어야 한다):
    uv run experiments/build_pilot.py
    uv run experiments/week04_gate_check.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import yaml
from _bootstrap import REPO_ROOT  # sys.path + UTF-8 stdout. 첫 import여야 한다

from src.evaluation.latency import Stage, environment, measure, summarize
from src.evaluation.metrics import NG, OK, REVIEW_POLICY, UNKNOWN, calibrate, decide
from src.evaluation.scenarios import evaluate_scenarios
from src.utils.metadata import find_errors, read_jsonl
from src.utils.paths import SHARED_ROOT
from src.utils.pilot import check_built_version, text_sha256
from src.utils.tracking import (
    flat_metrics,
    flat_scenario_metrics,
    git_commit,
    git_is_dirty,
    open_test,
    start_experiment,
    write_predictions,
)

CONFIG_PATH = REPO_ROOT / "configs" / "week04_gate_check.yaml"
REGISTRY_PATH = REPO_ROOT / "datasets" / "registry.yaml"
GALLERY_MAX = 20  # 유형별 최대 장수 (protocol §9 FP/FN gallery)


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def score_all(rows: list[dict], labels: list[str], rng: np.random.Generator) -> list[dict]:
    """모델 자리. score와 identity(등록 라벨 + UNKNOWN 중 무작위)를 낸다."""
    return [
        {
            "sample_id": r["sample_id"],
            "anomaly_score": float(rng.random()),
            "predicted_label_id": str(rng.choice(labels)),
        }
        for r in rows
    ]


def run(rows: list[dict], recipe: dict, cfg: dict) -> tuple[list[dict], dict, dict]:
    """score → 제품별 val calibration → test 판정 → 평가. rng를 매번 새로 만들어 재현성을 본다."""
    rng = np.random.default_rng(cfg["experiment"]["seed"])
    dec, split = cfg["decision"], cfg["dataset"]["split"]
    labels = [k for k, v in recipe["labels"].items() if v.get("known", True)] + [UNKNOWN]
    preds, thresholds = [], {}
    for pid, spec in recipe["products"].items():
        mine = [r for r in rows if r["product_id"] == pid]
        val = [r for r in mine if r["split"] == dec["calibration_split"]]
        f = 1 - (1 - recipe["product_false_reject_target"]) ** (1 / len(spec["slots"]))
        val_scores = [p["anomaly_score"] for p in score_all(val, labels, rng)]
        t_ok, t_ng = calibrate(val, val_scores, f, dec["normal_review_rate"])
        n_normal = sum(r["normal_or_defect"] == "normal" for r in val)
        thresholds[pid] = {"f": f, "ok": t_ok, "ng": t_ng, "n_val_normal": n_normal}
        test = [r for r in mine if r["split"] == split]
        preds += [
            p | {"decision": decide(p["anomaly_score"], t_ok, t_ng)}
            for p in score_all(test, labels, rng)
        ]
    return preds, evaluate_scenarios([r for r in rows if r["split"] == split], preds), thresholds


def dummy_pipeline(unit_rows: list[dict], stage: Stage) -> None:
    """latency 측정용 제품 1개 처리 = 그 제품의 Label Slot 전부. 모델이 생기면 구간이 늘어난다."""
    for _ in unit_rows:
        with stage("anomaly"):
            pass


def write_gallery(out: Path, image_root: Path, test: list[dict], preds: list[dict]) -> None:
    """FN(불량 → OK)과 FP(정상 → NG) ROI 이미지를 유형별 최대 GALLERY_MAX장 복사한다."""
    by_id = {r["sample_id"]: r for r in test}
    for kind, want in (("fn", ("defect", OK)), ("fp", ("normal", NG))):
        picked = [
            p for p in preds if (by_id[p["sample_id"]]["normal_or_defect"], p["decision"]) == want
        ]
        (out / kind).mkdir(parents=True)
        for p in picked[:GALLERY_MAX]:
            name = p["sample_id"].replace("/", "_") + ".png"
            shutil.copy(image_root / by_id[p["sample_id"]]["image_path"], out / kind / name)


def main() -> None:
    cfg = load_yaml(CONFIG_PATH)
    reg = load_yaml(REGISTRY_PATH)[cfg["dataset"]["name"]]
    test_tags = open_test(reg, cfg)  # 봉인된 pilot test는 final_report일 때만 (#69 T9)
    recipe_path = REPO_ROOT / reg["recipe"]
    recipe_sha = text_sha256(recipe_path.read_bytes())
    if recipe_sha != reg["sha256"]:
        raise ValueError(f"Recipe가 registry와 다르다 — build_pilot.py로 재생성: {recipe_sha}")
    recipe = load_yaml(recipe_path)

    image_root = SHARED_ROOT / reg["root"]
    check_built_version(image_root, reg["version"])
    rows = read_jsonl(SHARED_ROOT / reg["metadata"])
    if errors := find_errors(rows, image_root=image_root):
        raise ValueError(f"metadata 검증 실패 {len(errors)}건: {errors[:5]}")

    preds, metrics, thresholds = run(rows, recipe, cfg)
    _, again, _ = run(rows, recipe, cfg)
    reproducible = json.dumps(metrics, sort_keys=True) == json.dumps(again, sort_keys=True)
    if not reproducible:
        raise ValueError("재현성 실패: 같은 seed로 두 번 돌린 지표가 다르다")

    test = [r for r in rows if r["split"] == cfg["dataset"]["split"]]
    units: dict[str, list[dict]] = defaultdict(list)
    for r in test:
        units[r["unit_id"]].append(r)
    lat_cfg = cfg["latency"]
    latency = summarize(
        measure(
            dummy_pipeline,
            list(units.values()),
            warmup=lat_cfg["warmup_iters"],
            iters=lat_cfg["measure_iters"],
        )
    )

    start_experiment(cfg["tracking"]["experiment_name"])
    with mlflow.start_run(run_name="dummy-pilot") as run_info:
        mlflow.set_tags({"purpose": "month1_gate", "citable": "false"} | test_tags)
        # Pilot은 제품마다 L이 달라 f와 threshold가 제품별이다 → `{이름}_{제품}`
        per_product = {
            f"{key}_{pid}": t[name]
            for pid, t in thresholds.items()
            for key, name in (
                ("normal_ng_rate", "f"),
                ("threshold_ok", "ok"),
                ("threshold_ng", "ng"),
                ("num_val_normal", "n_val_normal"),
            )
        }
        mlflow.log_params(
            {
                "git_commit": git_commit(),
                "git_dirty": git_is_dirty(),
                "config_path": CONFIG_PATH.relative_to(REPO_ROOT).as_posix(),
                "dataset_name": cfg["dataset"]["name"],
                "dataset_version": reg["version"],
                "dataset_sha256": reg["sha256"],
                "dataset_schema": reg["schema"],
                "recipe_sha256": recipe_sha,
                "split": cfg["dataset"]["split"],
                "model_name": cfg["model"]["name"],
                "n_shot": "none",
                "seed": cfg["experiment"]["seed"],
                "threshold_source": "per-product val normal quantile, f from product F",
                "product_false_reject_target": recipe["product_false_reject_target"],
                "normal_review_rate": cfg["decision"]["normal_review_rate"],
                "num_test": len(test),
                "num_test_units": len(units),
                "reproducible": reproducible,
                "review_policy": REVIEW_POLICY,
            }
            | per_product
            | environment(
                lat_cfg["device"],
                lat_cfg["batch_size"],
                lat_cfg["resolution"],
                lat_cfg["precision"],
            )
        )
        mlflow.log_metrics(flat_scenario_metrics(metrics) | flat_metrics(latency))
        for path in (CONFIG_PATH, REGISTRY_PATH, recipe_path):
            mlflow.log_artifact(str(path), artifact_path="config")
        with tempfile.TemporaryDirectory() as tmp:
            write_predictions(Path(tmp) / "predictions.csv", test, preds)
            (Path(tmp) / "metrics.json").write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (Path(tmp) / "latency.json").write_text(json.dumps(latency, indent=2), encoding="utf-8")
            write_gallery(Path(tmp) / "gallery", image_root, test, preds)
            mlflow.log_artifacts(tmp)

    def pct(r: dict) -> str:
        return "N/A" if r["value"] is None else f"{r['k']}/{r['n']} = {r['value']:.2%}"

    print(f"run_id : {run_info.info.run_id}  ({cfg['tracking']['experiment_name']})")
    print(f"재현성 : 같은 seed 두 번 → 지표 {'일치' if reproducible else '불일치'}")
    for pid, t in thresholds.items():
        print(
            f"thresh {pid}: f={t['f']:.3%} ok={t['ok']:.4f} ng={t['ng']:.4f}"
            f"  (val 정상 {t['n_val_normal']})"
        )
    e1 = metrics["E1"]
    for level, m in (
        ("Defect", e1),
        ("Label", e1["label_level"]),
        ("Product", e1["product_level"]),
    ):
        print(
            f"E1 {level:7s}: n={m['n']}  DER {pct(m['defect_escape_rate'])}"
            f"  CDER {pct(m['critical_defect_escape_rate'])}"
            f"  FPR {pct(m['false_positive_rate'])}  Review {pct(m['review_rate'])}"
        )
    print(f"E1 known_label_accuracy          : {pct(e1['known_label_accuracy'])}")
    for name in (
        "unknown_label_ok_rate",
        "unknown_label_detection_rate",
        "unknown_forced_rate",
        "open_set_accuracy",
    ):
        print(f"E3 {name:29s}: {pct(metrics['E3'][name])}")
    print(
        "E4 DER : "
        + "  ".join(f"{k} {pct(v)}" for k, v in metrics["E4"]["defect_escape_rate_by_type"].items())
    )
    e5 = metrics["E5"]["similar_label_confusion_rate"]
    print("E5     : " + "  ".join(f"{k} {pct(v)}" for k, v in e5.items()))
    print(
        f"Latency: P50 {latency['latency_p50']:.3f} / P95 {latency['latency_p95']:.3f} ms"
        f"  (제품 {latency['latency_n']}회)"
    )
    print("※ dummy — 숫자는 의미 없음")


if __name__ == "__main__":
    main()
