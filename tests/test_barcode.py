"""바코드 판독 규칙 (#66, #69 T3). 디코더 하나로 결정적 NG를 내지 않는다."""

from __future__ import annotations

import pytest
import yaml

from src.evaluation.metrics import NG, OK, REVIEW
from src.models.barcode import (
    CONFLICT,
    DECISION,
    MATCH,
    MISMATCH,
    UNREADABLE,
    barcode_result,
    read_barcode,
)
from src.utils.pilot import render_label
from tests.conftest import RECIPE_PATH

A, B = frozenset({"XA1001"}), frozenset({"XA1011"})
NONE: frozenset[str] = frozenset()


@pytest.mark.parametrize(
    ("reads", "expected"),
    [
        ((A, A), MATCH),  # 둘이 같은 값 = 판독 성공, 기대값과 같다
        ((B, B), MISMATCH),  # 둘이 같은 값인데 기대값과 다르다 → barcode_mismatch
        ((A, B), CONFLICT),  # 디코더끼리 다르다 — 어느 쪽도 믿지 않는다
        ((A | B, A), CONFLICT),  # 한 디코더가 값을 둘 읽었다
        ((A, NONE), UNREADABLE),  # 한쪽만 읽은 것은 판독 성공이 아니다
        ((NONE, NONE), UNREADABLE),
    ],
)
def test_two_decoders_must_agree(reads: tuple[frozenset[str], ...], expected: str) -> None:
    assert barcode_result(reads, "XA1001") == expected


def test_only_mismatch_is_ng() -> None:
    assert DECISION == {MATCH: OK, MISMATCH: NG, UNREADABLE: REVIEW, CONFLICT: REVIEW}


def test_reads_rendered_label() -> None:
    """실제 디코더 조합이 Pilot 생성기가 그린 Code128을 읽는다 (nuisance 없는 깨끗한 라벨)."""
    spec = yaml.safe_load(RECIPE_PATH.read_text(encoding="utf-8"))["labels"]["a-1"]
    img = render_label(spec)
    assert read_barcode(img, spec["barcode"]) == MATCH
    assert read_barcode(img, "XA9999") == MISMATCH
