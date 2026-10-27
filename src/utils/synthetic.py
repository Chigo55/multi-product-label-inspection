"""Synthetic defect 생성 (#34). 불량 enum의 정본은 `datasets/defect_taxonomy.md`.

불량 1건 = 정상 라벨 1장에 가하는 **변형(Mutation)** 1개다. 변형은 두 곳에 흔적을 남긴다.

- 그림: 다른 라벨을 붙이거나(swap), 글자·바코드를 바꿔 그리거나, 위치를 벗어나게 하거나,
  라벨 위에 오염·흐림을 얹는다.
- metadata: `actual_*`가 그 변형을 그대로 기록한다. `expected_*`는 Recipe 값이라 건드리지 않는다.

그래서 logical defect의 ground truth가 **정확하다** — 사람이 라벨링한 게 아니라 만든 쪽이 안다 (기준 문서 §25).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# defect_taxonomy.md §1~2의 기본 Severity. 둘은 항상 같아야 한다 (tests/test_synthetic.py가 대조한다)
DEFAULT_SEVERITY = {
    # VISUAL
    "scratch": "MAJOR",
    "contamination": "MINOR",
    "tear": "MAJOR",
    "blur": "MAJOR",
    "missing_print": "MAJOR",
    "color_anomaly": "MINOR",
    "fold": "MAJOR",
    "occlusion": "MAJOR",
    "unknown_visual": "MAJOR",
    # LOGICAL
    "missing_label": "CRITICAL",
    "wrong_label": "CRITICAL",
    "wrong_product_label": "CRITICAL",
    "wrong_position": "MAJOR",
    "wrong_orientation": "MAJOR",
    "ocr_mismatch": "CRITICAL",
    "barcode_mismatch": "CRITICAL",
    "revision_mismatch": "CRITICAL",
}
VISUAL_TYPES = frozenset(list(DEFAULT_SEVERITY)[:9])

LabelFx = Callable[[Image.Image, np.random.Generator], Image.Image]


@dataclass(frozen=True)
class Mutation:
    """정상 라벨 1장에 가한 변형. `actual_spec is None`이면 라벨이 없다(missing_label)."""

    defect_type: str
    actual_label_id: str | None
    actual_spec: dict[str, Any] | None
    offset_mm: tuple[float, float]
    theta_deg: float
    label_fx: LabelFx | None = None
    ocr_field: str | None = None  # ocr_mismatch가 바꾼 field — severity override 단위


def severity(overrides: dict[str, str], product_id: str, slot: str, m: Mutation) -> str:
    """taxonomy 기본값 → Recipe override (defect_taxonomy §3, ADR 0004). 가장 구체적인 키가 이긴다."""
    base = f"{product_id}.{slot}.{m.defect_type}"
    if m.ocr_field and f"{base}.{m.ocr_field}" in overrides:
        return overrides[f"{base}.{m.ocr_field}"]
    return overrides.get(base, DEFAULT_SEVERITY[m.defect_type])


# ------------------------------------------------------------
# 내용 변형 — 문자 1개만 바꾼다
# ------------------------------------------------------------
def _change_one_char(text: str, rng: np.random.Generator) -> str:
    """한 글자만 바꾼다. 숫자는 다른 숫자로, 영문자는 다른 영문자로 **균등하게** 뽑는다.

    그래서 실제 OCR이 틀리는 0/O, 1/I 같은 숫자↔영문 혼동은 나오지 않는다 — 그건 `_change_confusable`.
    """
    positions = [i for i, c in enumerate(text) if c.isalnum()]
    i = int(rng.choice(positions))
    pool = "0123456789" if text[i].isdigit() else "ABCDEFGHJKLMNPRSTUVWXYZ"
    choices = [c for c in pool if c != text[i].upper()]
    new = str(rng.choice(choices))
    return (
        text[:i] + (new if text[i].isupper() or text[i].isdigit() else new.lower()) + text[i + 1 :]
    )


# OCR이 실제로 헷갈리는 숫자↔영문 쌍 (#69 T7)
CONFUSABLE = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
CONFUSABLE |= {v: k for k, v in CONFUSABLE.items()}


def _change_confusable(text: str, rng: np.random.Generator) -> str | None:
    """혼동 쌍이 있는 글자 하나를 짝으로 바꾼다. 그런 글자가 없으면 None."""
    positions = [i for i, c in enumerate(text) if c in CONFUSABLE]
    if not positions:
        return None
    i = int(rng.choice(positions))
    return text[:i] + CONFUSABLE[text[i]] + text[i + 1 :]


def boundary_offset(
    defect_type: str,
    tolerance: dict[str, float],
    offset_mm: tuple[float, float],
    theta_deg: float,
    rng: np.random.Generator,
) -> tuple[tuple[float, float], float, bool]:
    """허용 오차의 0.9~1.2배로 한 축만 민다 (#69 T6 경계 표본). (offset, theta, 허용 오차를 넘었는가).

    `wrong_position`/`wrong_orientation`(1.3배 이상)과 정상 흔들림(0.8배 이내) 사이의 빈 구간을 채운다.
    정답은 실제 값으로 정한다 — 허용 오차 이하면 정상이다.
    """
    factor = float(rng.uniform(0.9, 1.2))
    sign = float(rng.choice([-1, 1]))
    if defect_type == "wrong_orientation":
        return offset_mm, factor * sign * tolerance["theta_deg"], factor > 1.0
    shift = factor * sign * tolerance["xy_mm"]
    offset = (shift, offset_mm[1]) if rng.random() < 0.5 else (offset_mm[0], shift)
    return offset, theta_deg, factor > 1.0


# ------------------------------------------------------------
# 외관 변형 — 라벨 이미지 위에만 얹는다 (배경은 정상)
# ------------------------------------------------------------
def _contamination(label: Image.Image, rng: np.random.Generator) -> Image.Image:
    """기름·먼지 얼룩 1~3개. 반투명이라 밑의 인쇄가 비친다."""
    stain = Image.new("RGBA", label.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(stain)
    for _ in range(int(rng.integers(1, 4))):
        r = float(rng.uniform(8, 22))
        cx, cy = rng.uniform(r, label.width - r), rng.uniform(r, label.height - r)
        tone = tuple(int(v) for v in rng.integers(60, 120, 3))
        draw.ellipse(
            [cx - r, cy - r * 0.7, cx + r, cy + r * 0.7], fill=(*tone, int(rng.integers(90, 170)))
        )
    stain = stain.filter(ImageFilter.GaussianBlur(3))
    return Image.alpha_composite(label.convert("RGBA"), stain)


def _blur(label: Image.Image, rng: np.random.Generator) -> Image.Image:
    """인쇄 번짐. 촬영 nuisance(반경 ≤0.9)보다 확실히 강하게 준다."""
    return label.filter(ImageFilter.GaussianBlur(float(rng.uniform(2.0, 3.2))))


def _print_streak(label: Image.Image, rng: np.random.Generator) -> Image.Image:
    """인쇄 헤드 막힘으로 생기는 가로 줄무늬 탈락. taxonomy에 없는 모양이라 unknown_visual(E4)로 쓴다."""
    out = label.convert("RGBA")
    draw = ImageDraw.Draw(out)
    bg = out.getpixel((4, out.height // 2))
    for _ in range(int(rng.integers(2, 5))):
        y = float(rng.uniform(6, out.height - 6))
        draw.rectangle([2, y, out.width - 3, y + float(rng.uniform(1.5, 3.5))], fill=bg)
    return out


# ------------------------------------------------------------
# 변형 생성
# ------------------------------------------------------------
def mutate(
    defect_type: str,
    *,
    expected_id: str,
    labels: dict[str, Any],
    same_product: list[str],
    other_products: list[str],
    tolerance: dict[str, float],
    offset_mm: tuple[float, float],
    theta_deg: float,
    rng: np.random.Generator,
    confusable: bool = False,
) -> Mutation | None:
    """Label Slot 하나에 defect_type을 가한다. 그 자리에 적용할 수 없으면(바코드 없는 라벨 등) None.

    offset_mm / theta_deg는 정상 흔들림이다. 위치·회전 불량이 아니면 그대로 둔다.
    `confusable`이면 `ocr_mismatch`를 혼동 문자 치환으로 만든다 — 그런 글자가 없는 라벨은 None.
    """
    spec = labels[expected_id]
    keep = {"offset_mm": offset_mm, "theta_deg": theta_deg}

    if defect_type in ("wrong_label", "wrong_product_label"):
        pool = [
            i
            for i in (same_product if defect_type == "wrong_label" else other_products)
            if i != expected_id
        ]
        other = str(rng.choice(pool))
        return Mutation(defect_type, other, labels[other], **keep)

    if defect_type == "ocr_mismatch" and confusable:
        fields = [k for k, v in spec["text"].items() if any(c in CONFUSABLE for c in v)]
        if not fields:
            return None
        field = str(rng.choice(fields))
        actual = copy.deepcopy(spec)
        actual["text"][field] = _change_confusable(spec["text"][field], rng)
        return Mutation(defect_type, expected_id, actual, ocr_field=field, **keep)

    if defect_type == "ocr_mismatch":
        field = str(rng.choice(list(spec["text"])))
        actual = copy.deepcopy(spec)
        actual["text"][field] = _change_one_char(spec["text"][field], rng)
        return Mutation(defect_type, expected_id, actual, ocr_field=field, **keep)

    if defect_type == "barcode_mismatch":
        if not spec.get("barcode"):
            return None
        actual = copy.deepcopy(spec) | {"barcode": _change_one_char(spec["barcode"], rng)}
        return Mutation(defect_type, expected_id, actual, **keep)

    if defect_type == "wrong_position":
        # 허용 오차의 1.3~2배. 한 축으로만 밀어야 어느 방향 불량인지 분명하다
        shift = float(rng.uniform(1.3, 2.0) * tolerance["xy_mm"] * rng.choice([-1, 1]))
        offset = (shift, offset_mm[1]) if rng.random() < 0.5 else (offset_mm[0], shift)
        return Mutation(defect_type, expected_id, spec, offset, theta_deg)

    if defect_type == "wrong_orientation":
        tilt = float(rng.uniform(2.5, 5.0) * tolerance["theta_deg"] * rng.choice([-1, 1]))
        return Mutation(defect_type, expected_id, spec, offset_mm, tilt)

    if defect_type == "missing_label":
        return Mutation(defect_type, None, None, **keep)

    fx = {"contamination": _contamination, "blur": _blur, "unknown_visual": _print_streak}
    if defect_type in fx:
        return Mutation(defect_type, expected_id, spec, label_fx=fx[defect_type], **keep)

    raise ValueError(f"생성기가 없는 defect_type: {defect_type!r}")
