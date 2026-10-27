"""Pilot benchmark 생성 (#33). 정본은 `configs/recipes/pilot.yaml`(Recipe)과 `datasets/schema.md`.

한 row = 한 Label Slot의 ROI 이미지 1장. 이미지는 커밋하지 않고 여기서 재생성한다 —
sample_id 해시로 seed를 잡으므로 **생성 순서와 무관하게 항상 같은 그림**이 나온다.

정상 이미지도 서로 달라야 AD 모델이 할 일이 생긴다. 그래서 라벨을 깨끗하게 붙이지 않고
원근 워프 → 조명 그라디언트 → blur → 센서 노이즈를 준다. 그 세기가 `NUISANCE`이고,
E6(domain shift)는 이 값을 키운 subset으로 만든다 (schema §4.4).

불량은 정상 라벨에 가하는 변형으로 만든다 (#34). 변형 자체는 `src/utils/synthetic.py`에 있고,
여기서는 어느 unit의 어느 자리에 넣을지와 metadata 기록만 한다.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import barcode
import numpy as np
from barcode.writer import ImageWriter
from matplotlib import get_data_path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.utils import synthetic
from src.utils.metadata import SEVERITY_RANK

# 제품 좌표계(mm) ↔ 픽셀. ROI 256px = 약 43mm 시야.
PX_PER_MM = 6.0
# 정상 위치 오차는 Recipe tolerance의 이 비율 안에서만 흔든다 (넘으면 wrong_position 불량이다)
NORMAL_JITTER = 0.8

FONT_DIR = Path(get_data_path()) / "fonts" / "ttf"
FONT_FILES = {
    "mono": "DejaVuSansMono.ttf",
    "sans": "DejaVuSans-Bold.ttf",
    "serif": "DejaVuSerif.ttf",
}
PALETTES = {
    "steel": {"bg": (238, 238, 232), "fg": (32, 32, 34), "line": (92, 94, 98)},
    "paper": {"bg": (250, 250, 247), "fg": (24, 24, 24), "line": (140, 140, 140)},
    "amber": {"bg": (243, 197, 46), "fg": (26, 22, 10), "line": (26, 22, 10)},
    "mint": {"bg": (214, 235, 218), "fg": (28, 56, 38), "line": (110, 150, 120)},
}
# 제품 표면. (기본색, 결 방향) — 라벨 주변으로 보이는 배경이다.
BODIES = {
    "brushed_metal": ((150, 152, 156), "horizontal"),
    "plastic_dark": ((62, 64, 70), "none"),
    "carton": ((196, 176, 146), "vertical"),
}
BARCODE_TYPE = "Code128"

# E6에서 이 값을 키워 shift subset을 만든다 (schema §4.4)
NUISANCE = {
    "warp_px": 5.0,  # 원근 워프로 네 모서리가 움직이는 최대 px
    "light_gain": 0.26,  # 조명 그라디언트 진폭 (1.0 = 완전 암부~명부)
    "blur_px": 0.9,  # gaussian blur 반경 상한
    "noise_sigma": 4.0,  # 센서 노이즈 표준편차 (0~255 스케일)
}


BUILT_VERSION_FILE = "dataset_version.txt"  # build_pilot.py가 metadata 옆에 남긴다
NUISANCE_FILE = "nuisance.jsonl"  # 샘플별 실제 촬영 조건 (#69 T8). metadata와 행 수가 같다


def check_built_version(root: Path, version: str) -> None:
    """root의 metadata가 registry의 이 version으로 생성됐는지. 아니면 멈춘다.

    Recipe 해시만 보면 변환기만 바뀐 version 차이(예: 0.3 → 0.4)를 못 잡아, 다른 데이터에
    `dataset_version`이 잘못 기록된다.
    """
    f = root / BUILT_VERSION_FILE
    built = f.read_text(encoding="utf-8").strip() if f.exists() else "(기록 없음)"
    if built != version:
        raise ValueError(
            f"{root}: metadata는 v{built}로 생성됐는데 registry는 v{version}이다 — build_pilot.py로 재생성"
        )


def text_sha256(data: bytes) -> str:
    """줄바꿈을 LF로 맞춘 sha256 — Recipe 해시가 체크아웃 OS(CRLF/LF)에 따라 달라지지 않게."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def rng_for(sample_id: str) -> np.random.Generator:
    """sample_id만으로 정해지는 난수원. 생성 순서·병렬화와 무관하게 재현된다."""
    digest = hashlib.sha256(sample_id.encode()).digest()[:8]
    return np.random.default_rng(int.from_bytes(digest, "big"))


