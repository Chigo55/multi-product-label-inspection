"""metadata 검증기 + JSONL 입출력 테스트. 규칙의 정본은 datasets/schema.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.utils.metadata import FIELDS, assign_val, find_errors, read_jsonl, write_jsonl
from src.utils.mvtec import build_metadata


def normal(**overrides: Any) -> dict[str, Any]:
    row = dict.fromkeys(FIELDS)
    row |= {
        "sample_id": "d/p/test/1/-",
        "unit_id": "d/p/test/1",
        "product_id": "p",
        "label_slot": "-",
        "camera_id": "CAM01",
        "image_path": "p/1.png",
        "normal_or_defect": "normal",
        "defect_category": "none",
        "defect_severity": "none",
        "defects": [],
        "is_known_defect": True,
        "split": "test",
        "experiment_tags": [],
    }
    return row | overrides


def defect(**overrides: Any) -> dict[str, Any]:
    return (
        normal(
            sample_id="d/p/test/2/-",
            unit_id="d/p/test/2",
            normal_or_defect="defect",
            defect_category="visual",
            defect_type="tear",
            defect_severity="MAJOR",
            defects=[{"type": "tear", "severity": "MAJOR"}],
        )
        | overrides
    )


def test_valid_rows_have_no_errors() -> None:
    assert find_errors([normal(), defect()]) == []


def test_mvtec_rows_are_valid(tmp_path: Path) -> None:
    for rel in ["train/good/000.png", "test/good/000.png", "test/crack/000.png"]:
        (tmp_path / "bottle" / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "bottle" / rel).write_bytes(b"")
    assert find_errors(build_metadata(tmp_path, "bottle"), image_root=tmp_path) == []


@pytest.mark.parametrize(
    ("row", "fragment"),
    [
        (normal(defect_type="scratch"), "normal"),  # 정상인데 불량 유형
        (normal(defects=[{"type": "tear", "severity": "MAJOR"}]), "normal"),
        (normal(defect_category="visual"), "normal"),
        (normal(is_known_defect=False), "is_known_defect"),
        (defect(defects=[]), "defects"),
        (defect(defect_category="none"), "defect_category"),
        (defect(defect_type="scratch"), "defect_type"),  # defects[]와 대표값 불일치
        (defect(defect_severity="MINOR"), "defect_severity"),
        (defect(defects=[{"type": "tear", "severity": "HIGH"}]), "severity"),
        (normal(split="training"), "split"),
        (normal(normal_or_defect="ok"), "normal_or_defect"),
        (defect(split="reference"), "reference"),
    ],
)
def test_contradictions_are_reported(row: dict[str, Any], fragment: str) -> None:
    errors = find_errors([row])
    assert errors, row
    assert any(fragment in e for e in errors), errors


def test_representative_is_highest_severity() -> None:
    row = defect(
        defect_type="wrong_label",
        defect_severity="CRITICAL",
        defect_category="logical",
        defects=[
            {"type": "tear", "severity": "MAJOR"},
            {"type": "wrong_label", "severity": "CRITICAL"},
        ],
    )
    assert find_errors([row]) == []


def test_missing_and_extra_fields() -> None:
    row = normal()
    del row["camera_id"]
    row["label_id"] = "a-1"  # v0.2에서 폐기된 필드
    errors = find_errors([row])
    assert any("camera_id" in e for e in errors)
    assert any("label_id" in e for e in errors)


def test_duplicate_sample_id() -> None:
    assert any("중복" in e for e in find_errors([normal(), normal()]))


@pytest.mark.parametrize("other", ["train", "val", "reference"])
def test_unit_belongs_to_one_split(other: str) -> None:
    # schema §4.2-1: 같은 제품의 다른 라벨·카메라도 split을 나눌 수 없다
    a = normal(sample_id="u1/slot-1", unit_id="u1", split=other)
    b = normal(sample_id="u1/slot-2", unit_id="u1", split="test")
    assert any("leakage" in e and "u1" in e for e in find_errors([a, b]))


def test_same_unit_same_split_is_fine() -> None:
    a = normal(sample_id="u1/slot-1", unit_id="u1")
    b = normal(sample_id="u1/slot-2", unit_id="u1")
    assert find_errors([a, b]) == []


@pytest.mark.parametrize("other", ["train", "val", "reference"])
def test_test_lot_is_disjoint_from_other_splits(other: str) -> None:
    # schema §4.2-2: 과거 LOT으로 학습·조정·등록하고 미래 LOT을 검사한다
    a = normal(sample_id="u1/-", unit_id="u1", split=other, production_lot="L1")
    b = normal(sample_id="u2/-", unit_id="u2", split="test", production_lot="L1")
    assert any("LOT" in e and "L1" in e for e in find_errors([a, b]))


def test_lot_rule_ignores_null_and_non_test_overlap() -> None:
    rows = [
        normal(sample_id="u1/-", unit_id="u1", split="train", production_lot="L1"),
        normal(sample_id="u2/-", unit_id="u2", split="val", production_lot="L1"),
        normal(sample_id="u3/-", unit_id="u3", split="train"),
        normal(sample_id="u4/-", unit_id="u4", split="test"),  # public track: LOT null
    ]
    assert find_errors(rows) == []


@pytest.mark.parametrize("split", ["train", "val", "reference"])
def test_unknown_label_only_in_test(split: str) -> None:
    assert any(
        "is_known_label" in e for e in find_errors([normal(split=split, is_known_label=False)])
    )


@pytest.mark.parametrize("split", ["train", "val"])
def test_unknown_defect_only_in_test(split: str) -> None:
    assert any(
        "is_known_defect" in e for e in find_errors([defect(split=split, is_known_defect=False)])
    )


@pytest.mark.parametrize("split", ["train", "val", "reference"])
def test_unknown_visual_only_in_test(split: str) -> None:
    row = defect(
        split=split,
        defect_type="unknown_visual",
        defects=[{"type": "unknown_visual", "severity": "MAJOR"}],
    )
    assert any("unknown_visual" in e for e in find_errors([row]))


def test_missing_image_file(tmp_path: Path) -> None:
    assert any("파일" in e for e in find_errors([normal()], image_root=tmp_path))


def test_jsonl_round_trip(tmp_path: Path) -> None:
    rows = [normal(), defect()]
    path = tmp_path / "out" / "metadata.jsonl"
    write_jsonl(rows, path)
    assert read_jsonl(path) == rows


def test_assign_val_takes_fraction_per_product() -> None:
    # threshold는 제품별로 정하므로 val도 제품마다 20%여야 한다 (전체에서 20%가 아니라)
    rows = [
        normal(sample_id=f"{p}/{i}/-", unit_id=f"{p}/{i}", product_id=p, split="train")
        for p, n in (("a", 3), ("b", 3), ("c", 30))
        for i in range(n)
    ]
    val = [r for r in assign_val(rows, 0.2) if r["split"] == "val"]
    # 제품별: round(0.6)=1, round(0.6)=1, round(6)=6 → 8. 전체에서 뽑으면 round(7.2)=7
    assert [sum(r["product_id"] == p for r in val) for p in "abc"] == [1, 1, 6]
