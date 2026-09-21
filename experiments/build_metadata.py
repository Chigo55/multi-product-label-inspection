"""public 데이터셋 원본 → metadata.jsonl (schema v1.0).

    uv run experiments/build_metadata.py mvtec_ad
    uv run experiments/build_metadata.py mvtec_loco visa

datasets/registry.yaml 의 root 아래 원본 전체를 변환하고, **검증기 오류가 0건일 때만** metadata 경로에 쓴다.
metadata.jsonl은 datasets/public/ 아래라 커밋되지 않는다 — 이 스크립트로 재생성한다.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
# `uv run experiments/x.py`에서 `src` import (pytest의 pythonpath=["."]와 같은 규약)
sys.path.insert(0, str(REPO_ROOT))

from src.utils import mvtec, visa  # noqa: E402
from src.utils.metadata import find_errors, write_jsonl  # noqa: E402
from src.utils.paths import SHARED_ROOT  # noqa: E402

REGISTRY_PATH = REPO_ROOT / "datasets" / "registry.yaml"
CONVERTERS = {
    "mvtec_ad": lambda root: mvtec.convert(root, "mvtec_ad"),
    "mvtec_loco": lambda root: mvtec.convert(root, "mvtec_loco"),
    "visa": visa.convert,
}


def build(name: str, entry: dict) -> None:
    root = SHARED_ROOT / entry["root"]
    rows = CONVERTERS[name](root)
    if errors := find_errors(rows, image_root=root):
        raise ValueError(
            f"{name}: 검증 실패 {len(errors)}건 — metadata를 쓰지 않는다: {errors[:5]}"
        )
    out = SHARED_ROOT / entry["metadata"]
    write_jsonl(rows, out)

    print(
        f"[{name} v{entry['version']}] {len(rows)} rows → {out.relative_to(SHARED_ROOT).as_posix()}"
    )
    counts = Counter((r["product_id"], r["split"], r["normal_or_defect"]) for r in rows)
    for product in sorted({r["product_id"] for r in rows}):
        c = {k[1:]: v for k, v in counts.items() if k[0] == product}
        print(
            f"  {product:20s} train {c.get(('train', 'normal'), 0):4d} | val {c.get(('val', 'normal'), 0):4d}"
            f" | test normal {c.get(('test', 'normal'), 0):4d} + defect {c.get(('test', 'defect'), 0):4d}"
        )
    categories = Counter(r["defect_category"] for r in rows if r["defects"])
    print(f"  defect_category: {dict(sorted(categories.items()))}")


def main(names: list[str]) -> None:
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    for name in names:
        build(name, registry[name])


if __name__ == "__main__":
    main(sys.argv[1:] or ["mvtec_ad"])