@lru_cache(maxsize=64)
def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    """matplotlib이 동봉한 DejaVu를 쓴다 — 폰트 파일을 커밋하지 않아도 어디서나 같은 그림이 나온다."""
    return ImageFont.truetype(str(FONT_DIR / FONT_FILES[kind]), size)


@lru_cache(maxsize=32)
def barcode_strip(value: str, size: tuple[int, int]) -> Image.Image:
    """Code128 바코드. 사람이 읽는 문자열(HRI)은 끄고 막대만 남긴다.

    HRI를 켜면 b-3/b-4처럼 **바코드 값만 다른 라벨**이 OCR로도 구별돼서 E5-extreme이 성립하지 않는다.

    ponytail: 256px ROI 안에서는 6자 값이 모듈당 약 2px다 — 판독 하한에 가깝다.
    Week 13에서 실제 디코더가 놓치면 registry의 roi_size를 키우고 dataset_version을 올린다.
    """
    writer_cls = ImageWriter  # python-barcode는 Pillow가 없으면 이걸 None으로 둔다
    if writer_cls is None:
        raise ImportError("python-barcode가 Pillow를 찾지 못했다 — uv sync로 다시 설치한다")
    img = barcode.get("code128", value, writer=writer_cls()).render(
        {"module_height": 8.0, "quiet_zone": 1.0, "write_text": False, "dpi": 300}
    )
    return img.convert("L").resize(size, Image.Resampling.LANCZOS)


# ------------------------------------------------------------
# Layout — 라벨 한 장을 그린다. 좌표는 domain spec이 아니라 그리는 방법이라 Recipe가 아닌 여기 있다.
# ------------------------------------------------------------
LABEL_SIZE = {"plate": (216, 136), "tag": (216, 128), "warning": (192, 136), "food": (208, 108)}


