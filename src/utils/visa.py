"""VisA → Dataset Schema v1.0 metadata 변환기. 매핑 규칙은 datasets/schema.md §3.

<root>/split_csv/1cls.csv                  ← 공식 1-class split (object, split, label, image, mask)
<root>/<object>/image_anno.csv             ← 불량 설명. 한 칸에 쉼표로 복수 불량
<root>/<object>/Data/Images/{Normal,Anomaly}/*.JPG
"""

from __future__ import annotations

import csv
from pathlib import Path, PurePosixPath
from typing import Any

from src.utils.metadata import assign_val, public_row

DATASET = "visa"
SPLIT_CSV = Path("split_csv") / "1cls.csv"
LABELS = {"normal", "anomaly"}
SPLITS = {"train", "test"}


def convert(root: Path) -> list[dict[str, Any]]:
    """공식 1cls split 전체를 변환한다. val은 train 정상에서 뗀다 (schema §4.3)."""
    split_rows = _read_csv(root / SPLIT_CSV)
    objects = sorted({r["object"] for r in split_rows})
    description = {
        a["image"]: a["label"] for obj in objects for a in _read_csv(root / obj / "image_anno.csv")
    }
    rows = [_row(r, description) for r in split_rows]
    if bad := [r["image_path"] for r in rows if r["split"] == "train" and r["defects"]]:
        raise ValueError(f"train split에 불량이 있다 (normal-only 전제 위반): {bad[:5]}")
    return assign_val(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _row(r: dict[str, str], description: dict[str, str]) -> dict[str, Any]:
    if r["label"] not in LABELS or r["split"] not in SPLITS:
        raise ValueError(f"알 수 없는 label/split: {r}")
    image = PurePosixPath(r["image"])
    types: list[str] = []
    if r["label"] == "anomaly":
        text = description.get(r["image"], "normal")
        if text == "normal":
            raise ValueError(f"불량 설명이 없다 (image_anno.csv): {r['image']}")
        types = [t.strip() for t in text.split(",")]
    return public_row(
        unit_id=f"{DATASET}/{r['object']}/{r['split']}/{image.parent.name}_{image.stem}",
        product_id=r["object"],
        image_path=r["image"],
        split=r["split"],
        defect_types=types,
        defect_category="visual",
    )
