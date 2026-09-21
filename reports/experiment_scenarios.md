# Experiment Scenarios v0.1 (초안)

> 작성일: 2026-09-21 (Week 2) / 이슈: #31
> 기준 문서: `docs/multi_product_multi_label_industrial_inspection_research_summary.md` §30
> RQ 매핑: `reports/research_questions.md` / 지표 정의: `reports/evaluation_protocol.md` / 분할: `datasets/schema.md` §4
>
> ⚠️ **초안이다.** 성공 기준은 전부 **제안**이고, `[결정]` 표시 항목은 연구자가 확정한다.
> 모든 실험은 시작 전에 이 문서의 Scenario ID(`E1`~`E6`)와 RQ를 config에 적는다.

## 공통 규칙

- threshold는 `val`에서만 정한다. `test`는 보고 전용이다.
- 비율 지표는 분자/분모 + Clopper-Pearson 양측 95% 구간을 함께 보고한다 (ADR 0005).
- 3-level(Defect / Label / Product)로 보고한다. public track은 Label = Product다.
- 랜덤성이 있으면(few-shot 샘플링 등) 최소 3 seed, 평균 ± 표준편차.
- "escape 0건"을 주장하려면 표본이 먼저 있어야 한다. 0건일 때 95% 상한이 **5% 이하면 72건, 1% 이하면 368건** 이상 필요하다.

## 요약

