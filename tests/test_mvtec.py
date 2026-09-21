"""MVTec AD → schema v0.2 변환 테스트.

실제 데이터 없이 MVTec 디렉터리 구조를 tmp_path에 흉내 내서 돌린다.
실제 데이터 검증은 `slow` 마커가 붙은 마지막 테스트 하나뿐이다.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from src.utils.metadata import find_errors
from src.utils.mvtec import build_metadata, convert
from src.utils.paths import SHARED_ROOT

MVTEC_ROOT = SHARED_ROOT / "datasets" / "public" / "mvtec_ad"

# datasets/schema.md v0.2 §1 의 필드 전체
SCHEMA_V02_FIELDS = {
    "sample_id", "unit_id", "product_id", "label_slot", "camera_id", "image_path",
    "expected_label_id", "actual_label_id", "expected_text", "actual_text",
    "expected_barcode", "actual_barcode", "expected_position", "actual_position",
    "normal_or_defect", "defect_category", "defect_type", "defect_severity", "defects",
    "is_known_label", "is_known_defect",
    "production_lot", "revision", "split", "experiment_tags",
}  # fmt: skip


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@pytest.fixture
def fake_root(tmp_path: Path) -> Path:
    """bottle: train/good 2장, test/good 1장, test/broken_large 2장."""
    cat = tmp_path / "bottle"
    for rel in [
        "train/good/000.png",
        "train/good/001.png",
        "test/good/000.png",
        "test/broken_large/000.png",
        "test/broken_large/001.png",
        "ground_truth/broken_large/000_mask.png",
    ]:
        _touch(cat / rel)
    return tmp_path


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["sample_id"]: r for r in rows}


def test_every_row_has_exactly_schema_v02_fields(fake_root: Path) -> None:
    rows = build_metadata(fake_root, "bottle")
    assert len(rows) == 5  # ground_truth mask는 샘플이 아니다
    for row in rows:
        assert set(row) == SCHEMA_V02_FIELDS


def test_ids_are_unique_across_defect_folders(fake_root: Path) -> None:
    # MVTec은 폴더마다 000.png부터 다시 센다 → test/good/000 과 test/broken_large/000 이 충돌하면 안 된다
    rows = build_metadata(fake_root, "bottle")
    assert len({r["unit_id"] for r in rows}) == len(rows)
    assert len({r["sample_id"] for r in rows}) == len(rows)


def test_defect_row_follows_public_mapping(fake_root: Path) -> None:
    row = by_id(build_metadata(fake_root, "bottle"))["mvtec_ad/bottle/test/broken_large_001/-"]
    assert row["unit_id"] == "mvtec_ad/bottle/test/broken_large_001"
    assert row["product_id"] == "bottle"
    assert row["label_slot"] == "-"
    assert row["camera_id"] == "CAM01"
    assert row["image_path"] == "bottle/test/broken_large/001.png"
    assert row["split"] == "test"
    assert row["normal_or_defect"] == "defect"
    assert row["defect_category"] == "visual"
    assert row["defect_type"] == "broken_large"  # 원본 결함 폴더명 그대로
    # public track에는 Recipe가 없으므로 severity도 없다 (docs/adr/0004)
    assert row["defect_severity"] is None
    assert row["defects"] == [{"type": "broken_large", "severity": None}]
    assert row["is_known_defect"] is True


def test_normal_row(fake_root: Path) -> None:
    row = by_id(build_metadata(fake_root, "bottle"))["mvtec_ad/bottle/train/good_000/-"]
    assert row["split"] == "train"
    assert row["normal_or_defect"] == "normal"
    assert row["defect_category"] == "none"
    assert row["defect_type"] is None
    assert row["defect_severity"] == "none"
    assert row["defects"] == []
    assert row["is_known_defect"] is True  # 정상은 Known으로 인코딩 (CONTEXT.md)


def test_label_identity_and_expected_fields_are_null(fake_root: Path) -> None:
    # 이 조건이 참이어야 평가에서 Logical / Identity 지표가 자동 제외된다
    for row in build_metadata(fake_root, "bottle"):
        assert row["defect_category"] != "logical"
        assert row["is_known_label"] is None
        for key in SCHEMA_V02_FIELDS:
            if key.startswith(("expected_", "actual_")):
                assert row[key] is None, key


def test_val_is_deterministic_20_percent_of_train(tmp_path: Path) -> None:
    # schema §4.3 안 A: train 정상에서 unit 단위로 20%를 val로 뗀다
    for i in range(10):
        _touch(tmp_path / "bottle" / "train" / "good" / f"{i:03d}.png")
    _touch(tmp_path / "bottle" / "test" / "good" / "000.png")
    val = [r for r in build_metadata(tmp_path, "bottle") if r["split"] == "val"]
    assert len(val) == 2
    assert all(r["normal_or_defect"] == "normal" for r in val)
    # unit_id는 원본 폴더 기준이다 — split 정책이 바뀌어도 ID는 바뀌지 않는다
    assert all("/train/good_" in r["unit_id"] for r in val)
    again = [r for r in build_metadata(tmp_path, "bottle") if r["split"] == "val"]
    assert again == val


def test_loco_uses_official_validation_and_logical_category(tmp_path: Path) -> None:
    # MVTec LOCO: validation 디렉터리가 있으므로 train을 떼지 않는다. logical_anomalies → logical
    for rel in [
        "train/good/000.png",
        "train/good/001.png",
        "train/good/002.png",
        "train/good/003.png",
        "train/good/004.png",
        "validation/good/000.png",
        "test/good/000.png",
        "test/logical_anomalies/000.png",
        "test/structural_anomalies/000.png",
        "ground_truth/logical_anomalies/000/000.png",
    ]:
        _touch(tmp_path / "juice_bottle" / rel)
    rows = by_id(build_metadata(tmp_path, "juice_bottle", dataset="mvtec_loco"))
    assert len(rows) == 9
    assert [r["split"] for r in rows.values()].count("val") == 1
    val = rows["mvtec_loco/juice_bottle/validation/good_000/-"]
    assert val["split"] == "val"
    logical = rows["mvtec_loco/juice_bottle/test/logical_anomalies_000/-"]
    assert (logical["defect_category"], logical["defect_type"]) == ("logical", "logical_anomalies")
    structural = rows["mvtec_loco/juice_bottle/test/structural_anomalies_000/-"]
    assert structural["defect_category"] == "visual"  # 정본 용어는 visual (CONTEXT.md)
    assert find_errors(list(rows.values()), image_root=tmp_path) == []


def test_rejects_defect_folder_in_train(fake_root: Path) -> None:
    # normal-only 학습 전제가 깨지는 데이터는 조용히 변환하지 않는다
    _touch(fake_root / "bottle" / "train" / "broken_large" / "000.png")
    with pytest.raises(ValueError, match="train"):
        build_metadata(fake_root, "bottle")


def test_missing_category_raises(fake_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_metadata(fake_root, "cable")


@pytest.mark.slow
@pytest.mark.skipif(not (MVTEC_ROOT / "bottle").is_dir(), reason="MVTec AD 미다운로드")
def test_real_bottle_counts() -> None:
    # MVTec AD 논문(IJCV 2021) Table 1: bottle train 209 / test good 20 / test defect 63
    # train 209 중 20%(42)를 val로 뗀다 (schema §4.3)
    rows = build_metadata(MVTEC_ROOT, "bottle")
    count = {
        (split, kind): sum(r["split"] == split and r["normal_or_defect"] == kind for r in rows)
        for split in ("train", "val", "test")
        for kind in ("normal", "defect")
    }
    assert count == {
        ("train", "normal"): 167,
        ("train", "defect"): 0,
        ("val", "normal"): 42,
        ("val", "defect"): 0,
        ("test", "normal"): 20,
        ("test", "defect"): 63,
    }
    assert all((MVTEC_ROOT / r["image_path"]).is_file() for r in rows)


LOCO_ROOT = SHARED_ROOT / "datasets" / "public" / "mvtec_loco"


@pytest.mark.slow
@pytest.mark.skipif(not (LOCO_ROOT / "juice_bottle").is_dir(), reason="MVTec LOCO 미다운로드")
def test_real_loco_counts() -> None:
    # 배포본(sha256 9e7c84db…) 기준. 논문 표기(3,644장)와 7장 차이 — 원본 파일 수와는 일치한다
    rows = convert(LOCO_ROOT, "mvtec_loco")
    splits = Counter(r["split"] for r in rows)
    assert (splits["train"], splits["val"], splits["test"]) == (1778, 305, 1568)
    assert Counter(r["defect_category"] for r in rows if r["defects"]) == {
        "logical": 561,
        "visual": 432,
    }
    assert find_errors(rows, image_root=LOCO_ROOT) == []