def _blank(
    layout: str, pal: dict[str, tuple[int, int, int]]
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", LABEL_SIZE[layout], pal["bg"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (img.width - 1, img.height - 1)], outline=pal["line"], width=2)
    return img, draw


def _paste_barcode(img: Image.Image, value: str, box: tuple[int, int, int, int]) -> None:
    x, y, w, h = box
    img.paste(barcode_strip(value, (w, h)).convert("RGB"), (x, y))


def render_label(spec: dict[str, Any]) -> Image.Image:
    """Label Identity 1개를 그린다. 같은 spec이면 항상 같은 픽셀이 나온다 (난수 없음)."""
    layout, pal, font_kind = spec["layout"], PALETTES[spec["palette"]], spec["font"]
    text: dict[str, str] = spec["text"]
    img, draw = _blank(layout, pal)

    if layout == "plate":  # 산업용 명판: KEY VALUE 세 줄 + 하단 바코드
        for (key, value), (y, size) in zip(
            text.items(), ((10, 22), (44, 18), (72, 18)), strict=False
        ):
            draw.text((12, y), f"{key} {value}", font=_font(font_kind, size), fill=pal["fg"])
        _paste_barcode(img, spec["barcode"], (10, 98, 196, 30))
    elif layout == "tag":  # 바코드 태그: 제품군 한 줄 + 큰 바코드
        title = next(iter(text.values()))
        draw.text((14, 8), title, font=_font(font_kind, 20), fill=pal["fg"])
        _paste_barcode(img, spec["barcode"], (10, 38, 196, 78))
    elif layout == "warning":  # 경고 라벨: 큰 제목 + 본문. 바코드 없음
        values = list(text.values())
        draw.text((16, 22), values[0], font=_font(font_kind, 32), fill=pal["fg"])
        draw.text((16, 76), values[1], font=_font(font_kind, 22), fill=pal["fg"])
    elif layout == "food":  # 식품 라벨: 값만 두 줄, serif
        for value, (y, size) in zip(text.values(), ((16, 22), (56, 20)), strict=False):
            draw.text((14, y), value, font=_font(font_kind, size), fill=pal["fg"])
    else:
        raise ValueError(f"알 수 없는 layout: {layout!r}")
    return img


# ------------------------------------------------------------
# 촬영 조건 — 같은 라벨도 매번 다르게 찍힌다
# ------------------------------------------------------------
def body_patch(body: str, size: tuple[int, int], rng: np.random.Generator) -> Image.Image:
    """제품 표면. 라벨 주변에 보이는 배경이다."""
    base, grain = BODIES[body]
    w, h = size
    arr = np.array(base, dtype=float) + rng.normal(0, 3.0, (h, w, 1))
    if grain == "horizontal":
        arr += rng.normal(0, 9.0, (h, 1, 1))  # 헤어라인 가공 결
    elif grain == "vertical":
        arr += rng.normal(0, 7.0, (1, w, 1))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _perspective_coeffs(
    src: list[tuple[float, float]], dst: list[tuple[float, float]]
) -> list[float]:
    """PIL은 출력→입력 역방향 매핑 계수를 받는다."""
    rows = []
    for (x, y), (u, v) in zip(dst, src, strict=True):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    solution = np.linalg.solve(np.array(rows, dtype=float), np.array(src, dtype=float).reshape(8))
    return solution.tolist()


def apply_nuisance(
    img: Image.Image, rng: np.random.Generator, strength: dict[str, float] | None = None
) -> tuple[Image.Image, dict[str, Any]]:
    """원근 → 조명 → blur → 노이즈. 세기를 키우면 E6 shift subset이 된다.

    실제로 뽑힌 값도 돌려준다(nuisance sidecar, #69 T8). **난수 소비 순서는 바꾸지 않는다** —
    바꾸면 기존 이미지가 전부 달라진다.
    """
    s = NUISANCE | (strength or {})
    w, h = img.size

    corners = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
    warped = [
        (x + rng.uniform(-s["warp_px"], s["warp_px"]), y + rng.uniform(-s["warp_px"], s["warp_px"]))
        for x, y in corners
    ]
    img = img.transform(
        img.size,
        Image.Transform.PERSPECTIVE,
        _perspective_coeffs(corners, warped),
        Image.Resampling.BICUBIC,
    )

    # 한쪽에서 비스듬히 들어오는 조명
    angle = rng.uniform(0, 2 * np.pi)
    yy, xx = np.mgrid[0:h, 0:w] / max(w, h)
    ramp = (np.cos(angle) * xx + np.sin(angle) * yy)[..., None]
    arr = np.array(img, dtype=float) * (1.0 + s["light_gain"] * (ramp - ramp.mean()) * 2)

    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    blur = float(rng.uniform(0.2, s["blur_px"]))
    img = img.filter(ImageFilter.GaussianBlur(blur))

    arr = np.array(img, dtype=float) + rng.normal(0, s["noise_sigma"], (h, w, 3))
    used = {
        "warp_px": [[wx - x, wy - y] for (x, y), (wx, wy) in zip(corners, warped, strict=True)],
        "light_angle": float(angle),
        "light_gain": s["light_gain"],
        "blur_radius": blur,
        "noise_sigma": s["noise_sigma"],
    }
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB"), used


def render_roi(
    spec: dict[str, Any] | None,
    body: str,
    roi: tuple[int, int],
    offset_mm: tuple[float, float],
    theta_deg: float,
    rng: np.random.Generator,
    strength: dict[str, float] | None = None,
    label_fx: synthetic.LabelFx | None = None,
) -> tuple[Image.Image, dict[str, Any]]:
    """Label Slot 하나의 ROI 이미지와 실제로 쓴 촬영 조건·위치 (nuisance sidecar 한 행).

    라벨을 제품 표면에 붙이고 촬영 조건을 입힌다.

    `spec`이 None이면 라벨이 없는 자리다(missing_label). `label_fx`는 라벨 위에만 얹는 외관 불량이다 —
    배경까지 더럽히면 "라벨 불량"이 아니라 "사진 불량"이 된다.

    원근 워프는 프레임 밖을 끌어온다 — 가장자리에 검은 쐐기가 생기지 않도록 여유분까지 그린 뒤
    가운데를 잘라낸다.
    """
    pad = int(np.ceil((strength or NUISANCE).get("warp_px", NUISANCE["warp_px"]))) + 2
    work = (roi[0] + 2 * pad, roi[1] + 2 * pad)
    canvas = body_patch(body, work, rng)

    if spec is not None:
        label = render_label(spec)
        if label_fx is not None:
            label = label_fx(label, rng)
        # 회전하면 네 귀퉁이가 라벨 밖이 된다 — alpha로 비워 두고 mask로 붙여야 검은 삼각형이 안 생긴다
        label = label.convert("RGBA")
        label = label.rotate(
            theta_deg, Image.Resampling.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0)
        )
        x = round(work[0] / 2 - label.width / 2 + offset_mm[0] * PX_PER_MM)
        y = round(work[1] / 2 - label.height / 2 + offset_mm[1] * PX_PER_MM)
        canvas.paste(label, (x, y), label)

    out, used = apply_nuisance(canvas, rng, strength)
    used |= {"offset_mm": list(offset_mm), "theta_deg": theta_deg}
    return out.crop((pad, pad, pad + roi[0], pad + roi[1])), used


