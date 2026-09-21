"""reports/evaluation_protocol.md §0~§2, §5, §6 을 코드와 1:1로 맞추는 테스트."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pytest

from src.evaluation.metrics import NG, OK, REVIEW, calibrate, decide, evaluate, rate


def _rows_preds(cases: Sequence[tuple[str, str, str | None]]) -> tuple[list[dict], list[dict]]:
    """(normal_or_defect, decision, defect_severity) 목록 → metadata rows, predictions."""
    rows, preds = [], []
    for i, (kind, decision, severity) in enumerate(cases):
        rows.append({"sample_id": f"s{i}", "normal_or_defect": kind, "defect_severity": severity})
        score = {OK: 0.1, REVIEW: 0.5, NG: 0.9}[decision]
        preds.append({"sample_id": f"s{i}", "decision": decision, "anomaly_score": score})
    return rows, preds


# --- §6 판정 경계: score < ok → OK, score > ng → NG, 사이(경계 포함)는 REVIEW ---


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.29, OK), (0.3, REVIEW), (0.5, REVIEW), (0.7, REVIEW), (0.71, NG)],
)
def test_decide_boundaries(score: float, expected: str) -> None:
    assert decide(score, t_ok=0.3, t_ng=0.7) == expected


def test_decide_without_review_band() -> None:
    assert decide(0.5, t_ok=0.5, t_ng=0.5) == REVIEW
    assert decide(0.49, t_ok=0.5, t_ng=0.5) == OK


def test_decide_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError):
        decide(0.5, t_ok=0.7, t_ng=0.3)


# --- §5 Clopper-Pearson 95% (양측) ---


def test_rate_zero_escape_upper_bound_matches_protocol_example() -> None:
    # evaluation_protocol.md §5: 0 / 1,200 → 상한 0.31%
    r = rate(0, 1200)
    assert r["value"] == 0.0
    assert r["ci95"][0] == 0.0
    assert r["ci95"][1] == pytest.approx(1 - 0.025 ** (1 / 1200))
    assert round(r["ci95"][1] * 100, 2) == 0.31


def test_rate_small_n_zero_escape_is_not_proof() -> None:
    # CRITICAL 12건 중 0건 escape → 상한 약 26%
    assert rate(0, 12)["ci95"][1] == pytest.approx(0.2646, abs=1e-4)


def test_rate_empty_denominator_is_none() -> None:
    assert rate(0, 0) == {"k": 0, "n": 0, "value": None, "ci95": None}


# --- §1 DER: REVIEW는 escape가 아니다 ---


def test_der_three_of_hundred() -> None:
    rows, preds = _rows_preds([("defect", OK, None)] * 3 + [("defect", NG, None)] * 97)
    der = evaluate(rows, preds)["defect_escape_rate"]
    assert (der["k"], der["n"]) == (3, 100)
    assert der["value"] == pytest.approx(0.03)


def test_review_is_neither_escape_nor_false_reject() -> None:
    rows, preds = _rows_preds([("defect", REVIEW, None), ("normal", REVIEW, None)])
    m = evaluate(rows, preds)
    assert m["defect_escape_rate"]["k"] == 0
    assert m["false_positive_rate"]["k"] == 0
    assert m["review_rate"]["value"] == 1.0


def test_confusion_is_actual_by_decision() -> None:
    rows, preds = _rows_preds(
        [("defect", OK, None), ("defect", REVIEW, None), ("defect", NG, None), ("normal", NG, None)]
    )
    assert evaluate(rows, preds)["confusion"] == {
        "normal": {OK: 0, REVIEW: 0, NG: 1},
        "defect": {OK: 1, REVIEW: 1, NG: 1},
    }


def test_two_state_metrics_merge_review_into_ng() -> None:
    # 2-state 지표는 REVIEW를 NG로 합친다 (ADR 0002). → recall = 1 - DER
    rows, preds = _rows_preds(
        [
            ("defect", OK, None),  # FN
            ("defect", REVIEW, None),  # TP
            ("defect", NG, None),  # TP
            ("normal", REVIEW, None),  # FP
            ("normal", OK, None),  # TN
        ]
    )
    m = evaluate(rows, preds)
    assert (m["recall"]["k"], m["recall"]["n"]) == (2, 3)
    assert m["recall"]["value"] == pytest.approx(1 - m["defect_escape_rate"]["value"])
    assert (m["precision"]["k"], m["precision"]["n"]) == (2, 3)
    assert m["f1"] == pytest.approx(2 / 3)
    assert m["false_positive_rate"]["k"] == 0  # REVIEW는 false reject가 아니다


def test_only_review_decisions() -> None:
    rows, preds = _rows_preds([("defect", REVIEW, None), ("normal", REVIEW, None)])
    m = evaluate(rows, preds)
    assert m["defect_escape_rate"]["value"] == 0.0
    assert m["recall"]["value"] == 1.0
    assert m["precision"]["value"] == 0.5


def test_no_defects_leaves_defect_metrics_undefined() -> None:
    rows, preds = _rows_preds([("normal", OK, None), ("normal", NG, None)])
    m = evaluate(rows, preds)
    assert m["defect_escape_rate"]["value"] is None
    assert m["recall"]["value"] is None
    assert m["f1"] is None
    assert m["auroc"] is None and m["auprc"] is None
    assert m["false_positive_rate"]["value"] == 0.5


def test_single_sample() -> None:
    rows, preds = _rows_preds([("defect", OK, None)])
    m = evaluate(rows, preds)
    assert m["defect_escape_rate"]["value"] == 1.0
    assert m["precision"]["value"] is None  # 양성 판정이 0건
    assert m["auroc"] is None


# --- CDER: severity=CRITICAL 한정. public track(severity null)은 계산하지 않는다 ---


def test_cder_counts_only_critical() -> None:
    rows, preds = _rows_preds(
        [("defect", OK, "CRITICAL"), ("defect", NG, "CRITICAL"), ("defect", OK, "MAJOR")]
    )
    cder = evaluate(rows, preds)["critical_defect_escape_rate"]
    assert (cder["k"], cder["n"]) == (1, 2)


def test_cder_is_none_without_recipe_severity() -> None:
    rows, preds = _rows_preds([("defect", OK, None), ("normal", OK, "none")])
    assert evaluate(rows, preds)["critical_defect_escape_rate"]["value"] is None


# --- threshold-free ---


def test_auroc_auprc_perfect_separation() -> None:
    rows, preds = _rows_preds([("normal", OK, None), ("defect", NG, None)])
    m = evaluate(rows, preds)
    assert m["auroc"] == 1.0
    assert m["auprc"] == 1.0


# --- 조인: 예측이 평가 대상과 정확히 일치해야 한다 ---


def test_missing_prediction_raises() -> None:
    rows, preds = _rows_preds([("normal", OK, None), ("defect", NG, None)])
    with pytest.raises(ValueError, match="s1"):
        evaluate(rows, preds[:1])


def test_unknown_decision_raises() -> None:
    rows, preds = _rows_preds([("normal", OK, None)])
    preds[0]["decision"] = "PASS"
    with pytest.raises(ValueError, match="PASS"):
        evaluate(rows, preds)


def test_values_are_finite_floats() -> None:
    rows, preds = _rows_preds([("normal", OK, None), ("defect", NG, None)])
    m = evaluate(rows, preds)
    assert all(math.isfinite(v) for v in m["defect_escape_rate"]["ci95"])


# --- §6 threshold calibration: val 정상 score 분위수 (schema §4.3 안 A) ---


def test_calibrate_quantiles() -> None:
    t_ok, t_ng = calibrate(
        [float(s) for s in range(100)], normal_ng_rate=0.01, normal_review_rate=0.1
    )
    assert (t_ok, t_ng) == (90.0, 99.0)


def test_calibrate_small_val_uses_max_for_ng() -> None:
    # val 42장이면 1% 해상도가 없다 → t_ng = 최고 점수 (val 정상은 하나도 NG가 아님)
    scores = [i / 42 for i in range(42)]
    assert calibrate(scores, normal_ng_rate=0.01, normal_review_rate=0.1)[1] == max(scores)


def test_calibrated_val_ng_rate_never_exceeds_target() -> None:
    rng = np.random.default_rng(0)
    for n in (5, 42, 167, 1000):
        scores = rng.random(n).tolist()
        t_ok, t_ng = calibrate(scores, normal_ng_rate=0.05, normal_review_rate=0.2)
        decisions = [decide(s, t_ok, t_ng) for s in scores]
        assert decisions.count(NG) <= 0.05 * n
        assert t_ok <= t_ng


@pytest.mark.parametrize(
    ("scores", "f", "r"),
    [([], 0.01, 0.1), ([0.5], 0.2, 0.1), ([0.5], -0.1, 0.1), ([0.5], 0.01, 1.5)],
)
def test_calibrate_rejects_bad_input(scores: list[float], f: float, r: float) -> None:
    with pytest.raises(ValueError):
        calibrate(scores, normal_ng_rate=f, normal_review_rate=r)
