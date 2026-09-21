"""MVTec AD → Dataset Schema v1.0 metadata 변환기.

평가 코드는 원본 디렉터리 구조를 모르고 metadata.jsonl만 읽는다 (docs/adr/0006).
매핑 규칙은 datasets/schema.md §3 이 정본이다. 여기서 새로 정하지 않는다.

    <root>/<category>/train/good/000.png
    <root>/<category>/test/{good,<defect_type>}/000.png
    <root>/<category>/ground_truth/<defect_type>/000_mask.png   ← 샘플 아님
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

DATASET = "mvtec_ad"
NORMAL_DIR = "good"
LABEL_SLOT = "-"  # 라벨 개념이 없는 데이터셋
CAMERA_ID = "CAM01"
SPLITS = ("train", "test")  # 원본 디렉터리. MVTec AD에는 val이 없다
VAL_FRACTION = 0.2  # train 정상 중 val(calibration)로 떼는 비율 — schema §4.3 안 A


def build_metadata(root: Path, category: str) -> list[dict[str, Any]]:
    """category 하나를 schema v1.0 row 목록으로 변환한다. image_path는 root 기준 상대 경로."""
    category_dir = root / category
    if not category_dir.is_dir():
        raise FileNotFoundError(f"MVTec category 디렉터리가 없다: {category_dir}")

    rows = [
        _row(root, category, split, image)
        for split in SPLITS
        for image in sorted((category_dir / split).glob("*/*.png"))
    ]
    if not rows:
        raise ValueError(f"{category_dir} 아래에 train/test 이미지가 없다")

    bad = sorted({r["defect_type"] for r in rows if r["split"] == "train" and r["defects"]})
    if bad:
        raise ValueError(f"train split에 불량 폴더가 있다 (normal-only 전제 위반): {bad}")
    return _assign_val(rows)


def _assign_val(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """train 정상 중 VAL_FRACTION을 val로 옮긴다.

    sha256(unit_id) 순서로 고르므로 Python 버전이나 random seed와 무관하게 항상 같은 샘플이 뽑힌다.
    unit_id는 원본 디렉터리 기준이라 split이 val로 바뀌어도 그대로다.
    """
    train = sorted(
        (r for r in rows if r["split"] == "train"),
        key=lambda r: hashlib.sha256(r["unit_id"].encode()).hexdigest(),
    )
    val_ids = {r["unit_id"] for r in train[: round(len(train) * VAL_FRACTION)]}
    return [r | {"split": "val"} if r["unit_id"] in val_ids else r for r in rows]


def _row(root: Path, category: str, split: str, image: Path) -> dict[str, Any]:
    folder = image.parent.name
    is_normal = folder == NORMAL_DIR
    # MVTec은 폴더마다 000부터 다시 세므로 폴더명을 seq에 넣어야 unit_id가 고유하다
    unit_id = f"{DATASET}/{category}/{split}/{folder}_{image.stem}"
    return {
        "sample_id": f"{unit_id}/{LABEL_SLOT}",
        "unit_id": unit_id,
        "product_id": category,
        "label_slot": LABEL_SLOT,
        "camera_id": CAMERA_ID,
        "image_path": image.relative_to(root).as_posix(),
        # Recipe도 Label Identity도 없다 → Logical / Identity 지표에서 자동 제외
        "expected_label_id": None,
        "actual_label_id": None,
        "expected_text": None,
        "actual_text": None,
        "expected_barcode": None,
        "actual_barcode": None,
        "expected_position": None,
        "actual_position": None,
        "normal_or_defect": "normal" if is_normal else "defect",
        "defect_category": "none" if is_normal else "visual",
        "defect_type": None if is_normal else folder,
        # Severity는 Recipe가 정한다(docs/adr/0004). public track에는 Recipe가 없다.
        "defect_severity": "none" if is_normal else None,
        "defects": [] if is_normal else [{"type": folder, "severity": None}],
        "is_known_label": None,
        "is_known_defect": True,
        "production_lot": None,
        "revision": None,
        "split": split,
        "experiment_tags": [],
    }
