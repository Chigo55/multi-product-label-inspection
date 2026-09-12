# Research Questions (확정 v1.0)

> 작성일: 2026-09-12 (Week 1)
> 기준 문서: `docs/multi_product_multi_label_industrial_inspection_research_summary.md` §9
>
> **사용법**: 새 실험을 시작하기 전에 "이 실험은 어느 RQ에 답하는가?"를 먼저 적는다.
> 어떤 RQ에도 연결되지 않는 실험은 이번 24주 범위에서 하지 않는다.

---

## RQ1 — Scalable Label Identity

> **다수의 제품/라벨을 어떻게 확장성 있게 식별할 것인가?**

수십~수백 개의 label identity를, class가 계속 늘어나는 조건에서 하나의 시스템이 식별해야 한다.

- **왜 중요한가**: 제품/라벨이 추가될 때마다 전체 classifier를 재학습하는 구조는 현장에서 유지되지 않는다.
- **후보 기술**: DINOv2 embedding / Prototype learning / Metric learning / Retrieval / Open-set recognition
- **검증 실험**: E1 (Seen Label), E5 (Similar Label)
- **성공 기준(잠정)**: label identity accuracy, class 수 증가에 따른 성능 저하 곡선, prototype DB 크기·검색 latency
- **관련 주차**: Week 9 (DINOv2 Prototype Retrieval)

---

## RQ2 — Normal-only Known/Unknown Defect Detection

> **정상 데이터는 많고 불량 데이터가 매우 적을 때 Known/Unknown defect를 어떻게 검출할 것인가?**

- **왜 중요한가**: 실제 라인에서 불량은 희소하고, 학습 시점에 존재하지 않는 불량이 반드시 나타난다.
  supervised defect classification만으로는 구조적으로 부족하다.
- **후보 기술**: PatchCore / EfficientAD / AnomalyDINO / Dinomaly / INP-Former
- **검증 실험**: E1 (Seen Defect), E4 (Unknown Defect)
- **성공 기준(잠정)**: Defect Escape Rate, Critical Escape Rate, AUPRC, **seen vs unseen defect 성능 격차**
- **관련 주차**: Week 6 (PatchCore), Week 7 (EfficientAD), Week 10 (AnomalyDINO)

---

## RQ3 — Distinguishing Near-identical Labels

> **시각적으로 매우 유사한 라벨을 Product Context, 위치, OCR, Barcode, Visual Feature를 이용해 어떻게 구별할 것인가?**

그리고 **그 판단 근거를 작업자에게 어떻게 설명할 것인가?**

- **왜 중요한가**: 외형이 동일하고 문자 한두 글자 또는 barcode 내용만 다른 라벨이 존재한다.
  순수 visual embedding만으로는 원리적으로 분리 불가능한 구간이 있다.
- **후보 기술**: 제품 context(MES/Recipe) / ROI 기하 검증 / OCR field rule / Barcode decode / visual prototype
- **검증 실험**: E5 (Similar Label — Easy / Medium / Hard / Extreme)
- **성공 기준(잠정)**: 난이도 구간별 confusion rate, modality별 기여도(ablation), evidence 정확도
- **관련 주차**: Week 12 (Logical Inspection), Week 15 (Evidence-based XAI)

---

## RQ4 — Few-shot New Label Onboarding

> **신규 라벨을 1/5/10/20/50개의 정상 이미지로 등록하면서 전체 재학습을 최소화할 수 있는가?**

- **왜 중요한가**: 신규 품목 추가 주기가 짧다. 재학습 없는 등록(Training-free)이 목표 방향이다.
- **후보 기술**: Training-free / Few-shot / Prototype / Embedding retrieval / Reference bank
- **검증 실험**: E2 (Few-shot New Label)
- **성공 기준(잠정)**: shot 수별 성능 곡선, **new-label onboarding cost**(시간/연산/사람 개입), 기존 라벨 성능 무손상 여부
- **관련 주차**: Week 9, Week 10

---

## RQ5 — End-to-End vs Hybrid Pipeline

> **End-to-End와 Hybrid Pipeline 중 실제 산업환경에서 어느 방식이 더 적합한가?**

- **왜 중요한가**: 정확도만이 아니라 유지보수·감사(auditability)·추적(traceability)·신규 품목 추가성까지 포함해 비교해야 실제 답이 나온다.
- **비교 항목**: 정확도 / 불량 유출률 / 신규 품목 추가성 / 유지보수성 / Explainability / Auditability / Traceability / Latency
- **비교 대상**: Architecture A(Classical) / B(Standard DL) / C(Foundation·Few-shot Hybrid) / D(Unified Model)
- **검증 실험**: E1~E6 전체 + Ablation
- **관련 주차**: Week 5, Week 13, Week 16, Week 21

---

## RQ6 — Escape × Latency × Maintainability × Explainability

> **Defect Escape를 최소화하면서 1초 이내 latency, 유지보수성, Explainability를 동시에 확보할 수 있는가?**

- **왜 중요한가**: 네 축은 서로 상충한다. 어디까지 동시에 만족 가능한지가 이 연구의 실질적 결론이다.
- **측정**: 전체 pipeline latency P50/P95/P99 (모델 inference만이 아님), 구간별 breakdown
- **검증 실험**: 전체 pipeline + Edge (Jetson Nano / Raspberry Pi)
- **성공 기준(잠정)**: Critical Escape 목표치 하에서 P95 < 1000 ms 달성 여부와 그때의 REVIEW rate
- **관련 주차**: Week 13, Week 14, Week 23

---

## RQ ↔ 실험 시나리오 매핑

| | E1 Seen | E2 Few-shot | E3 Unknown Label | E4 Unknown Defect | E5 Similar Label | E6 Domain Shift |
|---|---|---|---|---|---|---|
| RQ1 | ● | ○ | ● | | ● | ○ |
| RQ2 | ● | ○ | | ● | | ○ |
| RQ3 | ○ | | ○ | | ● | ○ |
| RQ4 | | ● | ○ | ○ | | |
| RQ5 | ● | ● | ● | ● | ● | ● |
| RQ6 | ● | ○ | ○ | ○ | ○ | ● |

● 주 검증 / ○ 보조 검증

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-09-12 | RQ1~RQ6 확정, 실험 매핑 추가 |