| ID | 질문 | 주 RQ | 데이터 | 핵심 분할 | 주 지표 | 가능 시점 |
|---|---|---|---|---|---|---|
| **E1** Seen Label | 등록된 라벨의 알려진 불량을 잡는가 | RQ1, RQ2, RQ6 | Public(MVTec AD, VisA) + Pilot | 표준 train/val/test | DER, CDER, FPR, AUPRC, Review Rate, P95 latency | Week 5~ (public) |
| **E2** Few-shot New Label | 정상 1/5/10/20/50장으로 새 라벨을 온보딩할 수 있는가 | RQ4 | Pilot/Main (신규 라벨 hold-out). public은 MVTec few-shot 설정 | `reference`에서 k-shot 샘플링 | shot별 DER·Known Label Accuracy, 기존 라벨 성능 변화, onboarding cost | Week 9~10 |
| **E3** Unknown Label | 미등록 라벨을 기존 라벨로 오인하지 않는가 | RQ1 | Pilot/Main | Unknown 라벨은 `test`에만 | Unknown Label Detection Rate, 억지 분류 건수 | Week 11 |
| **E4** Unknown Defect | 본 적 없는 불량 유형도 잡는가 | RQ2 | Public(MVTec AD 결함 유형 hold-out) + synthetic | Unknown 유형은 calibration에서 제외 | seen vs unseen DER 격차 | Week 6~ |
| **E5** Similar Label | 거의 같은 라벨을 구별하는가 | RQ3, RQ1 | Pilot/Main (#35 난이도 구간) | 난이도별 `test` subset | 난이도별 Similar-label Confusion Rate, modality ablation | Week 12 |
| **E6** Domain Shift | 조명·LOT·카메라가 바뀌어도 버티는가 | RQ6, RQ2 | Public(후보: MVTec AD 2, VisA) + Pilot 촬영 조건 변경 | shift 요인별 `test` subset | in-domain 대비 DER/FPR 변화량 | Week 17~ |

> 현재 받아 둔 데이터(MVTec AD)로 바로 할 수 있는 것은 **E1, E4**다. E2는 public few-shot 설정으로 일부 가능하고,
> E3·E5는 자체 benchmark(#33~#35)가 있어야 한다.

---

## E1 — Seen Label

- **입력**: 등록된 Label Identity의 정상 + Known defect 이미지.
- **분할**: `train`(정상) / `val`(calibration) / `test`. public은 schema §4.3의 안 A/B 중 확정안을 따른다.
- **지표**: DER(primary), CDER(Recipe가 있는 track만), FPR, Review Rate, AUPRC, AUROC(선행 연구 비교용),
  제품 1개당 P50/P95/P99 latency.
- **성공 기준 (제안)**: FPR 상한 `[결정]`을 지키면서 DER 최소. Pilot에서 CDER 0건이면 상한과 n을 함께 보고한다.
  P95 < 1000 ms (RQ6 1차 목표).
- **주의**: public track은 CDER이 N/A다 (schema §3.1).

## E2 — Few-shot New Label

- **입력**: 신규 라벨 1개당 정상 reference k장 (k ∈ 1, 5, 10, 20, 50). 기존 라벨은 E1과 같다.
- **분할**: 신규 라벨의 reference는 `reference` split에서 샘플링한다. reference와 test는 unit·LOT가 겹치지 않는다 (schema §4.2).
- **지표**: shot별 DER / Known Label Accuracy 곡선, **신규 라벨 추가 전후 기존 라벨의 E1 지표 변화**,
  New-label onboarding cost(사람 시간 + 이미지 수 + 연산 시간, 재학습 여부).
- **성공 기준 (제안)**: 기존 라벨 성능 저하가 신뢰구간 안에 있다. E1 수준에 도달하는 최소 k `[결정: 목표 k]`.
- **주의**: seed ≥ 3. 샘플링한 reference 목록을 artifact로 남긴다.

## E3 — Unknown Label

- **입력**: prototype을 만들지 않은 라벨(`is_known_label=false`)을 test에 섞는다.
- **분할**: Unknown 라벨은 `test`에만 둔다. `reference`·`val`에 들어가면 안 된다 (schema §4.2-3).
- **지표**: Unknown Label Detection Rate, Open-set 3-state(`KNOWN_EXPECTED`/`KNOWN_WRONG`/`UNKNOWN`) 정확도,
  **Unknown을 기존 라벨로 억지 분류한 건수를 별도 실패 유형으로** 집계.
- **성공 기준 (제안)**: 억지 분류 0건 + 상한 보고. Detection Rate 목표 `[결정]`.

## E4 — Unknown Defect

- **입력**: 설계 시점에 없던 불량 유형(`is_known_defect=false`, `unknown_visual`).
- **분할**: Unknown 유형은 threshold calibration에서 뺀다 → `test`에만 둔다.
  public은 MVTec AD의 결함 폴더 일부를 hold-out해서 만든다 `[결정: category별 hold-out 방식]`.
- **지표**: seen defect DER vs unseen defect DER, 둘의 차이와 각각의 신뢰구간.
- **성공 기준 (제안)**: unseen DER의 상한이 seen DER과 같은 수준이다 (구간이 겹친다).
- **주의**: normal-only 모델은 학습 때 불량을 보지 않는다. 그래서 Known/Unknown 구분은 **calibration에서 본 적이 있는가**로 정의된다.

## E5 — Similar Label

- **입력**: 의도적으로 유사하게 만든 라벨 쌍. 난이도 4구간은 기준 문서 §30을 따른다.

  | 난이도 | 정의 |
  |---|---|
  | Easy | 외형이 완전히 다르다 |
  | Medium | Layout이 같다 |
  | Hard | 문자 한두 글자만 다르다 |
  | Extreme | Barcode/OCR 내용만 다르다 |

- **분할**: 난이도별 test subset을 `experiment_tags`(`E5-easy` … `E5-extreme`)로 표시한다.
- **지표**: 난이도별 Similar-label Confusion Rate, modality ablation(visual only → +OCR → +Barcode → +Context).
- **성공 기준 (제안)**: Extreme 구간에서 visual only는 구별하지 못하고 OCR/Barcode를 더하면 구별한다 — 가설 검증형.

## E6 — Domain Shift

- **입력**: 학습 조건과 다른 Lighting / Production LOT / Position / Rotation / Camera / Background / Reflection / Blur.
- **분할**: shift 요인별 test subset(`E6-lot`, `E6-light` …). **threshold는 in-domain `val` 값을 재조정 없이 쓴다** (schema §4.4).
- **지표**: 요인별 DER·FPR과 in-domain 대비 변화량. Review Rate 변화.
- **성공 기준 (제안)**: 요인별 DER 증가량 상한 `[결정]`. 증가가 크면 REVIEW로 흡수되는지(escape로 새지 않는지) 본다.
- **주의**: 조명·배경·반사는 schema에 전용 필드가 없다 (schema §4.4 `[결정]`).

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-09-21 | 초안. E1~E6별 입력 / 분할 / 지표 / 성공 기준(제안) / 대응 RQ |
