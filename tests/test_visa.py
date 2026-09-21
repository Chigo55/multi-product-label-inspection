"""VisA → schema v1.0 변환 테스트. 실제 데이터 검증은 slow 마커 테스트 하나뿐이다."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.metadata import find_errors
from src.utils.paths import SHARED_ROOT
from src.utils.visa import convert

VISA_ROOT = SHARED_ROOT / "datasets" / "public" / "visa"


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def fake_root(tmp_path: Path) -> Path:
    images = [f"candle/Data/Images/Normal/{i:04d}.JPG" for i in range(10)]
    images += ["candle/Data/Images/Anomaly/000.JPG", "candle/Data/Images/Anomaly/001.JPG"]
    for image in images:
        _write(tmp_path / image)
    _write(
        tmp_path / "split_csv" / "1cls.csv",
        "object,split,label,image,mask\n"
        + "".join(f"candle,train,normal,{i},\n" for i in images[:8])
        + f"candle,test,normal,{images[8]},\n"
        + f"candle,test,normal,{images[9]},\n"
        + f"candle,test,anomaly,{images[10]},candle/Data/Masks/Anomaly/000.png\n"
        + f"candle,test,anomaly,{images[11]},candle/Data/Masks/Anomaly/001.png\n",
    )
    _write(
        tmp_path / "candle" / "image_anno.csv",
        "image,label,mask\n"
        + "".join(f"{i},normal,\n" for i in images[:10])
        + f"{images[10]},chunk of wax missing,candle/Data/Masks/Anomaly/000.png\n"
        + f'{images[11]},"weird candle wick,different colour spot",candle/Data/Masks/Anomaly/001.png\n',
    )
    return tmp_path


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["sample_id"]: r for r in rows}


def test_rows_are_valid_and_follow_official_split(fake_root: Path) -> None:
    rows = convert(fake_root)
    assert find_errors(rows, image_root=fake_root) == []
    splits = [r["split"] for r in rows]
    # 공식 1cls split의 train 8장 중 20%(2장)를 val로 뗀다 (schema §4.3)
    assert (splits.count("train"), splits.count("val"), splits.count("test")) == (6, 2, 4)


def test_defect_types_come_from_image_anno(fake_root: Path) -> None:
    rows = by_id(convert(fake_root))
    one = rows["visa/candle/test/Anomaly_000/-"]
    assert one["image_path"] == "candle/Data/Images/Anomaly/000.JPG"
    assert (one["defect_category"], one["defect_type"]) == ("visual", "chunk of wax missing")
    # 쉼표로 이어진 복수 불량 → defects[] 원소 여러 개, 대표값은 첫 번째
    two = rows["visa/candle/test/Anomaly_001/-"]
    assert [d["type"] for d in two["defects"]] == ["weird candle wick", "different colour spot"]
    assert two["defect_type"] == "weird candle wick"


def test_anomaly_in_train_is_rejected(fake_root: Path) -> None:
    csv_path = fake_root / "split_csv" / "1cls.csv"
    text = csv_path.read_text(encoding="utf-8").replace(
        "candle,test,anomaly", "candle,train,anomaly", 1
    )
    csv_path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="train"):
        convert(fake_root)


def test_anomaly_without_description_is_rejected(fake_root: Path) -> None:
    anno = fake_root / "candle" / "image_anno.csv"
    lines = anno.read_text(encoding="utf-8").splitlines()
    anno.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Anomaly/001"):
        convert(fake_root)


@pytest.mark.slow
@pytest.mark.skipif(not (VISA_ROOT / "split_csv").is_dir(), reason="VisA 미다운로드")
def test_real_visa_counts() -> None:
    # VisA 논문(ECCV 2022) Table: 10,821장 = 정상 9,621 + 불량 1,200, 12 objects
    rows = convert(VISA_ROOT)
    assert len(rows) == 10821
    assert sum(r["normal_or_defect"] == "defect" for r in rows) == 1200
    assert len({r["product_id"] for r in rows}) == 12
    assert find_errors(rows, image_root=VISA_ROOT) == []
