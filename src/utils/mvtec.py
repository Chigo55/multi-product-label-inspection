"""MVTec AD / MVTec LOCO AD → Dataset Schema v1.0 metadata 변환기.

평가 코드는 원본 디렉터리 구조를 모르고 metadata.jsonl만 읽는다 (docs/adr/0006).
매핑 규칙은 datasets/schema.md §3 이 정본이다. 여기서 새로 정하지 않는다.

    <root>/<category>/train/good/000.png
    <root>/<category>/validation/good/000.png                     ← LOCO만
    <root>/<category>/test/{good,<defect_folder>}/000.png
    <root>/<category>/ground_truth/...                            ← 샘플 아님
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.metadata import assign_val, public_row

# 원본 split 디렉터리 → schema split. val이 없으면 train 정상에서 뗀다 (schema §4.3)
SPLIT_DIRS = {
    "mvtec_ad": {"train": "train", "test": "test"},
    "mvtec_loco": {"train": "train", "validation": "val", "test": "test"},
}
NORMAL_DIR = "good"
LOGICAL_DIR = "logical_anomalies"  # LOCO. 나머지 불량 폴더는 전부 visual (schema §3)


def convert(root: Path, dataset: str) -> list[dict[str, Any]]:
    """root 아래 모든 category를 변환한다."""
    categories = sorted(p.name for p in root.iterdir() if p.is_dir())
    return [row for c in categories for row in build_metadata(root, c, dataset)]


def build_metadata(root: Path, category: str, dataset: str = "mvtec_ad") -> list[dict[str, Any]]:
    """category 하나를 schema row 목록으로 변환한다. image_path는 root 기준 상대 경로."""
    category_dir = root / category
    if not category_dir.is_dir():
        raise FileNotFoundError(f"MVTec category 디렉터리가 없다: {category_dir}")

    split_dirs = SPLIT_DIRS[dataset]
    rows = [
        _row(root, dataset, category, source, split, image)
        for source, split in split_dirs.items()
        for image in sorted((category_dir / source).glob("*/*.png"))
    ]
    if not rows:
        raise ValueError(f"{category_dir} 아래에 이미지가 없다")

    bad = sorted({r["defect_type"] for r in rows if r["split"] != "test" and r["defects"]})
    if bad:
        raise ValueError(f"train/validation에 불량 폴더가 있다 (normal-only 전제 위반): {bad}")
    return rows if "val" in split_dirs.values() else assign_val(rows)


def _row(root: Path, dataset: str, category: str, source: str, split: str, image: Path) -> dict:
    folder = image.parent.name
    return public_row(
        # 폴더마다 000부터 다시 세므로 폴더명을 넣어야 고유하다. source는 원본 디렉터리라 split과 무관하게 고정
        unit_id=f"{dataset}/{category}/{source}/{folder}_{image.stem}",
        product_id=category,
        image_path=image.relative_to(root).as_posix(),
        split=split,
        defect_types=[] if folder == NORMAL_DIR else [folder],
        defect_category="logical" if folder == LOGICAL_DIR else "visual",
    )
