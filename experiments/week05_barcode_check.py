"""Week 5 — 바코드 판독률 점검 (#66, #69 T3).

    uv run experiments/week05_barcode_check.py

val 정상 전체와 val `barcode_mismatch`를 디코더 3조건(pyzbar, zxing-cpp 원본, zxing-cpp 2배)으로 읽어
레이아웃별 판독률과 오판독 수를 낸다. 디코더 쌍마다 합의 규칙(`src/models/barcode.py`)을 적용해
`MATCH` / `MISMATCH` / `CONFLICT` / `UNREADABLE`을 센다. **정상에서 `MISMATCH`는 과검이다 — 0건이어야
하고, n과 95% 상한을 함께 본다.** 이 결과로 `barcode.PAIR`를 정한다 (Week05.md).
"""

from __future__ import annotations

import csv
import json
import tempfile
from collections import Counter
from itertools import combinations
from pathlib import Path

import mlflow
import yaml
from _bootstrap import REPO_ROOT  # sys.path + UTF-8 stdout. 첫 import여야 한다
from PIL import Image

from src.evaluation.metrics import rate
from src.models.barcode import DECODERS, MISMATCH, PAIR, RESULTS, barcode_result, decoder_params
from src.utils.metadata import read_jsonl
from src.utils.paths import SHARED_ROOT
from src.utils.pilot import check_built_version
from src.utils.tracking import flat_metrics, git_commit, git_is_dirty, start_experiment

CONFIG_PATH = REPO_ROOT / "configs" / "week05_barcode_check.yaml"
REGISTRY_PATH = REPO_ROOT / "datasets" / "registry.yaml"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> None:
    cfg = load_yaml(CONFIG_PATH)
    reg = load_yaml(REGISTRY_PATH)[cfg["dataset"]["name"]]
    layout = {k: v["layout"] for k, v in load_yaml(REPO_ROOT / reg["recipe"])["labels"].items()}
    root = SHARED_ROOT / reg["root"]
    check_built_version(root, reg["version"])
    rows = [
        r
        for r in read_jsonl(SHARED_ROOT / reg["metadata"])
        if r["split"] == cfg["dataset"]["split"]
        and r["expected_barcode"]  # 바코드 없는 라벨은 검사하지 않는다
        and (r["normal_or_defect"] == "normal" or r["defect_type"] == "barcode_mismatch")
    ]

    records = []
    for r in rows:
        img = Image.open(root / r["image_path"]).convert("L")
        reads = {name: decode(img) for name, decode in DECODERS.items()}
        records.append((r, reads))

    # 디코더 단독: 값 하나를 읽었는가 / 읽은 값이 실제 바코드와 다른가(오판독)
    single: Counter[tuple[str, str, str, str]] = Counter()
    for r, reads in records:
        key = (r["normal_or_defect"], layout[r["expected_label_id"]])
        actual = r["actual_barcode"]["value"]
        for name, got in reads.items():
            single[(*key, name, "n")] += 1
            single[(*key, name, "read")] += len(got) == 1
            single[(*key, name, "misread")] += bool(got - {actual})

    # 디코더 쌍: 합의 규칙 결과
    pairs: Counter[tuple[str, str, str]] = Counter()
    for r, reads in records:
        for a, b in combinations(DECODERS, 2):
            result = barcode_result([reads[a], reads[b]], r["expected_barcode"]["value"])
            pairs[(r["normal_or_defect"], f"{a}+{b}", result)] += 1

    def n_of(kind: str) -> int:
        return sum(r["normal_or_defect"] == kind for r in rows)

    chosen = "+".join(PAIR)
    false_ng = rate(pairs[("normal", chosen, MISMATCH)], n_of("normal"))
    caught = rate(pairs[("defect", chosen, MISMATCH)], n_of("defect"))

    start_experiment(cfg["tracking"]["experiment_name"])
    with mlflow.start_run(run_name="barcode-val") as run_info:
        mlflow.set_tags({"purpose": "barcode_check", "citable": "false"})
        mlflow.log_params(
            {
                "git_commit": git_commit(),
                "git_dirty": git_is_dirty(),
                "config_path": CONFIG_PATH.relative_to(REPO_ROOT).as_posix(),
                "dataset_name": cfg["dataset"]["name"],
                "dataset_version": reg["version"],
                "dataset_sha256": reg["sha256"],
                "split": cfg["dataset"]["split"],
                "research_question": cfg["experiment"]["research_question"],
                "scenario": cfg["experiment"]["scenario"],
                "num_normal": n_of("normal"),
                "num_barcode_mismatch": n_of("defect"),
            }
            | decoder_params()
        )
        mlflow.log_metrics(
            flat_metrics(
                {"normal_false_mismatch_rate": false_ng, "mismatch_detection_rate": caught}
            )
        )
        for path in (CONFIG_PATH, REGISTRY_PATH):
            mlflow.log_artifact(str(path), artifact_path="config")
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / "reads.csv").open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["sample_id", "normal_or_defect", "layout", "expected", *DECODERS])
                for r, reads in records:
                    w.writerow(
                        [
                            r["sample_id"],
                            r["normal_or_defect"],
                            layout[r["expected_label_id"]],
                            r["expected_barcode"]["value"],
                            *("|".join(sorted(v)) for v in reads.values()),
                        ]
                    )
            (Path(tmp) / "summary.json").write_text(
                json.dumps(
                    {
                        "single": {"/".join(k): v for k, v in sorted(single.items())},
                        "pairs": {"/".join(k): v for k, v in sorted(pairs.items())},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            mlflow.log_artifacts(tmp)

    print(f"run_id : {run_info.info.run_id}  ({cfg['tracking']['experiment_name']})")
    print(
        f"val    : 정상 {n_of('normal')}행, barcode_mismatch {n_of('defect')}행 (바코드 있는 라벨만)\n"
    )
    print("| 대상 | layout | 디코더 | n | 판독 | 오판독 |\n|---|---|---|---:|---:|---:|")
    for kind, lay, name, stat in sorted(single):
        if stat == "n":
            n = single[(kind, lay, name, "n")]
            read, mis = single[(kind, lay, name, "read")], single[(kind, lay, name, "misread")]
            print(f"| {kind} | {lay} | {name} | {n} | {read} ({read / n:.1%}) | {mis} |")
    print(
        "\n| 대상 | 디코더 쌍 | MATCH | MISMATCH | CONFLICT | UNREADABLE |\n|---|---|---:|---:|---:|---:|"
    )
    for kind in ("normal", "defect"):
        for a, b in combinations(DECODERS, 2):
            c = [pairs[(kind, f"{a}+{b}", x)] for x in RESULTS]
            print(f"| {kind} | {a}+{b} | " + " | ".join(map(str, c)) + " |")

    def ci(x: dict) -> str:
        return f"{x['k']}/{x['n']} (95% CI {x['ci95'][0]:.2%}~{x['ci95'][1]:.2%})"

    print(
        f"\n채택 {chosen}: 정상 오판독(MISMATCH) {ci(false_ng)}, barcode_mismatch 검출 {ci(caught)}"
    )


if __name__ == "__main__":
    main()
