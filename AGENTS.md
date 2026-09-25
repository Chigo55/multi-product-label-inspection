# AGENTS.md

이 저장소에서 작업하는 코딩 에이전트(Claude Code, Codex 등)를 위한 안내다.

## 이 저장소의 성격

애플리케이션이 아니라 **24주짜리 연구 저장소**다(Week 1 = 2026-09-12). 코드는 그 자체가 목적이
아니라 RQ1~RQ6에 답하기 위해 존재한다. 주제는 다품종·다라벨 제조 환경의 Explainable Hybrid
Inspection System이고, 시스템 출력은 `OK`/`NG`가 아니라 **판정 + 원인 + 근거**다.

구현된 것은 평가 레일뿐이다: `src/utils/mvtec.py`·`visa.py`(MVTec AD / LOCO / VisA → JSONL), `src/utils/metadata.py`(JSONL 입출력·검증·public 공통 row),
`src/evaluation/metrics.py`(지표 정본), `src/utils/tracking.py`(MLflow). 모델은 아직 없다(Week 4 Gate).

## Commands

```bash
uv sync                          # .venv 생성 + 의존성 설치
uv sync --extra cv               # opencv-python-headless 포함
uv add <pkg>                     # 런타임 의존성 추가
uv add --dev <pkg>               # 개발 도구 추가

uv run pytest                            # 전체 테스트
uv run pytest tests/test_x.py::test_y    # 단일 테스트
uv run pytest -k mvtec                   # 이름으로 필터
uv run pytest -m "not slow"              # 느린 테스트 제외 (slow = 다운로드/학습 필요)

uv run ruff check . --fix        # lint (+ 자동 수정)
uv run ruff format .             # format (black 대체 — black은 설치하지 않는다)
uv run pyrefly check             # type check

uv run experiments/build_metadata.py mvtec_ad  # 원본을 registry의 root에 풀어 둔 뒤 metadata 생성 (mvtec_loco, visa도 같음)
uv run experiments/build_pilot.py             # 자체 Pilot benchmark 생성 (Recipe → 이미지 + metadata, 약 6분)
uv run experiments/week02_pipeline_check.py   # dummy 예측 → 평가 → MLflow (레일 점검)
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlartifacts # 메인 체크아웃에서
```

PyTorch는 하드웨어 종속이라 `pyproject.toml`에 고정하지 않는다:
`uv add torch torchvision --index https://download.pytorch.org/whl/cu124` (CPU는 `/cpu`).


## Agent skills

### Issue tracker

Issues live as GitHub issues in `Chigo55/multi-product-label-inspection`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

주차 메인 이슈(`week-main` label) → 하위 이슈 구조이고, Milestone 6개가 기준 문서 §37의 Phase에
대응한다. Week 5 이후는 해당 Phase 시작 시점에 분해한다.

### Triage labels

The five canonical triage roles, each used verbatim as its label string. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Architecture

### 문서가 스펙이고 `src/`는 그 구현이다

코드를 읽기 전에 어떤 문서가 무엇의 정본인지 알아야 한다.

| 문서 | 역할 |
|---|---|
| `docs/multi_product_..._research_summary.md` | 24주 기준 문서. **Week 1 스냅샷이므로 소급 수정하지 않는다** |
| `CONTEXT.md` | 용어의 정본. 도메인 개념을 부를 때 여기 정의된 단어를 쓴다 |
| `docs/adr/` | 되돌리기 어려운 결정 7건. 결정을 뒤집기 전에 읽는다 |
| `reports/research_questions.md` | RQ1~RQ6과 실험 시나리오(E1~E6) 매핑 |
| `reports/evaluation_protocol.md` | **무엇을 측정하는가.** 여기 없는 지표는 주장 근거로 쓰지 않는다. 코드 정본은 `src/evaluation/metrics.py` — 둘은 항상 같아야 한다 |
| `reports/experiment_scenarios.md` | E1~E6 시나리오별 입력·분할·지표·성공 기준 |
| `datasets/schema.md` / `defect_taxonomy.md` | metadata 필드와 불량 enum의 유일한 정의 |
| `configs/base.yaml` | 실험 설정 원형. 복제해서 모델별 config를 만든다 |
| `datasets/registry.yaml` | `dataset_version`의 정의(출처·SHA256·schema·변환기). 실제로 받은 데이터만 등록 |

이 문서들은 버전(`v0.2` 등)과 변경 이력 표를 갖는다. **내용을 바꾸면 버전을 올리고 이력에 적는다.**

### metadata schema가 유일한 seam

MVTec AD/LOCO, VisA 같은 public benchmark와 자체 benchmark는 원본 구조가 전부 다르다. 이걸
**동일한 JSONL(1 샘플 = 1 row)로 변환**해서 평가 코드를 한 번만 만든다(`docs/adr/0006`).

