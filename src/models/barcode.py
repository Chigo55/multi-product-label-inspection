"""Barcode 판독 (#66, #69 T3). 디코더 하나로 결정적 NG를 내지 않는다.

6자 Code128은 256px ROI에서 읽히지만 판독률이 디코더에 좌우되고, 디코더가 값을 잘못 읽기도 한다
(zxing-cpp가 `XA1001`을 `XA1011`로). 단일 디코더의 오판독은 그대로 과검이나 escape가 된다. 그래서
**두 디코더가 같은 값 하나를 읽어야 판독 성공**이다.

| 결과 | 조건 | 판정 |
|---|---|---|
| `MATCH` | 둘이 같은 값, 기대값과 같다 | OK |
| `MISMATCH` | 둘이 같은 값, 기대값과 다르다 (`barcode_mismatch`) | NG |
| `CONFLICT` | 둘 다 읽었지만 값이 다르다 (한 디코더가 값을 여럿 읽은 경우 포함) | REVIEW |
| `UNREADABLE` | 하나라도 못 읽었다 | REVIEW |

조합(`PAIR`)은 val 판독률 점검(`experiments/week05_barcode_check.py`, Week05.md)으로 정했다.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib.metadata import version

import zxingcpp
from PIL import Image
from pyzbar import pyzbar

from src.evaluation.metrics import NG, OK, REVIEW

MATCH, MISMATCH, UNREADABLE, CONFLICT = "MATCH", "MISMATCH", "UNREADABLE", "CONFLICT"
DECISION = {MATCH: OK, MISMATCH: NG, UNREADABLE: REVIEW, CONFLICT: REVIEW}


def _zxing(img: Image.Image) -> frozenset[str]:
    found = zxingcpp.read_barcodes(
        img, formats=zxingcpp.BarcodeFormats(zxingcpp.BarcodeFormat.Code128)
    )
    return frozenset(b.text for b in found)


def _zxing_x2(img: Image.Image) -> frozenset[str]:
    """모듈당 약 2px라 zxing-cpp가 놓친다. 2배 업스케일하면 읽힌다."""
    return _zxing(img.resize((img.width * 2, img.height * 2), Image.Resampling.BICUBIC))


def _pyzbar(img: Image.Image) -> frozenset[str]:
    found = pyzbar.decode(img, symbols=[pyzbar.ZBarSymbol.CODE128])
    return frozenset(b.data.decode() for b in found)


# 디코더 = 이미지 → 읽은 값의 집합 (못 읽으면 빈 집합)
DECODERS: dict[str, Callable[[Image.Image], frozenset[str]]] = {
    "pyzbar": _pyzbar,
    "zxing": _zxing,
    "zxing_x2": _zxing_x2,
}
PAIR = ("pyzbar", "zxing_x2")


def barcode_result(reads: Sequence[frozenset[str]], expected: str) -> str:
    """디코더별로 읽은 값 → MATCH / MISMATCH / CONFLICT / UNREADABLE (모듈 docstring 표)."""
    if any(not r for r in reads):
        return UNREADABLE
    if len(set().union(*reads)) > 1:
        return CONFLICT
    return MATCH if expected in reads[0] else MISMATCH


def read_barcode(img: Image.Image, expected: str) -> str:
    gray = img.convert("L")
    return barcode_result([DECODERS[name](gray) for name in PAIR], expected)


def decoder_params() -> dict[str, str]:
    """MLflow param — 판독률이 디코더와 버전에 좌우되므로 run마다 남긴다."""
    return {
        "barcode_decoders": "+".join(PAIR),
        "pyzbar_version": version("pyzbar"),
        "zxing_cpp_version": version("zxing-cpp"),
    }
