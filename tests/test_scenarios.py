"""시나리오별 평가 범위 (ADR 0008, experiment_scenarios v1.4) 를 고정하는 테스트."""

from __future__ import annotations

from typing import Any

import pytest

from src.evaluation.metrics import NG, OK
from src.evaluation.scenarios import evaluate_scenarios, scenario_rows
from src.utils.tracking import flat_scenario_metrics, open_test


def _row(unit: str, slot: str, **kw: Any) -> dict[str, Any]:
    return {
        "sample_id": f"{unit}/{slot}",
        "unit_id": unit,
        "label_slot": slot,
        "normal_or_defect": "normal",
        "defect_severity": "none",
        "is_known_label": True,
        "is_known_defect": True,
        "experiment_tags": [],
    } | kw


def _preds(rows: list[dict[str, Any]], decisions: list[str]) -> list[dict[str, Any]]:
    return [
        {"sample_id": r["sample_id"], "decision": d, "anomaly_score": {OK: 0.1, NG: 0.9}[d]}
        for r, d in zip(rows, decisions, strict=True)
    ]


def test_rejecting_unknown_label_is_not_a_false_positive() -> None:
    """#69 T2의 2행 예제. 미등록 라벨을 NG로 거부한 것은 E3 정답이지 E1 과검이 아니다."""
    rows = [_row("u1", "s1"), _row("u2", "s1", is_known_label=False)]
    m = evaluate_scenarios(rows, _preds(rows, [OK, NG]))

    for level in (m["E1"], m["E1"]["product_level"]):
        fpr = level["false_positive_rate"]
        assert (fpr["k"], fpr["n"]) == (0, 1)
    ok = m["E3"]["unknown_label_ok_rate"]
    assert (ok["k"], ok["n"]) == (0, 1)


def test_units_are_never_split() -> None:
    """미등록 라벨이 한 자리라도 있으면 unit 전체가 E3다. 나머지 자리는 E1에 남지 않는다."""
    rows = [_row("u1", "s1"), _row("u1", "s2", is_known_label=False), _row("u2", "s1")]
    assert [r["sample_id"] for r in scenario_rows(rows, "E3")] == ["u1/s1", "u1/s2"]
    assert [r["sample_id"] for r in scenario_rows(rows, "E1")] == ["u2/s1"]


def test_scenario_membership() -> None:
    swap = {"normal_or_defect": "defect", "defect_type": "wrong_label"}
    rows = [
        _row("normal", "s1"),
        _row("seen", "s1", normal_or_defect="defect", defect_type="torn_label"),
        _row("unseen", "s1", normal_or_defect="defect", is_known_defect=False),
        _row("random_swap", "s1", experiment_tags=["E5-hard"], **swap),
        _row("e5_only", "s1", experiment_tags=["E5", "E5-extreme"], **swap),
        _row("e5_only", "s2", experiment_tags=["E5"]),
        _row("unknown", "s1", is_known_label=False),
        _row("boundary", "s1", experiment_tags=["GEOM-boundary"]),
        _row("confusable", "s1", experiment_tags=["OCR-confusable"], normal_or_defect="defect"),
    ]

    def units(scenario: str) -> set[str]:
        return {r["unit_id"] for r in scenario_rows(rows, scenario)}

    # 결정 2: E5 전용 unit은 E1에서 뺀다. 무작위로 생긴 바꿔치기는 E1에 남는다
    assert units("E1") == {"normal", "seen", "random_swap"}
    assert units("E3") == {"unknown"}
    assert units("E4") == {"normal", "seen", "unseen", "random_swap"}
    assert units("E5") == {"random_swap", "e5_only"}
    # 덧붙인 unit 묶음은 E1·E4에서 빠지고 따로 평가된다 (#69 T6·T7)
    assert units("GEOM-boundary") == {"boundary"}
    assert units("OCR-confusable") == {"confusable"}


def test_public_track_is_all_e1() -> None:
    """public row는 is_known_label=None, 태그 없음 → 전부 E1이고 다른 시나리오는 결과에 없다.

    E4는 본 적 없는 유형이 하나도 없으면 seen/unseen 비교가 성립하지 않으므로 뺀다.
    """
    rows = [_row("p1", "-", is_known_label=None), _row("p2", "-", is_known_label=None)]
    m = evaluate_scenarios(rows, _preds(rows, [OK, OK]))
    assert set(m) == {"E1"}
    assert m["E1"]["n"] == 2


def test_mlflow_names_carry_scenario_prefix() -> None:
    rows = [_row("u1", "s1"), _row("u2", "s1", is_known_label=False)]
    flat = flat_scenario_metrics(evaluate_scenarios(rows, _preds(rows, [OK, NG])))
    assert flat["e1_false_positive_rate_n_product"] == 1
    assert flat["e3_unknown_label_ok_rate_k"] == 0
    assert not any(k.startswith("false_positive_rate") for k in flat)


def test_subset_names_become_valid_prefixes() -> None:
    rows = [_row("b", "s1", experiment_tags=["GEOM-boundary"])]
    flat = flat_scenario_metrics(evaluate_scenarios(rows, _preds(rows, [OK])))
    assert flat["geom_boundary_review_rate_n"] == 1


def test_sealed_test_opens_only_for_final_report() -> None:
    """pilot test를 보면서 방향을 정하지 않는다 (#69 T9). 연 run은 태그로 남는다."""
    cfg = {"dataset": {"name": "pilot", "split": "test"}, "experiment": {}}
    with pytest.raises(PermissionError):
        open_test({"test_sealed": True}, cfg)
    cfg["experiment"]["final_report"] = True
    assert open_test({"test_sealed": True}, cfg) == {"test_opened": "true"}
    assert open_test({}, {"dataset": {"split": "test"}, "experiment": {}}) == {}  # pilot_dev·public
