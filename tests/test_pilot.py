"""Pilot benchmark 생성 테스트 (#33).

여기서 고정하는 것은 두 가지다.

1. **Recipe 카탈로그가 #33이 요구한 관계를 실제로 담고 있는가.** 관계는 체크리스트가 아니라
   데이터여야 하고, 누가 Recipe를 손대도 관계가 깨지면 여기서 걸린다.
2. **생성 결과가 schema를 지키는가.** split·LOT·미등록 라벨 배치는 눈으로 못 본다.

실데이터(4800장) 생성은 오래 걸려서 테스트에서 하지 않는다 — 규모를 줄인 Recipe로 돌린다.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.utils.metadata import find_errors
from src.utils.pilot import (
    E5_TIERS,
    e5_pairs,
    render_label,
    render_roi,
    rng_for,
    similarity_tier,
    text_sha256,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RECIPE_PATH = REPO_ROOT / "configs" / "recipes" / "pilot.yaml"
REGISTRY_PATH = REPO_ROOT / "datasets" / "registry.yaml"


@pytest.fixture(scope="module")
def recipe() -> dict[str, Any]:
    return yaml.safe_load(RECIPE_PATH.read_text(encoding="utf-8"))


# ------------------------------------------------------------
# Recipe 카탈로그 — #33이 "반드시 포함할 관계"로 지정한 것들
# ------------------------------------------------------------
def _look(spec: dict[str, Any]) -> tuple[str, str, str]:
    """겉모습만. 이게 같고 text/barcode가 다르면 '외형은 같은데 내용만 다른' 쌍이다."""
    return (spec["layout"], spec["palette"], spec["font"])


def test_catalog_size(recipe: dict[str, Any]) -> None:
    """기준 문서 §24 Pilot 규모: 3 products / 10~15 label identities."""
    assert len(recipe["products"]) == 3
    assert 10 <= len(recipe["labels"]) <= 15


def test_same_product_similar_and_different(recipe: dict[str, Any]) -> None:
    labels = recipe["labels"]
    assert _look(labels["a-2"]) == _look(labels["a-4"])  # 같은 제품 / 외형 유사
    assert _look(labels["a-1"]) != _look(labels["a-3"])  # 같은 제품 / 외형 상이


def test_cross_product_similar_and_different(recipe: dict[str, Any]) -> None:
    labels, products = recipe["labels"], recipe["products"]
    owner = {
        i: p
        for p, v in products.items()
        for slots in v["revisions"].values()
        for i in slots.values()
    }
    assert owner["a-2"] != owner["b-2"] and _look(labels["a-2"]) == _look(labels["b-2"])
    assert owner["a-1"] != owner["c-1"] and _look(labels["a-1"]) != _look(labels["c-1"])


def test_ocr_only_difference(recipe: dict[str, Any]) -> None:
    """a-2 vs a-4: 외형도 barcode 자릿수도 같고 인쇄 문자만 다르다 (E5-hard 후보)."""
    a2, a4 = recipe["labels"]["a-2"], recipe["labels"]["a-4"]
    assert _look(a2) == _look(a4)
    assert a2["text"] != a4["text"]
    differing = sum(
        a != b
        for a, b in zip("".join(a2["text"].values()), "".join(a4["text"].values()), strict=True)
    )
    assert differing <= 2, "'문자 한두 글자만 다르다'를 넘어섰다"


def test_barcode_only_difference(recipe: dict[str, Any]) -> None:
    """b-3 vs b-4: 인쇄 문자가 완전히 같고 barcode 값만 다르다 (E5-extreme).

    이 쌍이 성립해야 '순수 visual embedding으로는 원리적으로 분리 불가능'을 주장할 수 있다.
    """
    b3, b4 = recipe["labels"]["b-3"], recipe["labels"]["b-4"]
    assert _look(b3) == _look(b4)
    assert b3["text"] == b4["text"]
    assert b3["barcode"] != b4["barcode"]


def test_barcode_only_pair_is_pixel_identical_except_bars(recipe: dict[str, Any]) -> None:
    """같은 값을 넣으면 b-3과 b-4는 완전히 같은 그림이다 — 차이가 오직 barcode에서만 온다."""
    b3 = copy.deepcopy(recipe["labels"]["b-3"])
    b4 = copy.deepcopy(recipe["labels"]["b-4"])
    b4["barcode"] = b3["barcode"]
    assert render_label(b3).tobytes() == render_label(b4).tobytes()


def test_unknown_labels_exist(recipe: dict[str, Any]) -> None:
    unknown = [i for i, s in recipe["labels"].items() if not s.get("known", True)]
    assert unknown, "E3용 미등록 라벨이 없다"


# ------------------------------------------------------------
# 생성 결과
# ------------------------------------------------------------
Small = tuple[dict[str, Any], list[dict[str, Any]], Path]


def test_build_passes_schema(pilot_small: Small) -> None:
    _, rows, root = pilot_small
    assert find_errors(rows, image_root=root) == []


def test_unknown_labels_only_in_test(pilot_small: Small) -> None:
    """schema §4.2-3. find_errors도 보지만, 애초에 만들어지지 않는지를 따로 고정한다."""
    _, rows, _ = pilot_small
    unknown = [r for r in rows if r["is_known_label"] is False]
    assert unknown, "미등록 라벨 row가 하나도 생성되지 않았다"
    assert {r["split"] for r in unknown} == {"test"}


def test_test_lots_are_disjoint(pilot_small: Small) -> None:
    """schema §4.2-2. 과거 LOT으로 학습·조정하고 미래 LOT을 검사한다."""
    _, rows, _ = pilot_small
    test_lots = {r["production_lot"] for r in rows if r["split"] == "test"}
    other_lots = {r["production_lot"] for r in rows if r["split"] != "test"}
    assert test_lots and other_lots and not (test_lots & other_lots)


def test_normal_rows_have_expected_equals_actual(pilot_small: Small) -> None:
    """정상이란 Recipe가 요구한 라벨이 그대로 붙어 있는 것이다. 위치만 허용 오차 안에서 흔들린다."""
    small, rows, _ = pilot_small
    tolerance = {p: v["tolerance"] for p, v in small["products"].items()}
    normal = [r for r in rows if r["normal_or_defect"] == "normal"]
    assert normal
    for r in normal:
        assert r["expected_label_id"] == r["actual_label_id"]
        assert r["expected_text"] == r["actual_text"]
        assert r["expected_barcode"] == r["actual_barcode"]
        tol = tolerance[r["product_id"]]
        assert abs(r["actual_position"]["x"] - r["expected_position"]["x"]) <= tol["xy_mm"]
        assert abs(r["actual_position"]["y"] - r["expected_position"]["y"]) <= tol["xy_mm"]
        assert (
            abs(r["actual_position"]["theta"] - r["expected_position"]["theta"]) <= tol["theta_deg"]
        )


def test_render_is_deterministic_per_sample_id(recipe: dict[str, Any]) -> None:
    """seed가 sample_id에서만 나오므로 생성 순서·병렬화와 무관하게 같은 그림이 재현된다."""
    spec = recipe["labels"]["a-2"]

    def once() -> bytes:
        return render_roi(
            spec, "brushed_metal", (64, 64), (0.3, -0.2), 1.0, rng_for("x/slot-1")
        ).tobytes()

    assert once() == once()
    other = render_roi(
        spec, "brushed_metal", (64, 64), (0.3, -0.2), 1.0, rng_for("y/slot-1")
    ).tobytes()
    assert once() != other, "sample_id가 달라도 같은 그림이면 정상 변이가 없는 것이다"


def test_registry_hash_matches_recipe() -> None:
    """registry의 sha256은 Recipe 파일 해시다 (원본 아카이브가 없으므로). 어긋나면 build가 막는다."""
    entry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))["pilot"]
    assert entry["sha256"] == text_sha256(RECIPE_PATH)


def test_text_sha256_ignores_line_endings(tmp_path: Path) -> None:
    """Windows 체크아웃(CRLF)과 Linux(LF)가 같은 Recipe에 같은 해시를 내야 한다 (#69 T1)."""
    (tmp_path / "lf").write_bytes(b"a: 1\nb: 2\n")
    (tmp_path / "crlf").write_bytes(b"a: 1\r\nb: 2\r\n")
    assert text_sha256(tmp_path / "lf") == text_sha256(tmp_path / "crlf")
    assert text_sha256(tmp_path / "lf") == hashlib.sha256(b"a: 1\nb: 2\n").hexdigest()


# ------------------------------------------------------------
# E5 난이도 구간 (#35)
# ------------------------------------------------------------
@pytest.mark.parametrize(
    ("a", "b", "tier"),
    [
        ("a-1", "c-1", "easy"),
        ("a-2", "b-2", "medium"),
        ("a-2", "a-4", "hard"),
        ("b-3", "b-4", "extreme"),
    ],
)
def test_designed_pairs_land_in_their_tier(
    recipe: dict[str, Any], a: str, b: str, tier: str
) -> None:
    """카탈로그를 설계할 때 의도한 쌍이 규칙으로도 같은 구간이 된다. 순서를 바꿔도 같다."""
    labels = recipe["labels"]
    assert similarity_tier(labels[a], labels[b]) == similarity_tier(labels[b], labels[a]) == tier


def test_every_tier_has_pairs(recipe: dict[str, Any]) -> None:
    pairs = e5_pairs(recipe["labels"])
    assert set(pairs) == set(E5_TIERS) and all(pairs.values())
    unknown = {i for i, s in recipe["labels"].items() if not s.get("known", True)}
    assert not [p for ps in pairs.values() for p in ps if set(p) & unknown], (
        "미등록 라벨은 E3 몫이다"
    )


def test_swap_rows_carry_their_tier_tag(pilot_small: Small) -> None:
    """바꿔치기 불량은 전부, 그리고 그것만 E5 태그를 받는다. 태그는 (요구, 실제) 쌍의 구간이다."""
    recipe, rows, _ = pilot_small
    labels = recipe["labels"]
    for r in rows:
        e5 = [t for t in r["experiment_tags"] if t.startswith("E5-")]
        if r["defect_type"] in ("wrong_label", "wrong_product_label"):
            tier = similarity_tier(labels[r["expected_label_id"]], labels[r["actual_label_id"]])
            assert e5 == [f"E5-{tier}"]
        else:
            assert e5 == []


def test_each_tier_gets_its_dedicated_units(pilot_small: Small) -> None:
    """무작위 바꿔치기로는 extreme(1쌍)이 거의 안 나온다. 전용 unit이 구간마다 최소 수를 채운다."""
    recipe, rows, _ = pilot_small
    n = recipe["build"]["e5_units_per_tier"]
    for tier in E5_TIERS:
        assert sum(f"E5-{tier}" in r["experiment_tags"] and r["split"] == "test" for r in rows) >= n


def test_extreme_rows_differ_only_in_barcode(pilot_small: Small) -> None:
    _, rows, _ = pilot_small
    extreme = [r for r in rows if "E5-extreme" in r["experiment_tags"]]
    assert extreme
    for r in extreme:
        assert r["actual_text"] == r["expected_text"]
        assert r["actual_barcode"] != r["expected_barcode"]
