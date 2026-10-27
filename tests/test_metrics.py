"""reports/evaluation_protocol.md §0~§6 을 코드와 1:1로 맞추는 테스트."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pytest

from src.evaluation.metrics import (
    NG,
    OK,
    REVIEW,
    UNKNOWN,
    calibrate,
    decide,
    evaluate,
    label_rate,
    normalize,
    rate,
    risk_coverage,
)


def _rows_preds(cases: Sequence[tuple[str, str, str | None]]) -> tuple[list[dict], list[dict]]:
    """(normal_or_defect, decision, defect_severity) 목록 → metadata rows, predictions."""
    rows, preds = [], []
    for i, (kind, decision, severity) in enumerate(cases):
        rows.append(
            {"sample_id": f"s{i}", "unit_id": f"u{i}", "label_slot": "-"}
            | {"normal_or_defect": kind, "defect_severity": severity}
        )
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


def _val(scores: Sequence[float]) -> list[dict]:
    return [{"split": "val", "normal_or_defect": "normal"} for _ in scores]


def test_calibrate_quantiles() -> None:
    scores = [float(s) for s in range(100)]
    t_ok, t_ng = calibrate(_val(scores), scores, normal_ng_rate=0.01, normal_review_rate=0.1)
    assert (t_ok, t_ng) == (90.0, 99.0)


def test_calibrate_small_val_uses_max_for_ng() -> None:
    # val 42장이면 1% 해상도가 없다 → t_ng = 최고 점수 (val 정상은 하나도 NG가 아님)
    scores = [i / 42 for i in range(42)]
    assert calibrate(_val(scores), scores, normal_ng_rate=0.01, normal_review_rate=0.1)[1] == max(
        scores
    )


def test_calibrated_val_ng_rate_never_exceeds_target() -> None:
    rng = np.random.default_rng(0)
    for n in (5, 42, 167, 1000):
        scores = rng.random(n).tolist()
        t_ok, t_ng = calibrate(_val(scores), scores, normal_ng_rate=0.05, normal_review_rate=0.2)
        decisions = [decide(s, t_ok, t_ng) for s in scores]
        assert decisions.count(NG) <= 0.05 * n
        assert t_ok <= t_ng


@pytest.mark.parametrize(
    ("scores", "f", "r"),
    [([], 0.01, 0.1), ([0.5], 0.2, 0.1), ([0.5], -0.1, 0.1), ([0.5], 0.01, 1.5)],
)
def test_calibrate_rejects_bad_input(scores: list[float], f: float, r: float) -> None:
    with pytest.raises(ValueError):
        calibrate(_val(scores), scores, normal_ng_rate=f, normal_review_rate=r)


def test_calibrate_refuses_non_val_rows() -> None:
    """test로 threshold를 정하는 경로를 코드가 막는다 (§6)."""
    rows = [*_val([0.1, 0.2]), {"split": "test", "normal_or_defect": "normal"}]
    with pytest.raises(ValueError, match="val로만"):
        calibrate(rows, [0.1, 0.2, 0.3], normal_ng_rate=0.01, normal_review_rate=0.1)


def test_calibrate_ignores_defect_rows() -> None:
    rows = [*_val([0.1] * 10), {"split": "val", "normal_or_defect": "defect"}]
    assert calibrate(rows, [*[0.1] * 10, 99.0], 0.0, 0.0) == (0.1, 0.1)


# --- E4 public 보고: 결함 분류·유형별 DER (reports/experiment_scenarios.md) ---


def test_der_breakdown_by_category_and_type() -> None:
    rows, preds = _rows_preds(
        [("defect", OK, None), ("defect", NG, None), ("defect", OK, None), ("normal", OK, None)]
    )
    for row, (cat, typ) in zip(
        rows[:3],
        [("logical", "missing"), ("logical", "missing"), ("visual", "scratch")],
        strict=True,
    ):
        row |= {"defect_category": cat, "defect_type": typ}
    m = evaluate(rows, preds)
    by_cat = m["defect_escape_rate_by_category"]
    assert {k: (v["k"], v["n"]) for k, v in by_cat.items()} == {"logical": (1, 2), "visual": (1, 1)}
    by_type = m["defect_escape_rate_by_type"]
    assert {k: (v["k"], v["n"]) for k, v in by_type.items()} == {
        "missing": (1, 2),
        "scratch": (1, 1),
    }


# --- §3 Similar-label Confusion Rate (E5) ---


def test_similar_label_confusion_rate_is_swap_escape_by_tier() -> None:
    """E5-<구간> 태그가 달린 바꿔치기 불량 중 OK로 나간 비율. 태그 없는 row는 세지 않는다."""
    rows, preds = _rows_preds(
        [
            ("defect", OK, "CRITICAL"),  # E5-extreme, 새어 나감
            ("defect", NG, "CRITICAL"),  # E5-extreme
            ("defect", REVIEW, "CRITICAL"),  # E5-hard — REVIEW는 escape가 아니다
            ("defect", OK, "CRITICAL"),  # 태그 없음 (E5가 아닌 불량)
            ("normal", OK, "none"),
        ]
    )
    for row, tags in zip(rows, (["E5-extreme"], ["E5-extreme"], ["E5-hard"], [], []), strict=True):
        row["experiment_tags"] = tags
    confusion = evaluate(rows, preds)["similar_label_confusion_rate"]
    assert {k: (v["k"], v["n"]) for k, v in confusion.items()} == {
        "extreme": (1, 2),
        "hard": (0, 1),
    }


def test_similar_label_confusion_rate_empty_without_e5_tags() -> None:
    """public track처럼 E5 태그가 없으면 빈 dict — 0%가 아니라 '해당 없음'이다."""
    rows, preds = _rows_preds([("defect", OK, None), ("normal", OK, "none")])
    assert evaluate(rows, preds)["similar_label_confusion_rate"] == {}


def test_effective_sample_size_pairs_and_identities() -> None:
    """행 수가 아니라 쌍·아이덴티티 수가 일반화의 표본이다 (#69 T11). 쌍은 순서를 따지지 않는다."""
    rows, preds = _rows_preds(
        [
            ("defect", OK, "CRITICAL"),  # b-3 → b-4 extreme, 새어 나감
            ("defect", NG, "CRITICAL"),  # b-4 → b-3 extreme (같은 쌍)
            ("defect", NG, "CRITICAL"),  # a-2 → a-5 hard
            ("normal", OK, "none"),  # 미등록 u-1, OK로 나감
            ("normal", NG, "none"),  # 미등록 u-1
            ("normal", REVIEW, "none"),  # 미등록 u-2
        ]
    )
    meta = [
        ("b-3", "b-4", ["E5-extreme"], True),
        ("b-4", "b-3", ["E5-extreme"], True),
        ("a-5", "a-2", ["E5-hard"], True),
        ("u-1", "u-1", [], False),
        ("u-1", "u-1", [], False),
        ("u-2", "u-2", [], False),
    ]
    for row, (expected, actual, tags, known) in zip(rows, meta, strict=True):
        row |= {"expected_label_id": expected, "actual_label_id": actual}
        row |= {"experiment_tags": tags, "is_known_label": known}
    m = evaluate(rows, preds)
    assert m["n_pairs"] == {"extreme": 1, "hard": 1}
    by_pair = m["similar_label_confusion_rate_by_pair"]
    assert {k: (v["k"], v["n"]) for k, v in by_pair.items()} == {
        "a-2/a-5": (0, 1),
        "b-3/b-4": (1, 2),
    }
    assert m["n_identities"] == 2
    by_label = m["unknown_label_ok_rate_by_label"]
    assert {k: (v["k"], v["n"]) for k, v in by_label.items()} == {"u-1": (1, 2), "u-2": (0, 1)}


# --- §4 Label / Product-level 집계 (ADR 0003) ---


def _units(units: dict[str, list[tuple[str, str, str, str | None]]]) -> tuple[list, list]:
    """{unit_id: [(label_slot, normal_or_defect, decision, severity), ...]} → rows, preds."""
    cases = [(kind, dec, sev) for labels in units.values() for _, kind, dec, sev in labels]
    rows, preds = _rows_preds(cases)
    keys = [(u, slot) for u, labels in units.items() for slot, *_ in labels]
    for row, (unit, slot) in zip(rows, keys, strict=True):
        row |= {"unit_id": unit, "label_slot": slot}
    return rows, preds


def test_product_level_ng_beats_review_regardless_of_severity() -> None:
    rows, preds = _units(
        {
            "u-ng": [("s1", "normal", NG, None), ("s2", "defect", REVIEW, "MAJOR")],
            "u-escape": [("s1", "defect", OK, "MAJOR"), ("s2", "normal", OK, None)],
            "u-review": [("s1", "normal", REVIEW, None), ("s2", "normal", OK, None)],
            "u-ok": [("s1", "normal", OK, None), ("s2", "normal", OK, None)],
        }
    )
    product = evaluate(rows, preds)["product_level"]
    assert product["confusion"] == {
        "normal": {OK: 1, REVIEW: 1, NG: 0},
        "defect": {OK: 1, REVIEW: 0, NG: 1},  # u-ng: NG 라벨이 REVIEW보다 우선
    }
    assert (product["defect_escape_rate"]["k"], product["defect_escape_rate"]["n"]) == (1, 2)
    assert product["review_rate"]["k"] == 1


def test_product_level_cder_follows_critical_label() -> None:
    rows, preds = _units({"u1": [("s1", "defect", OK, "CRITICAL"), ("s2", "defect", NG, "MINOR")]})
    m = evaluate(rows, preds)
    assert m["critical_defect_escape_rate"]["k"] == 1  # 라벨 단위로는 새었다
    assert m["product_level"]["critical_defect_escape_rate"]["k"] == 0  # 제품은 NG로 걸렸다


def test_label_level_merges_cameras_of_same_label() -> None:
    """같은 (unit_id, label_slot)의 row 여러 개(카메라)는 라벨 하나다. 판정은 최악값."""
    rows, preds = _units({"u1": [("s1", "normal", OK, None), ("s1", "normal", REVIEW, None)]})
    label = evaluate(rows, preds)["label_level"]
    assert label["n"] == 1
    assert label["confusion"]["normal"] == {OK: 0, REVIEW: 1, NG: 0}


def test_false_positive_rate_2state_merges_review() -> None:
    rows, preds = _rows_preds(
        [("normal", REVIEW, None), ("normal", NG, None), ("normal", OK, None)]
    )
    m = evaluate(rows, preds)
    assert m["false_positive_rate"]["k"] == 1
    assert m["false_positive_rate_2state"]["k"] == 2


# --- §3 Known / Unknown Label ---


def _identity_case(cases: list[tuple[bool, str | None, str | None]]) -> dict:
    """(is_known_label, actual_label_id, predicted_label_id) 목록 → evaluate 결과."""
    rows, preds = _rows_preds([("normal", OK, None)] * len(cases))
    for row, pred, (known, actual, predicted) in zip(rows, preds, cases, strict=True):
        row |= {"is_known_label": known, "actual_label_id": actual}
        pred["predicted_label_id"] = predicted
    return evaluate(rows, preds)


def test_identity_metrics_count_forced_unknown_separately() -> None:
    m = _identity_case(
        [
            (True, "a-1", "a-1"),
            (True, "a-2", "a-1"),  # 오답
            (True, "a-3", UNKNOWN),  # 등록 라벨을 거부 — 오답
            (True, None, None),  # missing_label: 맞힐 라벨이 없다 → 제외
            (False, "u-1", UNKNOWN),  # 거부 성공
            (False, "u-2", "a-1"),  # 억지 분류
            (False, "u-2", None),  # 답 없음 — 거부도 억지 분류도 아니다
        ]
    )
    assert (m["known_label_accuracy"]["k"], m["known_label_accuracy"]["n"]) == (1, 3)
    assert (m["unknown_label_detection_rate"]["k"], m["unknown_label_detection_rate"]["n"]) == (
        1,
        3,
    )
    assert (m["unknown_forced_rate"]["k"], m["unknown_forced_rate"]["n"]) == (1, 3)


def test_identity_metrics_undefined_without_identity_output() -> None:
    """AD 모델처럼 predicted_label_id를 전혀 내지 않으면 0%가 아니라 '정의되지 않음'."""
    m = _identity_case([(True, "a-1", None), (False, "u-1", None)])
    for name in ("known_label_accuracy", "unknown_label_detection_rate", "unknown_forced_rate"):
        assert m[name]["value"] is None


# --- E3 주 기준과 Open-set 3-state (§3) ---


def test_unknown_label_ok_rate_uses_decision_only() -> None:
    """미등록 라벨 row가 OK로 나간 비율. identity 출력이 없어도 계산된다."""
    rows, preds = _rows_preds(
        [("normal", OK, None), ("normal", REVIEW, None), ("normal", OK, None)]
    )
    for row, known in zip(rows, (False, False, True), strict=True):
        row["is_known_label"] = known
    r = evaluate(rows, preds)["unknown_label_ok_rate"]
    assert (r["k"], r["n"]) == (1, 2)


def test_open_set_accuracy_three_states() -> None:
    cases = [
        # (is_known, expected, actual, predicted) → 맞으면 True
        (True, "a-1", "a-1", "a-1"),  # KNOWN_EXPECTED == KNOWN_EXPECTED
        (True, "a-1", "b-3", "b-2"),  # KNOWN_WRONG == KNOWN_WRONG (어떤 틀린 라벨인지는 안 본다)
        (True, "a-1", "b-3", "a-1"),  # KNOWN_WRONG != KNOWN_EXPECTED
        (False, "u-1", "u-1", UNKNOWN),  # UNKNOWN == UNKNOWN
        (False, "u-1", "u-1", "a-1"),  # 억지 분류
        (True, "a-1", None, None),  # missing_label → 제외
    ]
    rows, preds = _rows_preds([("normal", OK, None)] * len(cases))
    for row, pred, (known, expected, actual, predicted) in zip(rows, preds, cases, strict=True):
        row |= {"is_known_label": known, "expected_label_id": expected, "actual_label_id": actual}
        pred["predicted_label_id"] = predicted
    acc = evaluate(rows, preds)["open_set_accuracy"]
    assert (acc["k"], acc["n"]) == (3, 5)


# --- §6 제품 검토 예산 R과 risk-coverage (#69 T10) ---


def test_label_rate_inverts_product_rate() -> None:
    """R=5%: L=3 → r≈1.70%, L=4 → r≈1.27% (이슈 #69 T10의 예). L=1이면 그대로다."""
    assert round(label_rate(0.05, 3), 4) == 0.0170
    assert round(label_rate(0.05, 4), 4) == 0.0127
    assert label_rate(0.05, 1) == pytest.approx(0.05)


def test_risk_coverage_points_and_area() -> None:
    """예산이 작으면 불량 제품이 OK로 새고, 크면 두 제품 다 REVIEW로 간다 — 손으로 그린 두 점의 면적 0.5."""
    rows = [
        {"unit_id": "bad", "normal_or_defect": "defect", "defect_severity": "CRITICAL"},
        {"unit_id": "bad", "normal_or_defect": "normal", "defect_severity": "none"},
        {"unit_id": "good", "normal_or_defect": "normal", "defect_severity": "none"},
    ]

    def decide_at(target: float) -> list[str]:
        return [OK, OK, OK] if target < 0.1 else [REVIEW, OK, REVIEW]

    rc = risk_coverage(rows, decide_at, [0.05, 0.2])
    assert [(p["review_rate"], p["der"], p["cder"]) for p in rc["points"]] == [
        (0.0, 1.0, 1.0),
        (1.0, 0.0, 0.0),
    ]
    assert rc["aurc"] == pytest.approx(0.5)


# --- §6 슬롯별 점수 정규화 (#69 T12) ---


def _two_slots(split: str, n: int, rng: np.random.Generator) -> tuple[list[dict], list[float]]:
    """정상만. 슬롯 B는 정상 점수 분포가 3만큼 높다 — 실제 AD 모델에서 라벨 종류마다 생기는 차이."""
    rows, scores = [], []
    for slot, shift in (("A", 0.0), ("B", 3.0)):
        for i in range(n):
            rows.append(
                {
                    "sample_id": f"{split}/{slot}/{i}",
                    "unit_id": f"{split}/{slot}/{i}",
                    "product_id": "P",
                }
                | {"label_slot": slot, "split": split, "normal_or_defect": "normal"}
                | {"defect_severity": "none"}
            )
            scores.append(float(rng.normal(shift, 1.0)))
    return rows, scores


@pytest.mark.parametrize("method", ["zscore", "rank"])
def test_slot_normalization_evens_out_slot_fpr(method: str) -> None:
    """한 threshold로 묶으면 NG가 점수 높은 슬롯에 몰린다. 정규화하면 슬롯별 FPR 편차가 준다."""
    rng = np.random.default_rng(0)
    val, val_scores = _two_slots("val", 400, rng)
    test, test_scores = _two_slots("test", 400, rng)

    def spread(v: list[float], t: list[float]) -> float:
        ok, ng = calibrate(val, v, 0.05, 0.10)
        preds = [
            {"sample_id": r["sample_id"], "decision": decide(s, ok, ng), "anomaly_score": s}
            for r, s in zip(test, t, strict=True)
        ]
        return evaluate(test, preds)["slot_fpr_spread"]

    raw = spread(val_scores, test_scores)
    normed = spread(
        normalize(val, val_scores, val, val_scores, method),
        normalize(val, val_scores, test, test_scores, method),
    )
    assert raw > 0.05 and normed < raw / 3


def test_normalize_fits_on_val_normal_only() -> None:
    rows = [{"split": "test", "normal_or_defect": "normal", "product_id": "P", "label_slot": "A"}]
    with pytest.raises(ValueError, match="val"):
        normalize(rows, [0.0], rows, [0.0])
