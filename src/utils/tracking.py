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
    """`evaluate_scenarios()` 결과 → 범위 접두사를 붙인 이름 (`e1_defect_escape_rate`,
    `geom_boundary_review_rate` …, §9)."""
    return {
        f"{s.lower().replace('-', '_')}_{k}": v
        for s, m in by_scenario.items()
        for k, v in flat_metrics(m).items()
    }


def open_test(reg_entry: dict[str, Any], cfg: dict[str, Any]) -> dict[str, str]:
    """봉인된 test(registry `test_sealed`)는 config `experiment.final_report: true`일 때만 연다 (#69 T9).

    test를 보면서 방향을 정하면 test가 더 이상 test가 아니다. 분석은 같은 Recipe의 `pilot_dev`로 한다.
    돌려주는 dict는 run 태그다 — 연 run에는 `test_opened=true`가 남는다.
    """
    if cfg["dataset"]["split"] != "test" or not reg_entry.get("test_sealed"):
        return {}
    if not cfg["experiment"].get("final_report"):
        raise PermissionError(
            f"{cfg['dataset']['name']} test는 봉인돼 있다 — 분석은 pilot_dev로, "
            "최종 보고 run만 experiment.final_report: true"
        )
    return {"test_opened": "true"}


def write_risk_coverage(out: Path, rc: dict[str, Any], chosen: float) -> None:
    """`risk_coverage()` 결과 → `risk_coverage.csv` + `.png` (protocol §6). chosen = 이 run이 쓴 R."""
    from matplotlib.figure import Figure  # pyplot 없이 그린다 — 전역 상태·GUI backend가 필요 없다

    with (out / "risk_coverage.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rc["points"][0]))
        writer.writeheader()
        writer.writerows(rc["points"])
    fig = Figure(figsize=(5, 3.5))
    ax = fig.subplots()
    for key in ("der", "cder"):
        pts = [(p["review_rate"], p[key]) for p in rc["points"] if p[key] is not None]
        if pts:
            ax.plot([x for x, _ in pts], [y for _, y in pts], marker="o", label=key.upper())
    for p in rc["points"]:
        if p["product_review_target"] == chosen:
            ax.axvline(p["review_rate"], linestyle=":", color="gray", label=f"R={chosen:.0%}")
    ax.set_xlabel("Product-level Review Rate")
    ax.set_ylabel("Product-level escape rate")
    ax.set_title(
        f"risk-coverage (AURC={rc['aurc']:.4f})" if rc["aurc"] is not None else "risk-coverage"
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "risk_coverage.png", dpi=120)


def write_predictions(path: Path, rows: list[dict], preds: list[dict]) -> None:
    by_id = {r["sample_id"]: r for r in rows}
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PRED_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(by_id[p["sample_id"]] | p for p in preds)
