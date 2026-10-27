"""Pilot-Real 인쇄용 라벨 내보내기 (#69 T14). 프로토콜은 `datasets/pilot_real.md`.

    uv run experiments/export_pilot_real_labels.py

Pilot과 **같은 Recipe·같은 그림**(`render_label`)을 인쇄 해상도로 내보낸다. PNG에 DPI를 적어 100%로
인쇄하면 Recipe 좌표계와 같은 실제 크기(mm)가 된다.

바코드만은 키우지 않고 같은 자리(`BARCODE_BOX`)에 같은 값·같은 심볼로지를 **모듈당 정수 px로 다시 그린다.**
Pilot 래스터는 모듈당 약 2px로 줄이면서 막대 폭이 고르지 않게 반올림돼, 원본 크기에서는 읽히지만 어떤
방식으로 키워도 9개 중 3~4개만 읽힌다(2026-10-27 확인) — 그대로 인쇄하면 실물에서 읽히지 않는다.
python-barcode의 300 dpi 렌더도 모듈당 2.36px라 같은 문제가 있어 모듈 패턴(`build()`)에서 직접 그린다. 내보낸 그림을 같은 판독
규칙(`read_barcode`)으로 다시 읽어 디지털 단계에서 먼저 확인한다. 인쇄 후 판독은 촬영 첫 회에 확인한다.
"""

from __future__ import annotations

import barcode
import yaml
from _bootstrap import REPO_ROOT  # sys.path + UTF-8 stdout. 첫 import여야 한다
from PIL import Image, ImageDraw

from src.models.barcode import read_barcode
from src.utils.paths import SHARED_ROOT
from src.utils.pilot import BARCODE_BOX, BARCODE_TYPE, PX_PER_MM, render_label

RECIPE_PATH = REPO_ROOT / "configs" / "recipes" / "pilot.yaml"
OUT = SHARED_ROOT / "datasets" / "custom" / "pilot_real" / "print"
SCALE = 4  # 6 px/mm x 4 = 24 px/mm ≈ 610 dpi — 일반 레이저 프린터(600 dpi)에서 바코드 모듈 1개가 약 8 dot


def print_barcode(value: str, size: tuple[int, int]) -> Image.Image:
    """Code128 막대를 모듈당 정수 px로 그린다. 남는 폭은 양쪽 quiet zone으로 나눈다."""
    modules = barcode.get(BARCODE_TYPE.lower(), value).build()[0]
    w, h = size
    k = w // (len(modules) + 10)  # 양쪽 quiet zone 최소 5 모듈
    img = Image.new("RGB", size, (255, 255, 255))
    draw, x0 = ImageDraw.Draw(img), (w - len(modules) * k) // 2
    for i, bit in enumerate(modules):
        if bit == "1":
            draw.rectangle([x0 + i * k, 0, x0 + (i + 1) * k - 1, h - 1], fill=(0, 0, 0))
    return img


def main() -> None:
    labels = yaml.safe_load(RECIPE_PATH.read_text(encoding="utf-8"))["labels"]
    dpi = PX_PER_MM * SCALE * 25.4
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{OUT.relative_to(SHARED_ROOT).as_posix()}  ({dpi:.1f} dpi, 100%로 인쇄)")
    for label_id, spec in labels.items():
        if not spec.get("known", True):
            continue  # 미등록 라벨(E3)은 Pilot-Real 1차에 넣지 않는다
        img = render_label(spec)
        big = img.resize((img.width * SCALE, img.height * SCALE), Image.Resampling.LANCZOS)
        if box := BARCODE_BOX.get(spec["layout"]):
            x, y, w, h = (v * SCALE for v in box)
            big.paste(print_barcode(spec["barcode"], (w, h)), (x, y))
        big.save(OUT / f"{label_id}.png", dpi=(dpi, dpi))
        barcode = read_barcode(big, spec["barcode"]) if spec.get("barcode") else "-"
        mm = f"{img.width / PX_PER_MM:.1f} x {img.height / PX_PER_MM:.1f} mm"
        print(f"  {label_id:4s} {spec['layout']:8s} {mm:16s} barcode {barcode}")


if __name__ == "__main__":
    main()
