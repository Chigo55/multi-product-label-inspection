"""reports/evaluation_protocol.md §0~§6 의 코드 정본.

REVIEW 처리 규칙 (ADR 0002):
- DER / FPR: REVIEW는 escape도 false reject도 아니다 (3-state 그대로).
- Precision / Recall / F1: 2-state 지표이므로 REVIEW를 NG로 합친다. 따라서 Recall = 1 - DER.
- Review Rate: 전체 중 REVIEW 비율. 별도 비용 지표.
- FPR(2-state): REVIEW를 NG로 합친 과검률. 2-state 선행 연구 비교용. DER은 두 방식이 같다.

모든 비율 지표는 분자/분모와 Clopper-Pearson(exact) 양측 95% 신뢰구간을 함께 낸다 (ADR 0005).
최상위 지표는 입력 row(Defect-level) 단위다. `label_level`은 (unit_id, label_slot),
`product_level`은 unit_id로 묶어 같은 지표를 다시 낸다 (§4, ADR 0003): 판정은 최악값
(NG > REVIEW > OK, severity 무관), 정답은 하나라도 불량이면 불량, score는 최댓값.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from scipy.stats import binomtest
from sklearn.metrics import average_precision_score, roc_auc_score

OK, REVIEW, NG = "OK", "REVIEW", "NG"
DECISIONS = (OK, REVIEW, NG)  # 나쁜 순서로 정렬돼 있다 — max(key=DECISIONS.index)가 최악값
UNKNOWN = "UNKNOWN"  # predicted_label_id: 등록되지 않은 라벨로 거부
REVIEW_POLICY = (
    "DER/FPR: REVIEW is neither escape nor false reject; precision/recall/F1: REVIEW merged into NG"
)


def decide(score: float, t_ok: float, t_ng: float) -> str:
    """score < t_ok → OK, score > t_ng → NG, 그 사이(경계 포함)는 REVIEW."""
    if t_ok > t_ng:
        raise ValueError(f"t_ok({t_ok}) > t_ng({t_ng})")
    if score < t_ok:
        return OK
    if score > t_ng:
        return NG
    return REVIEW


def calibrate(
    rows: Sequence[dict[str, Any]],
    scores: Sequence[float],
    normal_ng_rate: float,
    normal_review_rate: float,
) -> tuple[float, float]:
    """val 정상 score만으로 (t_ok, t_ng)를 정한다 (evaluation_protocol §6, schema §4.3 안 A).

    rows와 scores는 같은 순서다. val이 아닌 row가 하나라도 있으면 멈춘다 — test로 threshold를
    정하는 경로를 코드에서 막는다. 불량 row는 받아도 쓰지 않는다.

    t_ng = Q(1-f): val 정상 중 NG(score > t_ng)는 f 이하다 — f가 목표 과검률.
    t_ok = Q(1-r): val 정상 중 약 r이 REVIEW 이상으로 간다.
    Q는 관측값 중에서 고르는 경험 분위수(method="higher")라 val이 작으면 해상도가 거칠다.
    """
    _require_val(rows, "threshold")
    normal_scores = [
        s for r, s in zip(rows, scores, strict=True) if r["normal_or_defect"] == "normal"
    ]
    if len(normal_scores) == 0:
        raise ValueError("calibration용 정상 score가 없다")
    if not 0 <= normal_ng_rate <= normal_review_rate <= 1:
        raise ValueError(f"0 <= f({normal_ng_rate}) <= r({normal_review_rate}) <= 1 이어야 한다")
    t_ok, t_ng = np.quantile(
        normal_scores, [1 - normal_review_rate, 1 - normal_ng_rate], method="higher"
    )
    return float(t_ok), float(t_ng)


def normalize(
    fit_rows: list[dict[str, Any]],
    fit_scores: Sequence[float],
    rows: list[dict[str, Any]],
    scores: Sequence[float],
) -> list[float]:
    """슬롯별 z-score 정규화 (§6, #69 T12). 통계는 `(product_id, label_slot)`마다 val 정상으로만 잡는다.

    라벨 종류마다 정상 점수 분포가 달라 한 threshold로 묶으면 NG가 특정 슬롯에 몰린다. 슬롯별 분위수
    threshold는 쓸 수 없다 — 슬롯당 val 정상이 약 170행이라 f=0.334%면 꼬리에 0.57건이다. 그래서 분포를
    맞춘 뒤 제품별 공통 분위수 threshold(`calibrate`)를 쓴다. test 점수도 같은 변환을 거쳐야 하므로
    calibrate와 따로 둔다. 분위수 rank 정규화는 쓰지 않는다 — f < 1/n이면 t_ng가 rank 최댓값 1.0에 붙어
    NG가 나올 수 없다.
    """
    _require_val(fit_rows, "정규화 통계")
    groups: dict[tuple, list[float]] = defaultdict(list)
    for r, s in zip(fit_rows, fit_scores, strict=True):
        if r["normal_or_defect"] == "normal":
            groups[(r.get("product_id"), r.get("label_slot"))].append(s)
    stats = {g: (float(np.mean(v)), float(np.std(v)) or 1.0) for g, v in groups.items()}
    out = []
    for r, s in zip(rows, scores, strict=True):
        mean, std = stats[(r.get("product_id"), r.get("label_slot"))]
        out.append((s - mean) / std)
    return out


def _require_val(rows: Sequence[dict[str, Any]], what: str) -> None:
    """val이 아닌 row가 하나라도 있으면 멈춘다 — test로 정하는 경로를 코드에서 막는다 (§6)."""
    if bad := sorted({str(r.get("split")) for r in rows} - {"val"}):
        raise ValueError(f"{what}는 val로만 정한다 (받은 split: {bad})")


def rate(k: int, n: int) -> dict[str, Any]:
    """k/n 과 Clopper-Pearson 95% 구간. n == 0이면 정의되지 않으므로 None."""
    if n == 0:
        return {"k": 0, "n": 0, "value": None, "ci95": None}
    ci = binomtest(k, n).proportion_ci(confidence_level=0.95, method="exact")
    return {"k": k, "n": n, "value": k / n, "ci95": [float(ci.low), float(ci.high)]}


def evaluate(rows: list[dict[str, Any]], preds: list[dict[str, Any]]) -> dict[str, Any]:
    """metadata rows 와 predictions 를 sample_id로 조인해서 지표를 계산한다."""
    by_id = {p["sample_id"]: p for p in preds}
    missing = [r["sample_id"] for r in rows if r["sample_id"] not in by_id]
    if missing or len(preds) != len(rows):  # rows의 sample_id 고유성은 metadata 검증기가 보장
        raise ValueError(
            f"예측이 평가 대상과 다르다 (누락 {missing[:5]}, rows {len(rows)}, preds {len(preds)})"
        )

    decision = [by_id[r["sample_id"]]["decision"] for r in rows]
    score = [by_id[r["sample_id"]]["anomaly_score"] for r in rows]
    if bad := sorted(set(decision) - set(DECISIONS)):
        raise ValueError(f"알 수 없는 decision: {bad}")

    # E3 주 기준: 미등록 라벨이 붙은 정상 row가 OK로 나간 비율. decision만 쓴다 (AD 모델에도 적용)
    unknown: dict[str, list[str]] = defaultdict(list)
    for r, d in zip(rows, decision, strict=True):
        if r.get("is_known_label") is False:
            unknown[str(r.get("actual_label_id"))].append(d)
    unknown_dec = [d for ds in unknown.values() for d in ds]
    # 슬롯별 FPR — 한 threshold로 묶으면 NG가 특정 슬롯에 몰린다(§6 정규화). 편차 = 최댓값 - 최솟값
    by_slot: dict[str, list[str]] = defaultdict(list)
    for r, d in zip(rows, decision, strict=True):
        if r["normal_or_defect"] == "normal":
            by_slot[f"{r.get('product_id')}.{r.get('label_slot')}"].append(d)
    slot_fpr = {k: rate(v.count(NG), len(v)) for k, v in sorted(by_slot.items())}
    slot_values = [x["value"] for x in slot_fpr.values()]
    # 귀속 검출(§4 보조): 불량 제품을 불량 슬롯 자체가 OK가 아닐 때만 잡았다고 센다. 같은 제품의 정상 슬롯이
    # REVIEW/NG여서 잡힌 것은 빼므로, 과검이 많은 모델이 Product-level DER에서 유리해지는 것을 드러낸다
    defect_units: dict[str, bool] = {}
    for r, d in zip(rows, decision, strict=True):
        if r["normal_or_defect"] == "defect":
            defect_units[r["unit_id"]] = defect_units.get(r["unit_id"], False) or d != OK
    # 행 수가 아니라 쌍·아이덴티티 수가 일반화의 표본이다 — 행 단위 CI는 "이 쌍, 이 라벨"에 대한 구간이다 (§5)
    e5_rows, e5_dec = _e5_subset(rows, decision)
    tiers = sorted({r["e5_tier"] for r in e5_rows})

    return {
        "review_policy": REVIEW_POLICY,
        **_decision_metrics(rows, decision, score),
        "defect_escape_rate_by_category": _der_by(rows, decision, "defect_category"),
        "defect_escape_rate_by_type": _der_by(rows, decision, "defect_type"),
        "false_positive_rate_by_slot": slot_fpr,
        "slot_fpr_spread": max(slot_values) - min(slot_values) if len(slot_values) > 1 else None,
        "similar_label_confusion_rate": _der_by(e5_rows, e5_dec, "e5_tier"),
        "similar_label_confusion_rate_by_pair": _der_by(e5_rows, e5_dec, "e5_pair"),
        "n_pairs": {t: len({r["e5_pair"] for r in e5_rows if r["e5_tier"] == t}) for t in tiers},
        **_identity(rows, [by_id[r["sample_id"]].get("predicted_label_id") for r in rows]),
        "unknown_label_ok_rate": rate(unknown_dec.count(OK), len(unknown_dec)),
        "unknown_label_ok_rate_by_label": {
            k: rate(v.count(OK), len(v)) for k, v in sorted(unknown.items())
        },
        "n_identities": len(unknown),
        "label_level": _decision_metrics(*_group(rows, decision, score, ("unit_id", "label_slot"))),
        "product_level": _decision_metrics(*_group(rows, decision, score, ("unit_id",))),
        "product_detection_attributed": rate(sum(defect_units.values()), len(defect_units)),
    }


# 제품 검토 예산 R의 격자 (§6 risk-coverage). AURC를 방법끼리 비교하려면 같은 격자여야 한다 — F 미만은 쓰지 않는다
RC_TARGETS = (0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30)


def label_rate(product_rate: float, n_labels: int) -> float:
    """제품 단위 비율 → 라벨 단위 비율: 1 - (1 - R)^(1/L) (§6). 라벨 오류가 독립이라는 근사다."""
    return 1 - (1 - product_rate) ** (1 / n_labels)


def risk_coverage(
    rows: list[dict[str, Any]], decide_at: Callable[[float], list[str]], floor: float
) -> dict[str, Any]:
    """제품 검토 예산 R 격자(`RC_TARGETS` 중 floor=F 이상)마다 제품 단위 점과 AURC (§6, #69 T10).

    r 하나로 방법을 비교하면 결과가 r 선택에 좌우된다. `decide_at(R)`은 rows와 같은 순서의 판정이다 —
    R에 맞춘 calibration은 호출자가 val에서 한다. 점마다 비율은 분자·분모·95% CI와 함께 낸다:
    `normal_flagged`(정상 제품 중 REVIEW 이상 — R이 겨냥한 값), `review_rate`(전체 제품 중 REVIEW —
    실제 검토 부담), `der` / `cder`(제품 DER / CDER).

    AURC = 고정된 R 격자 위 제품 DER의 사다리꼴 면적 ÷ 구간 폭(구간 평균 DER). x축을 실제 Review Rate로
    두면 적분 구간이 방법마다 달라 비교할 수 없다. 작을수록 같은 예산에서 덜 샌다.
    """
    points: list[dict[str, Any]] = []
    for target in (t for t in RC_TARGETS if t >= floor):
        units, decision, score = _group(rows, decide_at(target), [0.0] * len(rows), ("unit_id",))
        m = _decision_metrics(units, decision, score)
        normal = m["confusion"]["normal"]
        points.append(
            {
                "product_review_target": target,
                "normal_flagged": rate(normal[REVIEW] + normal[NG], sum(normal.values())),
                "review_rate": m["review_rate"],
                "der": m["defect_escape_rate"],
                "cder": m["critical_defect_escape_rate"],
            }
        )
    xy = [(p["product_review_target"], p["der"]["value"]) for p in points if p["der"]["n"]]
    aurc = None
    if len(xy) > 1:
        x, y = [a for a, _ in xy], [b for _, b in xy]
        aurc = float(np.trapezoid(y, x) / (x[-1] - x[0]))
    return {"points": points, "aurc": aurc}


def _decision_metrics(
    rows: list[dict[str, Any]], decision: list[str], score: list[float]
) -> dict[str, Any]:
    """판정 지표 묶음. rows는 normal_or_defect와 defect_severity만 쓴다 — 어느 집계 단위든 같다."""
    is_defect = [r["normal_or_defect"] == "defect" for r in rows]

    def count(kind: bool, dec: str) -> int:
        return sum(d == kind and x == dec for d, x in zip(is_defect, decision, strict=True))

    n_def, n_norm = sum(is_defect), len(rows) - sum(is_defect)
    fn = count(True, OK)
    tp, fp = n_def - fn, n_norm - count(False, OK)  # 2-state: REVIEW → NG
    critical = [r.get("defect_severity") == "CRITICAL" for r in rows]
    precision, recall = rate(tp, tp + fp), rate(tp, n_def)
    p, r = precision["value"], recall["value"]

    return {
        "n": len(rows),
        "confusion": {
            "normal": {x: count(False, x) for x in DECISIONS},
            "defect": {x: count(True, x) for x in DECISIONS},
        },
        "defect_escape_rate": rate(fn, n_def),
        "critical_defect_escape_rate": rate(
            sum(c and x == OK for c, x in zip(critical, decision, strict=True)), sum(critical)
        ),
        "false_positive_rate": rate(count(False, NG), n_norm),
        "false_positive_rate_2state": rate(fp, n_norm),
        "review_rate": rate(decision.count(REVIEW), len(rows)),
        "precision": precision,
        "recall": recall,
        "f1": 2 * p * r / (p + r) if p is not None and r is not None and p + r > 0 else None,
        "auroc": float(roc_auc_score(is_defect, score)) if n_def and n_norm else None,
        "auprc": float(average_precision_score(is_defect, score)) if n_def and n_norm else None,
    }


def _group(
    rows: list[dict[str, Any]], decision: list[str], score: list[float], keys: tuple[str, ...]
) -> tuple[list[dict[str, Any]], list[str], list[float]]:
    """keys로 묶는다. 판정은 최악값(NG > REVIEW > OK), 하나라도 불량이면 불량, score는 최댓값 (§4)."""
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        groups[tuple(row[k] for k in keys)].append(i)
    members = list(groups.values())
    return (
        [
            {
                "normal_or_defect": "defect"
                if any(rows[i]["normal_or_defect"] == "defect" for i in m)
                else "normal",
                "defect_severity": "CRITICAL"
                if any(rows[i].get("defect_severity") == "CRITICAL" for i in m)
                else None,
            }
            for m in members
        ],
        [max((decision[i] for i in m), key=DECISIONS.index) for m in members],
        [max(score[i] for i in m) for m in members],
    )


def _identity(rows: list[dict[str, Any]], predicted: list[str | None]) -> dict[str, Any]:
    """Label Identity 지표 (§3). identity를 내지 않는 모델(전부 None)은 분모 0 → 정의되지 않음.

    라벨이 없는 row(missing_label, actual_label_id=None)는 맞힐 라벨이 없으므로 뺀다.
    Unknown을 등록 라벨로 억지 분류한 것은 오답과 따로 `unknown_forced_rate`로 센다.
    `open_set_accuracy`는 KNOWN_EXPECTED / KNOWN_WRONG / UNKNOWN 3-class 정확도다.
    """
    pairs = [] if all(p is None for p in predicted) else list(zip(rows, predicted, strict=True))
    known = [
        (r, p) for r, p in pairs if r.get("is_known_label") is True and r.get("actual_label_id")
    ]
    unknown = [p for r, p in pairs if r.get("is_known_label") is False]
    labeled = [
        (r, p) for r, p in pairs if r.get("actual_label_id") and r.get("is_known_label") is not None
    ]
    return {
        "known_label_accuracy": rate(sum(p == r["actual_label_id"] for r, p in known), len(known)),
        "unknown_label_detection_rate": rate(unknown.count(UNKNOWN), len(unknown)),
        "unknown_forced_rate": rate(sum(p not in (None, UNKNOWN) for p in unknown), len(unknown)),
        "open_set_accuracy": rate(
            sum(
                _open_set(r, r["actual_label_id"] if r["is_known_label"] else UNKNOWN)
                == _open_set(r, p)
                for r, p in labeled
            ),
            len(labeled),
        ),
    }


def _open_set(row: dict[str, Any], label: str | None) -> str | None:
    """라벨 하나를 open-set 상태로. 답이 없으면(None) 어느 상태와도 맞지 않는다."""
    if label is None or label == UNKNOWN:
        return label
    return "KNOWN_EXPECTED" if label == row.get("expected_label_id") else "KNOWN_WRONG"


def _e5_subset(
    rows: list[dict[str, Any]], decision: list[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """`E5-<구간>` 태그가 달린 row만, 구간(`e5_tier`)과 순서 없는 쌍(`e5_pair`)을 붙여서 (protocol §3)."""
    picked = [
        (row | {"e5_tier": tag.removeprefix("E5-"), "e5_pair": _pair(row)}, dec)
        for row, dec in zip(rows, decision, strict=True)
        for tag in row.get("experiment_tags") or []
        if tag.startswith("E5-")
    ]
    return [r for r, _ in picked], [d for _, d in picked]


def _pair(row: dict[str, Any]) -> str:
    """(요구, 실제) 라벨을 순서 없이 — b-3→b-4와 b-4→b-3은 같은 쌍이다."""
    return "/".join(sorted((str(row.get("expected_label_id")), str(row.get("actual_label_id")))))


def _der_by(rows: list[dict[str, Any]], decision: list[str], key: str) -> dict[str, Any]:
    """불량 row만 key로 묶은 DER. 복수 불량 row는 대표값(defect_type) 하나로만 센다."""
    groups: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row, dec in zip(rows, decision, strict=True):
        if row["normal_or_defect"] == "defect":
            g = groups[str(row.get(key))]
            g[0] += dec == OK
            g[1] += 1
    return {k: rate(*groups[k]) for k in sorted(groups)}
