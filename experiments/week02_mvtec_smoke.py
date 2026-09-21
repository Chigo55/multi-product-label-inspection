"""Week 1 마감 — Public dataset 하나 읽기 (#4).

모델은 돌리지 않는다. 데이터가 실제로 schema v1.0까지 흐르는지만 확인한다.

    이미지 1장 열기 → train/val/test 샘플 수 출력 → metadata.jsonl 생성

실행:
    uv run experiments/week02_mvtec_smoke.py            # bottle
    uv run experiments/week02_mvtec_smoke.py cable screw

데이터 준비: MVTec AD를 datasets/public/mvtec_ad/ 에 풀어 둔다 (CC BY-NC-SA 4.0, 비상업 전용).
결과 metadata.jsonl은 datasets/public/ 아래라 커밋되지 않는다 — 이 스크립트로 재생성한다.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
# `uv run experiments/x.py`는 sys.path[0]이 experiments/ 라서 `src`를 못 찾는다.
# pytest의 pythonpath=["."] 와 같은 규약을 스크립트에도 맞춘다.
sys.path.insert(0, str(REPO_ROOT))

from src.utils.metadata import write_jsonl  # noqa: E402
from src.utils.mvtec import build_metadata  # noqa: E402

MVTEC_ROOT = REPO_ROOT / "datasets" / "public" / "mvtec_ad"
OUT_PATH = MVTEC_ROOT / "metadata.jsonl"


def main(categories: list[str]) -> None:
    rows = [row for category in categories for row in build_metadata(MVTEC_ROOT, category)]

    with Image.open(MVTEC_ROOT / rows[0]["image_path"]) as img:
        print(f"이미지 열기: {rows[0]['image_path']}  {img.size} {img.mode}")
    print()

    for category in categories:
        mine = [r for r in rows if r["product_id"] == category]
        print(f"[{category}]")
        for split in ("train", "val", "test"):
            kinds = Counter(r["normal_or_defect"] for r in mine if r["split"] == split)
            print(f"  {split:5s}  normal={kinds['normal']:4d}  defect={kinds['defect']:4d}")
        types = Counter(r["defect_type"] for r in mine if r["defects"])
        print(f"  defect_type: {dict(sorted(types.items()))}")
    print()

    write_jsonl(rows, OUT_PATH)
    print(f"metadata: {OUT_PATH.relative_to(REPO_ROOT).as_posix()}  ({len(rows)} rows)")
    print(
        "다음: uv run experiments/week02_pipeline_check.py (datasets/registry.yaml이 이 경로를 가리킨다)"
    )


if __name__ == "__main__":
    main(sys.argv[1:] or ["bottle"])
