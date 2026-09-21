# Week 01 — Research Protocol

- 기간: 2026-09-12 (토) ~ 2026-09-13 (일)
- 주제: **모델을 돌리는 주가 아니라, 앞으로 24주 실험을 반복할 수 있는 연구 기반을 만드는 주**
- 이번 주 목표: Research Repository + 실험 추적 환경 + 연구 명세 완성

---

## Question

> 이번 주에 무엇을 검증했나?

모델 성능이 아니라 **인프라**를 검증했다.

1. 모든 실험이 통과할 기록 경로(config → run → param → metric → artifact → UI)가 실제로 동작하는가?
2. 앞으로 6개월간 바뀌지 않을 **측정 기준(Primary Metric)** 과 **데이터 스키마**를 지금 고정할 수 있는가?

---

## Experiment / 산출물

| 항목 | 결과 | 파일 |
|---|---|---|
| Repository 구조 | 완료 | (repo root) |
| 연구 목표 / KPI | 완료 | `README.md` |
| RQ1~RQ6 + 실험 매핑 | 완료 | `reports/research_questions.md` |
| Dataset Schema **v0.2** | 완료 (v0.1 26필드 → `unit_id`·`defects[]` 추가, `label_id`→`label_slot`) | `datasets/schema.md` |
| Defect Taxonomy **v0.1.1** | 완료 (VISUAL 9 + LOGICAL 8 + Severity 3, 정본 용어 `visual`로 통일) | `datasets/defect_taxonomy.md` |
| Evaluation Protocol **v0.2** | 완료 (Primary = Defect Escape Rate, Product-level 집계 규칙 확정) | `reports/evaluation_protocol.md` |
| 실험 Config 형식 | 완료 (YAML 파싱 검증 통과) | `configs/base.yaml` |
| MLflow 최소 동작 | **완료 — run 기록 및 UI 조회 확인** | `experiments/week01_mlflow_hello.py` |
| Literature Matrix | 완료 (Tier 1 논문 10편 등록) | `reports/literature/literature_matrix.md` |
| MVTec LOCO AD 정리 | 사전 정리 초안 작성 (원문 확인 필요) | `reports/literature/mvtec_loco_ad.md` |
| PatchCore 정리 | 사전 정리 초안 작성 (원문 확인 필요) | `reports/literature/patchcore.md` |

### 계획 외 추가 산출물

Week 1 체크리스트에는 없었지만, 다음 주부터 코드를 쓰려면 먼저 있어야 해서 함께 만들었다.

| 항목 | 내용 | 파일 |
|---|---|---|
| 개발 도구 체인 | pip+requirements → **uv** 전환. pytest 9.1.1 / ruff 0.16.7 / pyrefly 1.3.0 | `pyproject.toml`, `uv.lock` |
| 용어집 | 24개 용어. Product Unit↔Product Type, Label Slot↔Label Identity 분리, Inspection Recipe 정의 | `CONTEXT.md` |
| ADR | 되돌리기 어려운 결정 7건 기록 | `docs/adr/0001`~`0007` |
| 에이전트 규약 | 이슈 트래커·triage 라벨·도메인 문서 위치, 실행/아키텍처 가이드 | `docs/agents/`, `CLAUDE.md` |

> `ty`(Astral)도 검토했으나 도입 시점에 0.0.80이라 제외하고 pyrefly 1.3.0을 썼다.
> `ruff format`이 black을 대체하므로 black은 설치하지 않는다.

### MLflow 검증 결과

```text
experiment : week01_test
run_id     : 60082991751c4f4e833435dbac679bcc
params     : model=none, dataset=pilot, seed=42, git_commit=d47bfba, primary_metric=defect_escape_rate
metrics    : dummy_f1 = 0.5
artifacts  : config/base.yaml, summary/_week01_summary.json
UI         : http://127.0.0.1:5000 (HTTP 200, run 조회 확인)
```

---

## Result / 결정 사항

1. **Primary Metric = Defect Escape Rate (= FN / Actual Defects).** Accuracy는 대표 지표로 쓰지 않는다.
   실질적 최우선은 **Critical Defect Escape Rate**.
2. **REVIEW 집계 규칙 확정** — REVIEW는 escape가 아니고 false reject도 아니다. 별도 비용 지표(Review Rate)로 본다.
   (이 규칙을 지금 정하지 않으면 나중에 모든 표의 숫자가 섞인다.)
3. **Threshold는 test set에서 정하지 않는다.** val/calibration split 전용.
4. **`reference` split을 `train`과 분리**했다. RQ4에서 shot 수(1/5/10/20/50)를 바꿔 샘플링해야 하기 때문.
5. **MLflow는 로컬 SQLite(`mlflow.db`) 백엔드 사용.**
   MLflow 3.x부터 파일 기반 store(`./mlruns`)가 maintenance mode로 예외를 던진다.
   Docker/서버 없이 로컬만으로 동작하므로 Week 1 취지는 그대로 유지.
