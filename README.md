# multi-product-label-inspection

다품종·다라벨 제조 환경을 위한 **Explainable Hybrid Inspection System** 연구 저장소.

- 기준 문서: [`docs/multi_product_multi_label_industrial_inspection_research_summary.md`](docs/multi_product_multi_label_industrial_inspection_research_summary.md)
- 연구 기간: 24주 (Week 1 시작일 2026-09-12)
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
├─ requirements.txt
├─ configs/                   ← 실험 설정 (YAML). base.yaml을 복제해서 사용
├─ datasets/
│  ├─ schema.md               ← Dataset Schema v0.1
│  ├─ defect_taxonomy.md      ← Defect Taxonomy + Severity v0.1
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
└─ docs/                      ← 연구 기준 문서
```

**운영 규칙**

1. `experiments/`와 `notebooks/`를 섞지 않는다. 논문/보고서에 인용할 숫자는 반드시 `experiments/`에서 나온다.
2. 원본 데이터와 모델 weight는 커밋하지 않는다 (`.gitignore` 참고).
3. 모든 실험은 MLflow에 기록한다: git commit / dataset version / config / metric / latency / artifact.

---

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# MLflow 동작 확인 (Week 1)
.venv/bin/python experiments/week01_mlflow_hello.py

# MLflow UI (http://127.0.0.1:5000)
.venv/bin/mlflow ui --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlartifacts
```

> Week 1에서는 **로컬 SQLite MLflow**(`mlflow.db` + `mlartifacts/`)만 사용한다. 서버도 Docker도 필요 없다.
> (MLflow 3.x부터 파일 기반 store `./mlruns`는 maintenance mode라 예외를 던진다.)
> 다중 머신을 쓰게 되는 시점에 MLflow Server 도입을 검토한다.

---

## 진행 상황

| 주차 | 목표 | 상태 |
|---|---|---|
| Week 1 | Research Protocol (repo / MLflow / schema / metric / literature matrix) | 진행 중 |
| Week 2 | Dataset Schema & Benchmark Design | - |
| Week 3 | Pilot Benchmark + Synthetic defect generator | - |
| Week 4 | Evaluation Pipeline (**Month 1 Gate**) | - |

전체 24주 로드맵은 기준 문서 §37~§61 참고.

**Gate 규칙**: 평가 파이프라인이 완성되기 전에는 모델 수를 늘리지 않는다.
