"""Pilot benchmark 생성 (#33) — Recipe → 정상 이미지 + metadata.jsonl.

    uv run experiments/build_pilot.py

`datasets/registry.yaml`의 `pilot` 항목이 가리키는 root에 이미지를 쓰고, **검증기 오류가 0건일
때만** metadata를 쓴다. 이미지도 metadata도 커밋되지 않는다 — 이 스크립트로 재생성한다.

생성 결과는 Recipe와 `src/utils/pilot.py`만으로 결정된다(샘플별 seed = sha256(sample_id)).
그래서 registry의 `sha256`은 원본 아카이브 대신 **Recipe 파일 해시**다. 해시가 달라지면
데이터가 달라진 것이므로 `version`을 올리라고 여기서 막는다.

불량은 아직 없다 (#34). 지금은 test split도 전부 정상이다.
"""

from __future__ import annotations

import hashlib
from collections import Counter

import yaml
from _bootstrap import REPO_ROOT  # sys.path + UTF-8 stdout. 첫 import여야 한다

from src.utils.metadata import find_errors, write_jsonl
from src.utils.paths import SHARED_ROOT
from src.utils.pilot import build

REGISTRY_PATH = REPO_ROOT / "datasets" / "registry.yaml"
NAME = "pilot"


def main() -> None:
    entry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))[NAME]
    recipe_path = REPO_ROOT / entry["recipe"]
    recipe_bytes = recipe_path.read_bytes()

    digest = hashlib.sha256(recipe_bytes).hexdigest()
    if digest != entry["sha256"]:
        raise ValueError(
            f"Recipe가 registry에 등록된 내용과 다르다 — 데이터가 달라진다.\n"
            f"  {entry['recipe']}\n"
            f"  registry: {entry['sha256']}\n"
            f"  실제    : {digest}\n"
            f"Recipe를 의도적으로 바꿨다면 registry의 version을 올리고 sha256을 위 값으로 바꾼다."
        )

    recipe = yaml.safe_load(recipe_bytes.decode("utf-8"))
    root = SHARED_ROOT / entry["root"]
    rows = build(recipe, root)

    if errors := find_errors(rows, image_root=root):
        raise ValueError(
            f"{NAME}: 검증 실패 {len(errors)}건 — metadata를 쓰지 않는다: {errors[:5]}"
        )
    out = SHARED_ROOT / entry["metadata"]
    write_jsonl(rows, out)
    report(recipe, rows)
    print(
        f"[{NAME} v{entry['version']}] {len(rows)} rows → {out.relative_to(SHARED_ROOT).as_posix()}"
    )


def report(recipe: dict, rows: list[dict]) -> None:
    """calibration이 성립하는지(val 정상 표본이 f를 표현할 수 있는지)까지 같이 본다."""
    target = recipe["product_false_reject_target"]
    counts = Counter((r["product_id"], r["split"]) for r in rows)
    units = {(r["product_id"], r["split"]): set() for r in rows}
    for r in rows:
        units[(r["product_id"], r["split"])].add(r["unit_id"])

    for product_id, product in recipe["products"].items():
        n_slots = len(product["slots"])
        f = 1 - (1 - target) ** (1 / n_slots)
        n_val = counts[(product_id, "val")]
        mark = "ok" if n_val >= 1 / f else f"거칠다 — {round(1 / f)} row 이상 필요"
        print(f"  {product_id} ({product['name']}, L={n_slots} slot)")
        for split in ("reference", "train", "val", "test"):
            print(
                f"    {split:10s} unit {len(units[(product_id, split)]):4d} | row {counts[(product_id, split)]:5d}"
            )
        print(
            f"    F={target:.1%} → 라벨 단위 f={f:.3%}, val 정상 {n_val} row 분위수 해상도 {mark}"
        )

    unknown = {r["actual_label_id"] for r in rows if r["is_known_label"] is False}
    print(
        f"  미등록 라벨(E3): {sorted(unknown)} — {sum(r['is_known_label'] is False for r in rows)} row, test 전용"
    )
    print(
        f"  Label Identity {len({r['actual_label_id'] for r in rows})}종 / LOT {sorted({r['production_lot'] for r in rows})}"
    )


if __name__ == "__main__":
    main()
