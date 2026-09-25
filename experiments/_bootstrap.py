"""experiments/ 스크립트의 공통 진입 처리. 각 스크립트가 **첫 import로** 가져온다.

두 가지를 한다.

1. 저장소 루트를 `sys.path`에 넣어 `uv run experiments/x.py`에서 `src`를 import할 수 있게 한다
   (pytest의 `pythonpath = ["."]`, pyrefly의 `search-path = ["."]`와 같은 규약).
2. stdout/stderr를 UTF-8로 고정한다. Windows 기본 콘솔 인코딩(CP949)은 em dash(U+2014),
   en dash(U+2013) 같은 문자를 표현하지 못해서, MLflow 기록이 다 끝난 뒤 마지막 안내문을
   출력하다 `UnicodeEncodeError`로 exit 1이 난다. run은 남지만 자동화(worker, CI)에는
   실패로 보인다 (#49).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

for _stream in (sys.stdout, sys.stderr):
    # 파이프/캡처로 감싸인 스트림은 reconfigure를 갖지 않는다 (pytest capture 등)
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")
