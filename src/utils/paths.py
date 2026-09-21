"""gitignore된 로컬 자원(datasets/public·custom, mlflow.db, mlartifacts)은 메인 체크아웃에만 있다.

워크트리에서 실행해도 SHARED_ROOT는 메인 체크아웃을 가리킨다.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def shared_root(repo: Path) -> Path:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return repo
    return Path(out.stdout.strip()).parent


SHARED_ROOT = shared_root(REPO_ROOT)
