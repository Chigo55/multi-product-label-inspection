"""#49 — 실험 스크립트는 콘솔 인코딩과 무관하게 정상 종료해야 한다.

CP949 콘솔(Windows 기본)은 em dash(U+2014)를 표현하지 못한다. 스크립트가 마지막 안내문을
출력하다 UnicodeEncodeError로 exit 1이 나면, MLflow run은 남는데도 자동화는 실패로 본다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = REPO_ROOT / "experiments"


def run_with_cp949(code: str) -> subprocess.CompletedProcess[str]:
    """stdout이 CP949인 자식 프로세스에서 실행한다."""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=EXPERIMENTS,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=os.environ | {"PYTHONIOENCODING": "cp949"},
    )


def test_cp949_stdout_breaks_without_bootstrap() -> None:
    """재현: bootstrap 없이는 em dash 출력이 exit 1이다 (이 테스트가 돌 전제)."""
    result = run_with_cp949("print('em dash — here')")
    assert result.returncode != 0
    assert "UnicodeEncodeError" in result.stderr


def test_bootstrap_survives_cp949_stdout() -> None:
    result = run_with_cp949("import _bootstrap; print('em dash — here')")
    assert result.returncode == 0, result.stderr
    assert "—" in result.stdout


def test_bootstrap_puts_repo_root_on_path() -> None:
    result = run_with_cp949("import _bootstrap; import src.utils.paths; print('ok')")
    assert result.returncode == 0, result.stderr


def test_every_experiment_script_imports_bootstrap() -> None:
    """새 스크립트가 bootstrap을 빼먹으면 여기서 걸린다."""
    for script in EXPERIMENTS.glob("*.py"):
        if script.name.startswith("_"):
            continue
        assert "_bootstrap import" in script.read_text(encoding="utf-8"), script.name
