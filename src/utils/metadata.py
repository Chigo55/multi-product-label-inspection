"""metadata.jsonl 입출력과 검증. 규칙의 정본은 datasets/schema.md (v0.2.1).

평가 코드는 원본 데이터셋을 모르고 이 파일만 읽는다 (docs/adr/0006).
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# schema.md §1 순서
FIELDS = (
    "sample_id", "unit_id", "product_id", "label_slot", "camera_id", "image_path",
    "expected_label_id", "actual_label_id", "expected_text", "actual_text",
    "expected_barcode", "actual_barcode", "expected_position", "actual_position",
    "normal_or_defect", "defect_category", "defect_type", "defect_severity", "defects",
    "is_known_label", "is_known_defect",
    "production_lot", "revision", "split", "experiment_tags",
)  # fmt: skip
SPLITS = {"train", "val", "test", "reference"}
SEVERITY_RANK = {"CRITICAL": 3, "MAJOR": 2, "MINOR": 1}  # null = Recipe 없음 (schema §3.1)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def find_errors(rows: list[dict[str, Any]], image_root: Path | None = None) -> list[str]:
    """schema 위반을 전부 모아서 돌려준다. 빈 리스트면 통과."""
    errors = [f"{r.get('sample_id')}: {e}" for r in rows for e in _row_errors(r, image_root)]

    seen: set[str] = set()
    for r in rows:
        if r.get("sample_id") in seen:
            errors.append(f"{r.get('sample_id')}: sample_id 중복")
        seen.add(r.get("sample_id"))

    # schema §4: 같은 Product Unit이 reference와 test에 동시에 있으면 안 된다
    units = defaultdict(set)
    for r in rows:
        units[r.get("split")].add(r.get("unit_id"))
    errors += [f"{u}: reference/test leakage" for u in sorted(units["reference"] & units["test"])]
    return errors


def _row_errors(r: dict[str, Any], image_root: Path | None) -> list[str]:
    errors = []
    if missing := [k for k in FIELDS if k not in r]:
        errors.append(f"필드 누락 {missing}")
    if extra := sorted(set(r) - set(FIELDS)):
        errors.append(f"정의되지 않은 필드 {extra}")
    if r.get("split") not in SPLITS:
        errors.append(f"split={r.get('split')!r}")

    defects = r.get("defects") or []
    types = [d.get("type") for d in defects]
    if bad := [
        d.get("severity") for d in defects if d.get("severity") not in (*SEVERITY_RANK, None)
    ]:
        errors.append(f"defects[].severity={bad}")

    kind = r.get("normal_or_defect")
    if kind == "normal":
        if defects or r.get("defect_type") is not None:
            errors.append(
                f"normal인데 불량 정보가 있다 (defect_type={r.get('defect_type')!r}, defects={types})"
            )
        if r.get("defect_category") != "none" or r.get("defect_severity") != "none":
            errors.append("normal이면 defect_category/defect_severity는 'none'")
        if r.get("is_known_defect") is not True:
            errors.append("normal이면 is_known_defect=true")
    elif kind == "defect":
        if not defects:
            errors.append("defect인데 defects[]가 비어 있다")
        if r.get("defect_category") not in ("visual", "logical"):
            errors.append(f"defect_category={r.get('defect_category')!r}")
        sevs = [d.get("severity") for d in defects]
        top = None if None in sevs or not sevs else max(sevs, key=lambda s: SEVERITY_RANK.get(s, 0))
        if r.get("defect_severity") != top:
            errors.append(
                f"defect_severity={r.get('defect_severity')!r} ≠ defects[] 최고값 {top!r}"
            )
        if r.get("defect_type") not in [d.get("type") for d in defects if d.get("severity") == top]:
            errors.append(f"defect_type={r.get('defect_type')!r}가 최고 severity 불량이 아니다")
    else:
        errors.append(f"normal_or_defect={kind!r}")

    if r.get("split") == "reference" and kind != "normal":
        errors.append("reference split은 정상만")
    if "unknown_visual" in types and r.get("split") != "test":
        errors.append("unknown_visual은 test에만 (학습·calibration 금지)")
    if image_root is not None and not (image_root / str(r.get("image_path"))).is_file():
        errors.append(f"이미지 파일 없음 {r.get('image_path')}")
    return errors
