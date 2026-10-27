"""시나리오별 평가 범위 — reports/experiment_scenarios.md "평가 범위"의 코드 정본 (ADR 0008).

전체 test를 한 번에 평가하면 시나리오끼리 서로의 지표를 오염시킨다. 미등록 라벨을 NG로 거부한 것은
E3의 정답인데, 그 row도 `normal`이라 E1 FPR에 과검으로 들어간다. 그래서 시나리오마다 범위를 잘라
`evaluate()`를 따로 돌린다. F 판단과 헤드라인 FPR·DER은 E1 결과만 쓴다.

범위는 **unit 단위**로 고른다. 한 unit의 row를 쪼개면 Product-level 판정이 달라진다.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from src.evaluation.metrics import evaluate

Unit = list[dict[str, Any]]


def _unknown_label(u: Unit) -> bool:
    return any(r.get("is_known_label") is False for r in u)


# 특정 질문을 위해 덧붙인 unit의 태그 — E1·E4에서 뺀다. 넣으면 불량 구성이 그쪽으로 쏠린다.
# `E5`는 E5 전용 unit(무작위 바꿔치기는 `E5-<구간>`만 있어 여기 들지 않는다), 나머지 둘은 Pilot v0.4 (#69)
DEDICATED = ("E5", "GEOM-boundary", "OCR-confusable")


def _tags(u: Unit) -> set[str]:
    return {t for r in u for t in r.get("experiment_tags") or []}


def _dedicated(u: Unit) -> bool:
    return bool(_tags(u) & set(DEDICATED))


RULES: dict[str, Callable[[Unit], bool]] = {
    "E1": lambda u: (
        not _unknown_label(u) and not _dedicated(u) and all(r.get("is_known_defect") for r in u)
    ),
    "E3": _unknown_label,
    "E4": lambda u: not _unknown_label(u) and not _dedicated(u),
    "E5": lambda u: any(t.startswith("E5-") for t in _tags(u)),
    # 시나리오가 아니라 덧붙인 unit 묶음 그대로 — 위치·각도 경계에서 REVIEW가 하는 일, OCR 혼동 문자
    "GEOM-boundary": lambda u: "GEOM-boundary" in _tags(u),
    "OCR-confusable": lambda u: "OCR-confusable" in _tags(u),
}


def scenario_rows(rows: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    """scenario 범위에 드는 unit의 row 전부 (입력 순서 유지)."""
    if scenario == "E4" and all(r.get("is_known_defect") is not False for r in rows):
        return []  # 본 적 없는 유형이 없으면 seen/unseen 비교가 성립하지 않는다 (public track)
    units: dict[str, Unit] = defaultdict(list)
    for r in rows:
        units[r["unit_id"]].append(r)
    keep = {u for u, unit in units.items() if RULES[scenario](unit)}
    return [r for r in rows if r["unit_id"] in keep]


def evaluate_scenarios(
    rows: list[dict[str, Any]], preds: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """범위가 비지 않은 시나리오마다 `evaluate()` 결과. 범위가 빈 시나리오는 키가 없다."""
    out = {}
    for scenario in RULES:
        if sub := scenario_rows(rows, scenario):
            ids = {r["sample_id"] for r in sub}
            out[scenario] = evaluate(sub, [p for p in preds if p["sample_id"] in ids])
    return out
