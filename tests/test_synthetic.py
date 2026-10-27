"""Synthetic defect 생성 테스트 (#34).

불량 사진은 눈으로 봐도 metadata가 맞는지 알 수 없다. 그래서 유형마다 **어떤 필드가 어떻게
달라져야 하는지**를 고정한다. 이게 깨지면 logical defect의 "정확한 ground truth"라는 이점이 사라진다.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.utils.synthetic import (
    CONFUSABLE,
    DEFAULT_SEVERITY,
    VISUAL_TYPES,
    Mutation,
    _change_confusable,
    _change_one_char,
    severity,
)

Small = tuple[dict[str, Any], list[dict[str, Any]], Path]
TAXONOMY = Path(__file__).resolve().parents[1] / "datasets" / "defect_taxonomy.md"
# taxonomy 표의 한 행: | `type` | 설명 | 기본 Severity |  (머리글 행은 severity 칸이 없어 걸리지 않는다)
SEVERITY_ROW = r"^\| `(\w+)` \| .+? \| (CRITICAL|MAJOR|MINOR) \|$"
# taxonomy 표의 한 행: | `type` | 설명 | 기본 Severity |
SEVERITY_ROW = r"^\| `(\w+)` \| .+? \| (CRITICAL|MAJOR|MINOR) \|$"


def _defects(rows: list[dict[str, Any]], defect_type: str) -> list[dict[str, Any]]:
    found = [r for r in rows if r["defect_type"] == defect_type]
    assert found, f"{defect_type} row가 생성되지 않았다"
    return found


def _owner(recipe: dict[str, Any]) -> dict[str, str]:
    return {
        i: p
        for p, v in recipe["products"].items()
        for s in v["revisions"].values()
        for i in s.values()
    }


def _within(r: dict[str, Any], tol: dict[str, float]) -> tuple[bool, bool]:
    """(위치가 허용 오차 안인가, 각도가 허용 오차 안인가)"""
    e, a = r["expected_position"], r["actual_position"]
    xy = abs(a["x"] - e["x"]) <= tol["xy_mm"] and abs(a["y"] - e["y"]) <= tol["xy_mm"]
    return xy, abs(a["theta"] - e["theta"]) <= tol["theta_deg"]


def _diff_chars(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b, strict=True))


# ------------------------------------------------------------
# taxonomy와 코드가 같은가
# ------------------------------------------------------------
def test_default_severity_matches_taxonomy() -> None:
    """defect_taxonomy.md가 enum의 유일한 정의다. 코드의 표는 그 사본이라 어긋나면 안 된다."""
    rows = re.findall(SEVERITY_ROW, TAXONOMY.read_text(encoding="utf-8"), re.M)
    assert dict(rows) == DEFAULT_SEVERITY


def test_visual_types_are_the_visual_section() -> None:
    text = TAXONOMY.read_text(encoding="utf-8")
    visual = text[text.index("## 1. VISUAL") : text.index("## 2. LOGICAL")]
    assert {t for t, _ in re.findall(SEVERITY_ROW, visual, re.M)} == VISUAL_TYPES


# ------------------------------------------------------------
# 배치
# ------------------------------------------------------------
def test_every_configured_type_is_generated(pilot_small: Small) -> None:
    recipe, rows, _ = pilot_small
    made = {r["defect_type"] for r in rows if r["split"] == "test" and r["defect_type"]}
    assert made == set(recipe["build"]["defects"]["types"]) | {"revision_mismatch"}  # v0.4 블록


def test_no_defects_in_train_or_reference(pilot_small: Small) -> None:
    _, rows, _ = pilot_small
    assert not [
        r
        for r in rows
        if r["split"] in ("train", "reference") and r["normal_or_defect"] == "defect"
    ]


def test_exactly_one_defective_slot_per_defect_unit(pilot_small: Small) -> None:
    """불량 unit은 한 자리만 불량이다 — 그래야 Label-level과 Product-level 결과를 1:1로 대조할 수 있다."""
    _, rows, _ = pilot_small
    per_unit = Counter(r["unit_id"] for r in rows if r["normal_or_defect"] == "defect")
    assert per_unit and set(per_unit.values()) == {1}


def test_holdout_is_unknown_and_test_only(pilot_small: Small) -> None:
    """E4: hold-out 유형은 calibration에서 본 적이 없어야 한다 (schema §4.2-4)."""
    recipe, rows, _ = pilot_small
    holdout = set(recipe["build"]["defects"]["holdout"])
    for r in rows:
        if r["defect_type"] in holdout:
            assert r["split"] == "test" and r["is_known_defect"] is False
        else:
            assert r["is_known_defect"] is True
    val_types = {r["defect_type"] for r in rows if r["split"] == "val" and r["defect_type"]}
    assert val_types and not (val_types & holdout)


def test_defect_units_never_carry_unknown_labels(pilot_small: Small) -> None:
    """E3와 불량이 한 unit에 겹치면 둘 중 무엇 때문에 판정이 났는지 알 수 없다."""
    _, rows, _ = pilot_small
    defect_units = {r["unit_id"] for r in rows if r["normal_or_defect"] == "defect"}
    assert not [r for r in rows if r["unit_id"] in defect_units and r["is_known_label"] is False]


# ------------------------------------------------------------
# 유형별로 달라져야 하는 필드
# ------------------------------------------------------------
def test_wrong_label_comes_from_same_product(pilot_small: Small) -> None:
    recipe, rows, _ = pilot_small
    owner = _owner(recipe)
    for r in _defects(rows, "wrong_label"):
        assert r["actual_label_id"] != r["expected_label_id"]
        assert owner[r["actual_label_id"]] == r["product_id"]


def test_wrong_product_label_comes_from_other_product(pilot_small: Small) -> None:
    recipe, rows, _ = pilot_small
    owner = _owner(recipe)
    for r in _defects(rows, "wrong_product_label"):
        assert owner[r["actual_label_id"]] != r["product_id"]


def test_ocr_mismatch_changes_one_character_of_one_field(pilot_small: Small) -> None:
    _, rows, _ = pilot_small
    for r in _defects(rows, "ocr_mismatch"):
        assert r["actual_label_id"] == r["expected_label_id"]
        assert r["actual_barcode"] == r["expected_barcode"]
        changed = [k for k in r["expected_text"] if r["expected_text"][k] != r["actual_text"][k]]
        assert len(changed) == 1
        assert _diff_chars(r["expected_text"][changed[0]], r["actual_text"][changed[0]]) == 1


def test_barcode_mismatch_keeps_printed_text(pilot_small: Small) -> None:
    """인쇄 문자는 그대로라 OCR로는 못 잡는다. 바코드를 읽어야만 잡힌다."""
    _, rows, _ = pilot_small
    for r in _defects(rows, "barcode_mismatch"):
        assert r["actual_text"] == r["expected_text"]
        assert _diff_chars(r["expected_barcode"]["value"], r["actual_barcode"]["value"]) == 1


def test_position_and_orientation_break_only_their_own_axis(pilot_small: Small) -> None:
    recipe, rows, _ = pilot_small
    tol = {p: v["tolerance"] for p, v in recipe["products"].items()}
    for r in _defects(rows, "wrong_position"):
        assert _within(r, tol[r["product_id"]]) == (False, True)
    for r in _defects(rows, "wrong_orientation"):
        assert _within(r, tol[r["product_id"]]) == (True, False)


def test_missing_label_has_no_actual(pilot_small: Small) -> None:
    _, rows, _ = pilot_small
    for r in _defects(rows, "missing_label"):
        assert r["actual_label_id"] is None
        assert (
            r["actual_text"] is None
            and r["actual_barcode"] is None
            and r["actual_position"] is None
        )


@pytest.mark.parametrize("defect_type", ["contamination", "blur", "unknown_visual"])
def test_visual_defect_keeps_logical_fields(pilot_small: Small, defect_type: str) -> None:
    """외관 불량은 라벨 내용·위치가 정상이다. logical 축에서는 아무것도 틀리지 않았다."""
    recipe, rows, _ = pilot_small
    tol = {p: v["tolerance"] for p, v in recipe["products"].items()}
    for r in _defects(rows, defect_type):
        assert r["defect_category"] == "visual"
        assert r["actual_label_id"] == r["expected_label_id"]
        assert r["actual_text"] == r["expected_text"]
        assert _within(r, tol[r["product_id"]]) == (True, True)


# ------------------------------------------------------------
# Severity override (defect_taxonomy §3, ADR 0004)
# ------------------------------------------------------------
def _m(defect_type: str, ocr_field: str | None = None) -> Mutation:
    return Mutation(defect_type, "x", None, (0.0, 0.0), 0.0, ocr_field=ocr_field)


def test_severity_default_and_overrides(pilot_small: Small) -> None:
    overrides = pilot_small[0]["severity_overrides"]
    assert severity(overrides, "A", "slot-1", _m("contamination")) == "MINOR"  # 기본값
    assert severity(overrides, "B", "slot-1", _m("contamination")) == "MAJOR"  # 제품·자리 override
    assert severity(overrides, "A", "slot-3", _m("blur")) == "CRITICAL"
    # OCR은 field 단위까지 — 같은 라벨이라도 field에 따라 다르다
    assert severity(overrides, "C", "slot-2", _m("ocr_mismatch", "STORAGE")) == "MINOR"
    assert severity(overrides, "C", "slot-2", _m("ocr_mismatch", "EXP")) == "CRITICAL"


def test_metadata_records_final_severity(pilot_small: Small) -> None:
    """metadata에는 taxonomy 기본값이 아니라 override가 적용된 최종값이 들어간다."""
    _, rows, _ = pilot_small
    blurred_tags = [r for r in _defects(rows, "blur") if r["label_slot"] == "slot-3"]
    others = [r for r in _defects(rows, "blur") if r["label_slot"] != "slot-3"]
    assert {r["defect_severity"] for r in blurred_tags} <= {"CRITICAL"}
    assert {r["defect_severity"] for r in others} <= {"MAJOR"}


def test_confusable_change_swaps_digit_and_letter() -> None:
    """0/O, 1/I 같은 실제 OCR 혼동 쌍 (#69 T7). 그런 글자가 없으면 None."""
    rng = np.random.default_rng(0)
    for text in ("XA-100", "P-4471", "B-SERIES"):
        for _ in range(20):
            new = _change_confusable(text, rng)
            assert new is not None and _diff_chars(text, new) == 1
            i = next(k for k in range(len(text)) if text[k] != new[k])
            assert {text[i], new[i]} in (
                {"0", "O"},
                {"1", "I"},
                {"5", "S"},
                {"8", "B"},
                {"2", "Z"},
                {"6", "G"},
            )
    assert _change_confusable("ACE", rng) is None


def test_ocr_confusable_rows_are_tagged(pilot_small: Small) -> None:
    _, rows, _ = pilot_small
    found = [r for r in rows if "OCR-confusable" in r["experiment_tags"] and r["defect_type"]]
    assert found
    for r in found:
        assert r["defect_type"] == "ocr_mismatch" and r["split"] == "test"
        k = next(k for k in r["expected_text"] if r["expected_text"][k] != r["actual_text"][k])
        a, b = r["expected_text"][k], r["actual_text"][k]
        i = next(j for j in range(len(a)) if a[j] != b[j])
        assert CONFUSABLE[a[i]] == b[i]


def test_geom_boundary_truth_follows_actual_offset(pilot_small: Small) -> None:
    """경계 unit(0.9~1.2배)은 실제 값이 허용 오차 이하면 정상, 넘으면 불량이다 (#69 T6)."""
    recipe, rows, _ = pilot_small
    tol = {p: v["tolerance"] for p, v in recipe["products"].items()}
    found = [r for r in rows if "GEOM-boundary" in r["experiment_tags"]]
    assert found and {r["split"] for r in found} == {"test"}
    for r in found:
        inside = _within(r, tol[r["product_id"]]) == (True, True)
        assert inside == (r["normal_or_defect"] == "normal"), r["sample_id"]
        assert r["defect_type"] in (None, "wrong_position", "wrong_orientation")


def test_change_one_char_keeps_character_class() -> None:
    rng = np.random.default_rng(0)
    for text in ("XA-100", "2027-04-30", "120 g", "BX2007"):
        for _ in range(50):
            new = _change_one_char(text, rng)
            assert _diff_chars(text, new) == 1
            i = next(k for k in range(len(text)) if text[k] != new[k])
            assert text[i].isdigit() == new[i].isdigit()
            assert text[i].islower() == new[i].islower()