# ------------------------------------------------------------
# E5 — 두 Label Identity가 얼마나 헷갈리는가 (#35)
# ------------------------------------------------------------
E5_TIERS = ("easy", "medium", "hard", "extreme")
SWAP_TYPES = ("wrong_label", "wrong_product_label")
# 구간 태그를 받는 라벨 바꿔치기. revision_mismatch는 구 revision 라벨로 바꿔 붙인 것이다 (#69 T5)
TIER_TAGGED = (*SWAP_TYPES, "revision_mismatch")


def similarity_tier(a: dict[str, Any], b: dict[str, Any]) -> str:
    """experiment_scenarios E5의 4구간을 카탈로그에서 기계적으로 정한다. 위에서부터 첫 번째로 맞는 구간이다.

    | 구간    | 규칙                                        | 예        |
    | easy    | layout·palette·font 중 하나라도 다르다      | a-1 / c-1 |
    | extreme | 겉모습과 인쇄 문자가 전부 같다 (바코드만 다름) | b-3 / b-4 |
    | hard    | 같은 field, 같은 글자 수, 다른 글자 ≤ 2개    | a-2 / a-4 |
    | medium  | 나머지 — 겉모습은 같고 내용이 여러 곳 다르다 | a-2 / b-2 |

    사람이 쌍을 골라 적지 않는 이유: 카탈로그가 바뀌면 구간도 따라 바뀌어야 하고,
    누락된 쌍(a-3 / b-3처럼 제품이 달라도 한 글자 차이인 쌍)이 생기지 않아야 한다.
    """
    if (a["layout"], a["palette"], a["font"]) != (b["layout"], b["palette"], b["font"]):
        return "easy"
    ta, tb = a["text"], b["text"]
    if ta == tb:
        return "extreme"
    same_shape = ta.keys() == tb.keys() and all(len(ta[k]) == len(tb[k]) for k in ta)
    if same_shape and sum(x != y for k in ta for x, y in zip(ta[k], tb[k], strict=True)) <= 2:
        return "hard"
    return "medium"


