"""reports/evaluation_protocol.md §0~§2, §5, §6 의 코드 정본.

REVIEW 처리 규칙 (ADR 0002):
- DER / FPR: REVIEW는 escape도 false reject도 아니다 (3-state 그대로).
- Precision / Recall / F1: 2-state 지표이므로 REVIEW를 NG로 합친다. 따라서 Recall = 1 - DER.
- Review Rate: 전체 중 REVIEW 비율. 별도 비용 지표.

모든 비율 지표는 분자/분모와 Clopper-Pearson(exact) 양측 95% 신뢰구간을 함께 낸다 (ADR 0005).
집계 단위는 입력 row 그대로다. Label/Product-level 집계는 #37.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy.stats import binomtest
from sklearn.metrics import average_precision_score, roc_auc_score

OK, REVIEW, NG = "OK", "REVIEW", "NG"
DECISIONS = (OK, REVIEW, NG)
REVIEW_POLICY = (
    "DER/FPR: REVIEW is neither escape nor false reject; precision/recall/F1: REVIEW merged into NG"
)


def decide(score: float, t_ok: float, t_ng: float) -> str:
    """score < t_ok → OK, score > t_ng → NG, 그 사이(경계 포함)는 REVIEW."""
    if t_ok > t_ng:
        raise ValueError(f"t_ok({t_ok}) > t_ng({t_ng})")
    if score < t_ok:
        return OK
    if score > t_ng:
        return NG
    return REVIEW


def calibrate(
    normal_scores: Sequence[float], normal_ng_rate: float, normal_review_rate: float
) -> tuple[float, float]:
    """val 정상 score만으로 (t_ok, t_ng)를 정한다 (evaluation_protocol §6, schema §4.3 안 A).

    t_ng = Q(1-f): val 정상 중 NG(score > t_ng)는 f 이하다 — f가 목표 과검률.
    t_ok = Q(1-r): val 정상 중 약 r이 REVIEW 이상으로 간다.
    Q는 관측값 중에서 고르는 경험 분위수(method="higher")라 val이 작으면 해상도가 거칠다.
    """
    if len(normal_scores) == 0:
        raise ValueError("calibration용 정상 score가 없다")
    if not 0 <= normal_ng_rate <= normal_review_rate <= 1:
        raise ValueError(f"0 <= f({normal_ng_rate}) <= r({normal_review_rate}) <= 1 이어야 한다")
    t_ok, t_ng = np.quantile(
        normal_scores, [1 - normal_review_rate, 1 - normal_ng_rate], method="higher"
    )
    return float(t_ok), float(t_ng)


def rate(k: int, n: int) -> dict[str, Any]:
    """k/n 과 Clopper-Pearson 95% 구간. n == 0이면 정의되지 않으므로 None."""
    if n == 0:
        return {"k": 0, "n": 0, "value": None, "ci95": None}
    ci = binomtest(k, n).proportion_ci(confidence_level=0.95, method="exact")
    return {"k": k, "n": n, "value": k / n, "ci95": [float(ci.low), float(ci.high)]}


def evaluate(rows: list[dict[str, Any]], preds: list[dict[str, Any]]) -> dict[str, Any]:
    """metadata rows 와 predictions 를 sample_id로 조인해서 지표를 계산한다."""
    by_id = {p["sample_id"]: p for p in preds}
    missing = [r["sample_id"] for r in rows if r["sample_id"] not in by_id]
    if missing or len(preds) != len(rows):  # rows의 sample_id 고유성은 metadata 검증기가 보장
        raise ValueError(
            f"예측이 평가 대상과 다르다 (누락 {missing[:5]}, rows {len(rows)}, preds {len(preds)})"
        )

    is_defect = [r["normal_or_defect"] == "defect" for r in rows]
    decision = [by_id[r["sample_id"]]["decision"] for r in rows]
    score = [by_id[r["sample_id"]]["anomaly_score"] for r in rows]
    if bad := sorted(set(decision) - set(DECISIONS)):
        raise ValueError(f"알 수 없는 decision: {bad}")

    def count(kind: bool, dec: str) -> int:
        return sum(d == kind and x == dec for d, x in zip(is_defect, decision, strict=True))

    n_def, n_norm = sum(is_defect), len(rows) - sum(is_defect)
    fn = count(True, OK)
    tp, fp = n_def - fn, n_norm - count(False, OK)  # 2-state: REVIEW → NG
    critical = [r.get("defect_severity") == "CRITICAL" for r in rows]
    precision, recall = rate(tp, tp + fp), rate(tp, n_def)
    p, r = precision["value"], recall["value"]

    return {
        "n": len(rows),
        "review_policy": REVIEW_POLICY,
        "confusion": {
            "normal": {x: count(False, x) for x in DECISIONS},
            "defect": {x: count(True, x) for x in DECISIONS},
        },
        "defect_escape_rate": rate(fn, n_def),
        "critical_defect_escape_rate": rate(
            sum(c and x == OK for c, x in zip(critical, decision, strict=True)), sum(critical)
        ),
        "false_positive_rate": rate(count(False, NG), n_norm),
        "review_rate": rate(decision.count(REVIEW), len(rows)),
        "precision": precision,
        "recall": recall,
        "f1": 2 * p * r / (p + r) if p is not None and r is not None and p + r > 0 else None,
        "auroc": float(roc_auc_score(is_defect, score)) if n_def and n_norm else None,
        "auprc": float(average_precision_score(is_defect, score)) if n_def and n_norm else None,
    }
