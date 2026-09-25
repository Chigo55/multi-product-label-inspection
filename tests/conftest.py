"""여러 테스트 파일이 함께 쓰는 fixture."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.utils.pilot import build

RECIPE_PATH = Path(__file__).resolve().parents[1] / "configs" / "recipes" / "pilot.yaml"


@pytest.fixture(scope="session")
def pilot_small(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    """규모만 줄인 Pilot을 세션에 한 번 만든다 (Recipe, rows, 이미지 root).

    카탈로그·배치 규칙·불량 유형은 실제 Recipe 그대로다. 수백 장을 그리므로 테스트마다 새로 만들지 않는다.
    """
    recipe = yaml.safe_load(RECIPE_PATH.read_text(encoding="utf-8"))
    small = copy.deepcopy(recipe)
    small["build"]["units_per_product"] = {"reference": 2, "train": 2, "val": 2, "test": 4}
    small["build"]["unknown_units_per_product"] = 2
    small["build"]["defects"] |= {"val_units_per_type": 1, "test_units_per_type": 2}
    root = tmp_path_factory.mktemp("pilot_small")
    return small, build(small, root), root