def e5_pairs(labels: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    """구간별 (Recipe가 요구한 라벨, 대신 붙은 라벨) 순서쌍. 미등록 라벨은 E3 몫이라 뺀다."""
    known = sorted(i for i, spec in labels.items() if spec.get("known", True))
    pairs: dict[str, list[tuple[str, str]]] = {t: [] for t in E5_TIERS}
    for a in known:
        for b in known:
            if a != b:
                pairs[similarity_tier(labels[a], labels[b])].append((a, b))
    return pairs


# ------------------------------------------------------------
# metadata row 생성
# ------------------------------------------------------------
# (split, seq, revision, lot, defect_type, forced, tag)
# - forced = (label_slot, 대신 붙일 라벨): E5 전용 unit과 revision_mismatch
# - tag = unit의 모든 row에 다는 태그: `E5`(E5 전용) / `GEOM-boundary` / `OCR-confusable`.
#   셋 다 특정 질문을 위해 덧붙인 unit이라 E1 평가 범위에서 뺀다 (ADR 0008)
Plan = tuple[str, int, str, str, str | None, tuple[str, str] | None, str | None]


def _v03_catalog(
    labels: dict[str, Any], products: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """`since`가 없는 라벨과 그 라벨만으로 된 revision. v0.3 unit은 이것으로 배정해야 그림이 그대로다 —
    새 라벨이 들어오면 revision 순환·무작위 바꿔치기 후보·E5 쌍 배정이 전부 달라진다 (#69 공통 규칙 4).
    """
    old = {k: v for k, v in labels.items() if "since" not in v}
    return old, {
        p: v
        | {"revisions": {r: s for r, s in v["revisions"].items() if set(s.values()) <= set(old)}}
        for p, v in products.items()
    }


def _unit_plan(
    product: dict[str, Any],
    labels: dict[str, Any],
    cfg: dict[str, Any],
    e5: list[tuple[str, str, str]],
) -> list[Plan]:
    """제품 1종의 unit 목록. defect_type이 None이면 정상 unit이다.

    - 미등록 라벨이 든 revision은 `test`에만 배정한다 (schema §4.2-3). 불량 unit에는 쓰지 않는다 —
      E3(미등록 라벨)와 불량이 한 unit에 겹치면 둘 다 해석할 수 없다.
    - LOT도 test와 나머지를 분리한다 (§4.2-2).
    - 불량 unit은 정상 unit **뒤에** 이어 붙인다. 그래야 정상 unit의 seq·그림이 불량 설정과 무관하게 유지된다.
    - hold-out 유형(E4)은 val에 넣지 않는다 — calibration에서 본 적 없는 불량이어야 한다.
    - E5 전용 unit(`e5` = [(defect_type, 요구된 라벨, 대신 붙일 라벨)])은 맨 뒤, test에만 둔다.
    """
    known_revs: list[str] = []
    unknown_revs: list[str] = []
    for rev, slots in product["revisions"].items():
        has_unknown = any(not labels[i].get("known", True) for i in slots.values())
        (unknown_revs if has_unknown else known_revs).append(rev)

    def lots_of(split: str) -> list[str]:
        return cfg["lots"]["test"] if split == "test" else cfg["lots"]["fit"]

    per_split = cfg["units_per_product"]
    n_unknown = cfg["unknown_units_per_product"] if unknown_revs else 0
    plan: list[Plan] = []
    seq = 0
    for split in ("reference", "train", "val", "test"):
        lots = lots_of(split)
        total = per_split[split]
        n_known = total - n_unknown if split == "test" else total
        for i in range(total):
            revs = known_revs if i < n_known else unknown_revs
            plan.append((split, seq, revs[i % len(revs)], lots[seq % len(lots)], None, None, None))
            seq += 1

    defects = cfg.get("defects") or {}
    types = defects.get("types", [])
    seen = [t for t in types if t not in defects.get("holdout", [])]
    for split, split_types, n in (
        ("val", seen, defects.get("val_units_per_type", 0)),
        ("test", types, defects.get("test_units_per_type", 0)),
    ):
        lots = lots_of(split)
        for defect_type in split_types:
            for i in range(n):
                plan.append(
                    (
                        split,
                        seq,
                        known_revs[i % len(known_revs)],
                        lots[seq % len(lots)],
                        defect_type,
                        None,
                        None,
                    )
                )
                seq += 1

    lots = lots_of("test")
    for defect_type, expected, actual in e5:
        rev, slot = next(
            (r, s) for r in known_revs for s, i in product["revisions"][r].items() if i == expected
        )
        plan.append(("test", seq, rev, lots[seq % len(lots)], defect_type, (slot, actual), "E5"))
        seq += 1
    return plan


def _v04_plan(
    product: dict[str, Any], labels: dict[str, Any], cfg: dict[str, Any], seq: int, share: dict
) -> list[Plan]:
    """v0.4 unit (#69 T5~T7). v0.3 unit 전부의 **뒤에** 붙인다. `share`는 이 제품 몫의 unit 수다.

    - 새 revision(`since` 라벨이 든 것)의 정상 unit — split마다 기존 등록 revision 하나와 같은 수
    - `revision_mismatch`: `revision_of`가 있는 라벨 자리에 구 revision 라벨을 붙인다 (val·test)
    - `GEOM-boundary`: 허용 오차 0.9~1.2배 위치·각도 (test). 정답은 실제 값이라 정상과 불량이 섞인다
    - `OCR-confusable`: 혼동 문자(0/O, 1/I …) 치환 `ocr_mismatch` (test)
    """
    revisions = product["revisions"]
    known = [
        r for r, s in revisions.items() if all(labels[i].get("known", True) for i in s.values())
    ]
    new = [r for r in known if any("since" in labels[i] for i in revisions[r].values())]
    old = [r for r in known if r not in new]
    plan: list[Plan] = []

    def add(
        split: str, revision: str, defect_type: str | None = None, forced=None, tag=None
    ) -> None:
        nonlocal seq
        lots = cfg["lots"]["test"] if split == "test" else cfg["lots"]["fit"]
        plan.append((split, seq, revision, lots[seq % len(lots)], defect_type, forced, tag))
        seq += 1

    n_unknown = cfg["unknown_units_per_product"] if len(known) < len(revisions) else 0
    for split, total in cfg["units_per_product"].items():
        for i in range((total - (n_unknown if split == "test" else 0)) // len(old) * len(new)):
            add(split, new[i % len(new)])

    swaps = [(r, s, labels[i].get("revision_of")) for r in known for s, i in revisions[r].items()]
    swaps = [x for x in swaps if x[2]]
    for split in ("val", "test"):
        for i in range(share[f"revision_mismatch_{split}"] if swaps else 0):
            r, slot, older = swaps[i % len(swaps)]
            add(split, r, "revision_mismatch", (slot, older))
    for defect_type in ("wrong_position", "wrong_orientation"):
        for i in range(share["geom_boundary"]):
            add("test", known[i % len(known)], defect_type, tag="GEOM-boundary")
    for i in range(share["ocr_confusable"]):
        add("test", known[i % len(known)], "ocr_mismatch", tag="OCR-confusable")
    return plan


def _barcode(spec: dict[str, Any] | None) -> dict[str, str] | None:
    value = spec.get("barcode") if spec else None
    return {"type": BARCODE_TYPE, "value": value} if value else None


def _row(
    *, sample_id: str, unit_id: str, product_id: str, label_slot: str, image_path: str,
    expected_id: str, expected_spec: dict[str, Any], actual_id: str | None,
    actual_spec: dict[str, Any] | None, expected_position: dict[str, Any],
    actual_position: dict[str, Any] | None, defects: list[dict[str, str]],
    is_known_defect: bool, lot: str, revision: str, split: str, experiment_tags: list[str],
) -> dict[str, Any]:  # fmt: skip
    """row 1개. `expected_*`는 Recipe에서, `actual_*`는 실제로 그린 것에서 온다.

    정상이면 Recipe가 요구한 라벨이 허용 오차 안에 붙어 있다 → expected == actual (위치만 흔들림).
    미등록 라벨(u-*)도 **정상**이다. Recipe가 그 라벨을 요구하고 실제로 그게 붙어 있기 때문이다.
    다른 점은 prototype이 없다는 것뿐이고, 그래서 `is_known_label=false`로만 표시한다 (E3).
    """
    top = max(defects, key=lambda d: SEVERITY_RANK[d["severity"]]) if defects else None
    category = "none"
    if top:
        category = "visual" if top["type"] in synthetic.VISUAL_TYPES else "logical"
    return {
        "sample_id": sample_id,
        "unit_id": unit_id,
        "product_id": product_id,
        "label_slot": label_slot,
        "camera_id": "CAM01",
        "image_path": image_path,
        "expected_label_id": expected_id,
        "actual_label_id": actual_id,
        "expected_text": dict(expected_spec["text"]),
        "actual_text": dict(actual_spec["text"]) if actual_spec else None,
        "expected_barcode": _barcode(expected_spec),
        "actual_barcode": _barcode(actual_spec),
        "expected_position": expected_position,
        "actual_position": actual_position,
        "normal_or_defect": "defect" if defects else "normal",
        "defect_category": category,
        "defect_type": top["type"] if top else None,
        "defect_severity": top["severity"] if top else "none",
        "defects": defects,
        "is_known_label": (actual_spec or expected_spec).get("known", True),
        "is_known_defect": is_known_defect,
        "production_lot": lot,
        "revision": revision,
        "split": split,
        "experiment_tags": experiment_tags,
    }


def build(
    recipe: dict[str, Any],
    out_root: Path,
    namespace: str = "custom_pilot",
    lots: dict[str, list[str]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recipe대로 이미지를 out_root에 쓰고 (metadata row, nuisance sidecar row)를 돌려준다.

    불량 unit은 Label Slot 하나에만 불량이 있고 나머지는 정상이다. 어느 자리인지는 unit_id로 정해진다.
    `namespace`는 unit_id 접두사이자 seed 네임스페이스다 — 같은 Recipe로 그림만 다른 분석용 세트
    (`pilot_dev`)를 만든다(#69 T9). `lots`는 그 세트의 LOT 이름이다.
    """
    labels, cfg = recipe["labels"], recipe["build"] | ({"lots": lots} if lots else {})
    old_labels, old_products = _v03_catalog(labels, recipe["products"])
    overrides: dict[str, str] = recipe.get("severity_overrides") or {}
    holdout = set((cfg.get("defects") or {}).get("holdout", []))
    roi = (recipe["roi_size"][0], recipe["roi_size"][1])
    owned = {
        p: sorted(
            {i for s in v["revisions"].values() for i in s.values() if labels[i].get("known", True)}
        )
        for p, v in old_products.items()
    }
    owner = {i: p for p, ids in owned.items() for i in ids}

    # v0.4 unit의 제품별 몫: 전체 수를 제품 수(revision_mismatch는 revision_of가 있는 제품 수)로 나눈다
    v04 = cfg.get("v04") or {}
    related = [
        p
        for p, v in recipe["products"].items()
        if any(labels[i].get("revision_of") for s in v["revisions"].values() for i in s.values())
    ]
    n = len(recipe["products"])
    share = {
        "geom_boundary": v04.get("geom_boundary", 0) // n,
        "ocr_confusable": v04.get("ocr_confusable", 0) // n,
    } | {
        f"revision_mismatch_{split}": k // max(len(related), 1)
        for split, k in (v04.get("revision_mismatch") or {"val": 0, "test": 0}).items()
    }

    # E5 전용 unit: 구간마다 n개를 그 구간의 순서쌍에 돌아가며 배정하고, 요구된 라벨의 제품에 둔다
    e5: dict[str, list[tuple[str, str, str]]] = {p: [] for p in recipe["products"]}
    n_e5 = cfg.get("e5_units_per_tier", 0)
    for pairs in e5_pairs(old_labels).values():
        for k in range(n_e5 if pairs else 0):
            expected, actual = pairs[k % len(pairs)]
            same = owner[expected] == owner[actual]
            e5[owner[expected]].append((SWAP_TYPES[0] if same else SWAP_TYPES[1], expected, actual))

    rows: list[dict[str, Any]] = []
    nuisance: list[dict[str, Any]] = []
    for product_id, product in recipe["products"].items():
        tol = product["tolerance"]
        others = [i for p, ids in owned.items() if p != product_id for i in ids]
        plan = _unit_plan(old_products[product_id], labels, cfg, e5[product_id])
        plan += _v04_plan(product, labels, cfg, len(plan), share)
        for split, seq, revision, lot, defect_type, forced, tag in plan:
            unit_id = f"{namespace}/{product_id}/{split}/{seq:05d}"
            out_dir = out_root / "images" / product_id / split
            out_dir.mkdir(parents=True, exist_ok=True)
            slots: dict[str, str] = product["revisions"][revision]

            # 정상 흔들림을 먼저 뽑는다 — 정상 row의 난수 소비 순서가 불량 유무와 무관해진다
            jitter: dict[str, tuple[np.random.Generator, tuple[float, float], float]] = {}
            for label_slot in slots:
                rng = rng_for(f"{unit_id}/{label_slot}")
                dx, dy = rng.uniform(-1, 1, 2) * tol["xy_mm"] * NORMAL_JITTER
                dtheta = float(rng.uniform(-1, 1) * tol["theta_deg"] * NORMAL_JITTER)
                jitter[label_slot] = (rng, (float(dx), float(dy)), dtheta)

            broken: dict[str, synthetic.Mutation] = {}
            if forced is not None:
                slot, actual = forced
                _, offset, dtheta = jitter[slot]
                assert defect_type is not None
                broken[slot] = synthetic.Mutation(
                    defect_type, actual, labels[actual], offset, dtheta
                )
            elif tag == "GEOM-boundary":
                assert defect_type is not None
                slot = str(rng_for(unit_id).permutation(list(slots))[0])
                rng, offset, dtheta = jitter[slot]
                offset, dtheta, beyond = synthetic.boundary_offset(
                    defect_type, tol, offset, dtheta, rng
                )
                if beyond:
                    broken[slot] = synthetic.Mutation(
                        defect_type, slots[slot], labels[slots[slot]], offset, dtheta
                    )
                else:  # 허용 오차 안이면 정상이다 — 흔들림만 경계까지 키운 정상 row
                    jitter[slot] = (rng, offset, dtheta)
            elif defect_type is not None:
                for label_slot in (str(s) for s in rng_for(unit_id).permutation(list(slots))):
                    rng, offset, dtheta = jitter[label_slot]
                    m = synthetic.mutate(
                        defect_type, expected_id=slots[label_slot], labels=labels,
                        same_product=owned[product_id], other_products=others,
                        tolerance=tol, offset_mm=offset, theta_deg=dtheta, rng=rng,
                        confusable=tag == "OCR-confusable",
                    )  # fmt: skip
                    if m is not None:
                        broken[label_slot] = m
                        break
                if not broken:
                    raise ValueError(f"{unit_id}: {defect_type}를 넣을 수 있는 Label Slot이 없다")

            unit_tags = [tag] if tag else []
            for label_slot, identity in slots.items():
                rng, offset, dtheta = jitter[label_slot]
                m = broken.get(label_slot)
                actual_id, actual_spec = (
                    (m.actual_label_id, m.actual_spec) if m else (identity, labels[identity])
                )
                if m:
                    offset, dtheta = m.offset_mm, m.theta_deg
                nominal = product["slots"][label_slot]

                name = f"{seq:05d}_{label_slot}.png"
                img, used = render_roi(
                    actual_spec, product["body"], roi, offset, nominal["theta"] + dtheta, rng,
                    label_fx=m.label_fx if m else None,
                )  # fmt: skip
                img.save(out_dir / name)
                nuisance.append({"sample_id": f"{unit_id}/{label_slot}"} | used)

                actual_position = None
                if actual_spec is not None:
                    actual_position = {
                        "x": round(nominal["x"] + offset[0], 3),
                        "y": round(nominal["y"] + offset[1], 3),
                        "theta": round(nominal["theta"] + dtheta, 3),
                        "unit": "mm",
                    }
                defects, tags = [], [*unit_tags]
                if m:
                    sev = synthetic.severity(overrides, product_id, label_slot, m)
                    defects = [{"type": m.defect_type, "severity": sev}]
                if m and m.defect_type in TIER_TAGGED and actual_id is not None:
                    # 라벨 바꿔치기는 무작위로 생긴 것이든 E5 전용이든 전부 구간 태그를 단다
                    tags = [*tags, f"E5-{similarity_tier(labels[identity], labels[actual_id])}"]
                rows.append(
                    _row(
                        sample_id=f"{unit_id}/{label_slot}",
                        unit_id=unit_id,
                        product_id=product_id,
                        label_slot=label_slot,
                        image_path=f"images/{product_id}/{split}/{name}",
                        expected_id=identity,
                        expected_spec=labels[identity],
                        actual_id=actual_id,
                        actual_spec=actual_spec,
                        expected_position=dict(nominal) | {"unit": "mm"},
                        actual_position=actual_position,
                        defects=defects,
                        is_known_defect=not (m and m.defect_type in holdout),
                        lot=lot,
                        revision=revision,
                        split=split,
                        experiment_tags=tags,
                    )
                )
    return rows, nuisance