- 평가 코드는 원본 데이터셋을 몰라야 한다. `metadata.jsonl`만 읽는다.
- 새 데이터셋을 붙이는 비용은 "변환기 1개"로 고정된다.
- public track은 `expected_*`가 비어 있어 Logical 검사가 자동 제외된다.

### 판정과 집계

evaluation 코드를 쓸 때 반드시 지켜야 하는 구조다.

- **3-state**: `OK` / `NG` / `REVIEW`. `REVIEW`는 Escape도 False Reject도 아니고 Review Rate로
  따로 보고한다(`docs/adr/0002`).
- **Primary metric**은 Defect Escape Rate이고 Critical Escape가 실질 최우선이다.
  **Accuracy는 대표 지표로 쓰지 않는다**(`docs/adr/0001`).
- **3-level 집계**: Defect / Label `(unit_id, label_slot)` / Product `unit_id`.
  Product-level은 **하나라도 NG면 NG(severity 무관), NG가 REVIEW보다 우선**(`docs/adr/0003`).
- 비율 지표는 분자·분모와 **Clopper-Pearson 95% 신뢰구간**을 함께 보고한다. escape 0건은
  n이 작으면 아무것도 증명하지 않는다(`docs/adr/0005`).
- Severity는 defect type의 고유 속성이 아니라 **Recipe가 정하는 값**이다. 따라서 Critical Escape
  Rate는 Recipe에 상대적이다(`docs/adr/0004`).

### import 규약

`src/__init__.py`가 있어 **`src` 자체가 패키지**다 — 표준 src-layout이 아니다.

```python
from src.utils.mvtec import load_metadata
```

pytest는 `pythonpath = ["."]`, pyrefly는 `search-path = ["."]`로 같은 규약에 맞춰져 있다.

### 실험 기록

모든 실험은 `experiments/`의 스크립트에서 나오고 로컬 SQLite MLflow에 기록한다
(`docs/adr/0007`). params에 `git_commit` / `dataset_version` / `config_path`를 남기고 config
사본을 artifact로 저장한다. `mlflow.db`와 `mlartifacts/`는 커밋하지 않으므로 **clone해도 실험
이력은 따라오지 않는다** — 인용할 숫자는 `reports/`에 텍스트로 남긴다.
워크트리에서 돌려도 메인 체크아웃의 `mlflow.db`에 기록되고, MLflow UI는 메인 체크아웃에서 실행한다.

## 이 저장소의 규칙

문서에 명시된 것들이다. 어기면 결과가 조용히 무효가 된다.

- 작업은 **이슈 단위로 Orca 워크트리에서** 한다. 이슈 1개 = 워크트리 1개 = 브랜치 1개 = PR 1개. main에 직접 커밋·push하지 않는다. 절차는 `docs/agents/issue-tracker.md`.
- PR은 **merge commit으로** 머지한다(squash·rebase 금지). 커밋 해시가 보존되어야 MLflow `git_commit`과 이슈 댓글의 해시가 유효하다.
- gitignore된 로컬 자원(`datasets/public`, `mlflow.db`, `mlartifacts/`)은 메인 체크아웃에만 있다. 코드는 `src/utils/paths.SHARED_ROOT`로 찾는다.
- 어떤 RQ에도 연결되지 않는 실험은 하지 않는다. 실험 시작 전에 RQ와 Scenario를 먼저 적는다.
- `notebooks/`는 즉흥 탐색 전용이다. **논문·보고서에 인용할 숫자는 `experiments/`에서만** 나온다.
- threshold는 `val`(또는 calibration) split에서 정한다. **`test`로 정하지 않는다.**
- `expected_*` / `actual_*`에 모델 출력을 쓰지 않는다. predicted 값은 실험 결과 파일에 따로 남긴다.
- `unknown_visual`이 붙은 샘플은 **어떤 형태로도** 학습·threshold calibration에 쓰지 않는다.
- 원본 데이터, 모델 weight, `mlflow.db`는 커밋하지 않는다(`.gitignore` 참고).

### Gate 규칙 (기준 문서 §64)

주차별로 다음을 넘지 못하면 진행하지 않는다. 범위를 늘리기 전에 확인한다.

| Gate | 조건 |
|---|---|
| Week 4 | 평가 파이프라인이 완성되기 전에는 **모델을 늘리지 않는다** |
| Week 8 | 기존 모델을 재현하지 못했다면 **신규 모델 개발 금지** |
| Week 12 | 명확한 Research Gap이 없으면 **Proposed Method 개발 금지** |
| Week 16 | baseline 대비 장점이 없으면 복잡도를 늘리지 않고 **방향 수정** |
| Week 20 | **기능 개발 종료.** 실험·Ablation·논문화에 집중 |
| Week 24 | 추가 실험보다 **현재 결과로 논문 초안 완성** |