6. **`experiments/`와 `notebooks/`를 분리.** 보고서에 인용할 숫자는 반드시 `experiments/`에서 나온다.
7. **Product-level 집계 규칙 확정** — 라벨 중 **하나라도 NG면 제품 NG**(severity 무관), NG가 REVIEW보다 우선.
   기존의 "CRITICAL만 제품 NG" 규칙은 찢어진 라벨(MAJOR NG)이 붙은 제품을 Product-level에서
   정상으로 집계하는 결함이 있었다.
8. **Product Unit을 명시적 키(`unit_id`)로 도입.** v0.1에는 여러 라벨·카메라 row를 한 물리 제품으로
   묶는 키가 없어 **Level 3 계산이 원리적으로 불가능했다.** 함께 `label_id`가 `actual_label_id`와
   값이 중복이라 **`label_slot`(라벨 자리)** 으로 재정의했다.
9. **Severity는 defect type의 고유 속성이 아니라 Recipe가 정하는 값.**
   따라서 Critical Escape Rate는 Recipe에 상대적이며, Recipe가 다른 데이터셋끼리 나란히 비교할 수 없다.
10. **의존성 관리를 uv로 전환하고 `uv.lock`을 커밋.** 재현성을 git commit + YAML config + lockfile
    세 축으로 고정한다.
11. **용어와 결정을 문서로 분리.** 용어의 정본은 `CONTEXT.md`, 되돌리기 어려운 결정은 `docs/adr/`.
    이전에는 결정이 주간 연구노트에만 남아 있어 12주 뒤에 찾을 수 없는 상태였다.
12. 환경 특이사항: **이 개발 머신에는 GPU가 없다**(`nvidia-smi` 실패). torch는 아직 설치하지 않았다.
    Week 5~6 baseline 학습 전에 GPU 환경을 확정해야 한다.

---

## 이번 주 체크리스트

- [x] Git Repository 생성
- [x] 프로젝트 폴더 구조
- [x] README 연구 목표
- [x] RQ1~RQ6
- [x] Dataset Schema (v0.1 → **v0.2**)
- [x] Defect Taxonomy
- [x] Evaluation Protocol (v0.1 → **v0.2**)
- [x] `base.yaml`
- [x] MLflow 최소 동작
- [x] Literature Matrix
- [ ] MVTec LOCO AD 정리 ← 초안 있음, **원문 훑고 확정**
- [ ] PatchCore 정리 ← 초안 있음, **원문 훑고 확정**
- [ ] Public dataset 하나 읽기 성공 (내일)
- [x] `Week01.md` 연구노트
- [x] (추가) uv 전환 + pytest/ruff/pyrefly
- [x] (추가) `CONTEXT.md` 용어집 + ADR 7건

---

## 내일(일요일) 할 일

기준 문서 §39 Week 2로 넘어가기 전에, 오늘 만든 구조 위에서 **데이터가 실제로 흐르는지** 확인한다.

```text
MVTec AD 다운로드
↓
데이터 읽기 (이미지 1장 열기 성공)
↓
Train/Test sample 목록 출력
↓
datasets/schema.md v0.2 형식으로 metadata 변환 (metadata.jsonl 생성)
↓
evaluation code 연결 지점 확인
```

- 구현 위치: `src/utils/mvtec.py` (loader) + `experiments/week02_mvtec_smoke.py`
- 검증 기준: MVTec AD 1개 category를 **schema v0.2** JSONL로 변환하고, normal/defect 개수를 출력한다.
  v0.2이므로 `unit_id`를 채우고 `label_slot`은 `-`로 둔다 (MVTec은 제품당 라벨 1개).
- 테스트가 가능해졌다. loader는 `tests/`에 테스트를 먼저 쓰고 `uv run pytest`로 돌린다.
- **주의**: MVTec AD 데이터셋 라이선스(상업적 이용 조건)를 다운로드 시점에 확인해서 matrix에 기록한다.

---

## 세 줄 정리

```text
이번 주에 결정한 것:
Primary Metric을 Defect Escape Rate(+Critical Escape)로 고정하고, REVIEW를 escape/false reject와
분리해 집계하기로 했다. Dataset Schema와 Defect Taxonomy(VISUAL 9 / LOGICAL 8 / Severity 3)를
확정했고, 실험 기록은 로컬 SQLite MLflow + YAML config + git commit + uv.lock으로 고정했다.
스키마를 검토하다 Product-level 집계 키(`unit_id`)가 없어 Level 3 계산이 불가능하다는 걸 발견해
v0.2로 올렸고, 결정들을 주간 노트가 아니라 `CONTEXT.md`와 `docs/adr/`로 옮겼다.

아직 불확실한 것:
(1) GPU 환경이 없다 — Week 5~6 baseline 전에 확정 필요.
(2) MVTec AD/LOCO 및 DINOv2 weights의 상업적 이용 라이선스 미확인.
(3) PatchCore류를 30~60개 label identity로 확장할 때의 memory/latency 비용이 미지수.
(4) 자체 benchmark를 synthetic으로 어디까지 만들 수 있는지(특히 OCR/Barcode-only 차이) 미검증.

다음 주말 첫 번째 할 일:
MVTec AD 1개 category를 내려받아 schema v0.2 형식의 metadata.jsonl로 변환하고,
normal/defect 샘플 수를 출력하는 loader(`src/utils/mvtec.py`)를 만든다. (→ issue #4)
```
