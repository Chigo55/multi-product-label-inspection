# multi-product-label-inspection

다품종·다라벨 제조 환경을 위한 **Explainable Hybrid Inspection System** 연구 저장소.

- 기준 문서: [`docs/multi_product_multi_label_industrial_inspection_research_summary.md`](docs/multi_product_multi_label_industrial_inspection_research_summary.md)
- 연구 기간: 24주 (Week 1 시작일 2026-09-12). 2026-10-27에 약 3주 순연 — Week 24 = 2027-03-13 주말 (#69)
- 연구 시간: 주 10~15시간, 주로 주말 / **한 주말 = 하나의 명확한 실험 목표**

---

## Research Goal

> 다품종·다라벨 제조환경에서 **정상 데이터 중심으로 신규 라벨을 적은 샘플만으로 등록**하고,
>
> - **Visual Defect**
> - **Logical Defect**
> - **Unknown Label**
> - **Unknown Defect**
>
> 를 탐지하는 **Explainable Hybrid Inspection System**을 연구한다.

시스템 출력은 `OK / NG`가 아니라 **판정 + 원인 + 근거**다.

```text
Product A
→ Label a-2
→ NG
→ Wrong Label
→ Expected: a-2
→ Detected: b-3
→ Confidence: 98.7%
→ Evidence:
   - Prototype similarity
   - OCR mismatch
   - Product-label rule violation
```

판정이 불확실하면 강제 판정하지 않고 **`REVIEW`** 상태로 보낸다.

---

## 핵심 요구조건

```text
Primary KPI:
Defect Escape Rate / False Negative Rate

Secondary:
False Positive Rate
Unknown Detection
Few-shot Performance
Review Rate
Latency

Latency target:
< 1 second / product

Evaluation:
100 ms / 500 ms / 1000 ms
```

우선순위 (확정):

```text
1. 불량 유출 최소화 (False Negative 최소화)
2. 정상품 과검 최소화 (False Positive)
3. 신규 품목/라벨 추가 편의성
4. 유지보수 편의성
5. 속도
```

속도는 중요하지만 **불량 유출 방지보다 우선하지 않는다.**

---

## Research Questions

6개 RQ 전문은 [`reports/research_questions.md`](reports/research_questions.md).

| RQ | 한 줄 요약 |
|---|---|
| RQ1 | 다수의 제품/라벨을 어떻게 확장성 있게 **식별**할 것인가? |
| RQ2 | 정상 데이터만 많을 때 **Known/Unknown defect**를 어떻게 검출할 것인가? |
| RQ3 | 거의 동일한 라벨을 Context/위치/OCR/Barcode/Visual로 어떻게 **구별**할 것인가? |
| RQ4 | 신규 라벨을 **1/5/10/20/50장**으로 등록하며 재학습을 최소화할 수 있는가? |
| RQ5 | **End-to-End vs Hybrid Pipeline** 중 산업환경에 무엇이 더 적합한가? |
| RQ6 | Escape 최소화 + **1초 이내** + 유지보수성 + Explainability를 동시에 달성 가능한가? |

> 모든 실험은 "이 실험이 어느 RQ에 답하는가?"를 먼저 적고 시작한다.

---

## 저장소 구조

```text
multi-product-label-inspection/
├─ README.md                  ← 연구 목표 / KPI (이 문서)
├─ CONTEXT.md                 ← 용어집 (도메인 언어의 정본)
├─ pyproject.toml             ← 의존성 / 도구 설정 (uv)
├─ uv.lock                    ← 재현용 lockfile (반드시 커밋)
├─ configs/                   ← 실험 설정 (YAML). base.yaml을 복제해서 사용
├─ datasets/
│  ├─ schema.md               ← Dataset Schema v0.2
│  ├─ defect_taxonomy.md      ← Defect Taxonomy + Severity v0.1.1
│  ├─ public/                 ← MVTec AD / LOCO / VisA ... (git에 커밋하지 않음)
│  └─ custom/                 ← 자체 Multi-Product Multi-Label benchmark
├─ src/
│  ├─ models/                 ← 모델 wrapper (PatchCore, EfficientAD, DINOv2 ...)
│  ├─ pipelines/              ← Hybrid pipeline 조립
│  ├─ evaluation/             ← metric / protocol 구현 (Week 4)
│  ├─ xai/                    ← evidence 생성 / 설명
│  └─ utils/
├─ experiments/               ← 실행 스크립트 (재현 가능한 것만)
├─ notebooks/                 ← 즉흥 탐색 전용 (여기 결과는 인용하지 않는다)
├─ reports/
│  ├─ research_questions.md
│  ├─ evaluation_protocol.md
│  ├─ literature/             ← literature matrix + 논문별 요약
│  ├─ weekly/                 ← 주간 연구노트 (WeekNN.md)
│  └─ figures/
├─ tests/
└─ docs/
   ├─ adr/                    ← 되돌리기 어려운 결정 기록
   └─ ...                     ← 연구 기준 문서
```

**운영 규칙**

1. `experiments/`와 `notebooks/`를 섞지 않는다. 논문/보고서에 인용할 숫자는 반드시 `experiments/`에서 나온다.
2. 원본 데이터와 모델 weight는 커밋하지 않는다 (`.gitignore` 참고).
3. 모든 실험은 MLflow에 기록한다: git commit / dataset version / config / metric / latency / artifact.

---

## Quick start

```bash
uv sync

# MLflow 동작 확인 (Week 1)
uv run experiments/week01_mlflow_hello.py

# MLflow UI (http://127.0.0.1:5000)
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlartifacts
```

> Week 1에서는 **로컬 SQLite MLflow**(`mlflow.db` + `mlartifacts/`)만 사용한다. 서버도 Docker도 필요 없다.
> (MLflow 3.x부터 파일 기반 store `./mlruns`는 maintenance mode라 예외를 던진다.)
> 다중 머신을 쓰게 되는 시점에 MLflow Server 도입을 검토한다.

---

## 진행 상황

- **Project board**: https://github.com/users/Chigo55/projects/5
- **Milestones**: Month 1~6 = 기준 문서 §37의 6개 Phase. 각 월 말이 Gate다.
- **이슈 구조**: `[Week N] 주차 메인 이슈` (label `week-main`) → 하위 이슈

| Phase | 기간 | 주차 메인 이슈 |
|---|---|---|
| [Month 1 — 문제·환경 구축](../../milestone/1) | ~2026-10-04 | [#1 Week 1](../../issues/1) · [#7 Week 2](../../issues/7) · [#8 Week 3](../../issues/8) · [#9 Week 4](../../issues/9) |
| [Month 2 — Baseline](../../milestone/2) | ~2026-11-29 | [#10 Week 5](../../issues/10) · [#11 Week 6](../../issues/11) · [#12 Week 7](../../issues/12) · [#13 Week 8](../../issues/13) |
| [Month 3 — 핵심 문제 검증](../../milestone/3) | ~2026-12-20 | [#14 Week 9](../../issues/14) · [#15 Week 10](../../issues/15) · [#16 Week 11](../../issues/16) · [#17 Week 12](../../issues/17) |
| [Month 4 — Proposed Method](../../milestone/4) | ~2027-01-17 | [#18 Week 13](../../issues/18) · [#19 Week 14](../../issues/19) · [#20 Week 15](../../issues/20) · [#21 Week 16](../../issues/21) |
| [Month 5 — Main Experiment](../../milestone/5) | ~2027-02-14 | [#22 Week 17](../../issues/22) · [#23 Week 18](../../issues/23) · [#24 Week 19](../../issues/24) · [#25 Week 20](../../issues/25) |
| [Month 6 — Validation / Paper](../../milestone/6) | ~2027-03-14 | [#26 Week 21](../../issues/26) · [#27 Week 22](../../issues/27) · [#28 Week 23](../../issues/28) · [#29 Week 24](../../issues/29) |

**일정 재조정 (2026-10-27, #69 결정 5).** Week 5 시작 전에 리뷰 후속 P0(#69)을 끝내느라 약 3주 순연했다.
Week 6~7(PatchCore·EfficientAD)은 같은 하네스(Anomalib)로 한 주에, Week 9~10(DINOv2 Prototype·AnomalyDINO)도
한 주에 묶는다. Raspberry Pi 측정과 Human study는 **선택 항목**으로 내린다. 범위 축소는 Week 12 Gate 결과를 보고 정한다.

| 주말 | Week | | 주말 | Week |
|---|---|---|---|---|
| 11-14 | 5 | | 01-16 | 16 (Gate) |
| 11-21 | 6~7 | | 01-23 | 17 |
| 11-28 | 8 (Gate) | | 01-30 | 18 |
| 12-05 | 9~10 | | 02-06 | 19 |
| 12-12 | 11 | | 02-13 | 20 (Feature Freeze) |
| 12-19 | 12 (Gate) | | 02-20 | 21 |
| 12-26 | 13 | | 02-27 | 22 |
| 2027-01-02 | 14 | | 03-06 | 23 |
| 01-09 | 15 | | 03-13 | 24 (논문 초안) |

Week 1~4는 하위 이슈까지 분해되어 있다. Week 5 이후는 메인 이슈에 체크리스트만 있고,
**해당 Phase가 시작될 때 분해**한다 (그 시점의 결과에 따라 내용이 달라지므로).

### Gate 규칙 (기준 문서 §64)

| Gate | 조건 |
|---|---|
| [Week 4](../../issues/9) | 평가 파이프라인이 완성되기 전에는 **모델을 늘리지 않는다** |
| [Week 8](../../issues/13) | 기존 모델을 재현하지 못했다면 **신규 모델 개발 금지** |
| [Week 12](../../issues/17) | 명확한 Research Gap이 없으면 **Proposed Method 개발 금지**. 논문 방향 확정 |
| [Week 16](../../issues/21) | baseline 대비 의미 있는 장점이 없으면 복잡도를 늘리지 않고 **방향 수정** |
| [Week 20](../../issues/25) | **기능 개발 종료.** 실험·Ablation·논문화 집중 |
| [Week 24](../../issues/29) | 추가 실험 욕심보다 **현재 결과로 논문 초안 완성** |
