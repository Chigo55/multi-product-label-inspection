"""워크트리의 로컬 자원 경로는 메인 체크아웃을 가리킨다."""

import subprocess
from pathlib import Path

import pytest

from src.utils.paths import shared_root


def test_shared_root_for_main_and_worktree(tmp_path: Path) -> None:
    main = tmp_path / "main"
    worktree = tmp_path / "worktree"
    subprocess.run(["git", "init", str(main)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(main),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-b", "linked", str(worktree)],
        check=True,
        capture_output=True,
    )

    assert shared_root(worktree).resolve() == main.resolve()
    assert shared_root(main).resolve() == main.resolve()


def test_shared_root_outside_git(tmp_path: Path) -> None:
    assert shared_root(tmp_path) == tmp_path


def test_shared_root_without_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    assert shared_root(tmp_path) == tmp_path
