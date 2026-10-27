# Experiment Scenarios v1.5

> 작성일: 2026-09-21 (Week 2) / 최종 수정: 2026-10-27 / 이슈: #31, #33, #34, #35, #69
> 기준 문서: `docs/multi_product_multi_label_industrial_inspection_research_summary.md` §30
> RQ 매핑: `reports/research_questions.md` / 지표 정의: `reports/evaluation_protocol.md` / 분할: `datasets/schema.md` §4
>
> 성공 기준의 **형태는 확정**이다. `[시작 시 확정]` 표시 숫자만 해당 시나리오를 시작할 때 정한다.
> 모든 실험은 시작 전에 이 문서의 Scenario ID(`E1`~`E6`)와 RQ를 config에 적는다.

## 공통 규칙

- threshold는 `val` 정상 score 분위수로 정한다 (evaluation_protocol §6). `test`는 보고 전용이다.
- 비율 지표는 분자/분모 + Clopper-Pearson 양측 95% 구간을 함께 보고한다 (ADR 0005).
- 3-level(Defect / Label / Product)로 보고한다. public track은 Label = Product다.
- 랜덤성이 있으면(few-shot 샘플링 등) 최소 3 seed, 평균 ± 표준편차.
- **Week 5~16 보고 수치와 실패 분석(Failure Gallery, Research Gap)은 `pilot_dev`에서 낸다.** `pilot`의 test는 봉인이고
  (registry `test_sealed`), config `experiment.final_report: true`일 때만 열린다 — 첫 개봉 Week 18 (#69 T9).
  `pilot_dev`는 같은 Recipe·변환기로 seed 네임스페이스(`custom_pilot_dev/`)와 LOT만 다르게 만든 세트다.
- "escape 0건"을 주장하려면 표본이 먼저 있어야 한다. 0건일 때 95% 상한이 **5% 이하면 72건, 1% 이하면 368건** 이상 필요하다.

## 요약

| ID | 질문 | 주 RQ | 데이터 | 핵심 분할 | 주 지표 | 가능 시점 |
|---|---|---|---|---|---|---|
| **E1** Seen Label | 등록된 라벨의 알려진 불량을 잡는가 | RQ1, RQ2, RQ6 | Public(MVTec AD, VisA) + Pilot | 표준 train/val/test | DER, CDER, FPR, AUPRC, Review Rate, P95 latency | Week 5~ (public) |
| **E2** Few-shot New Label | 정상 1/5/10/20/50장으로 새 라벨을 온보딩할 수 있는가 | RQ4 | Pilot/Main (신규 라벨 hold-out). public은 MVTec few-shot 설정 | `reference`에서 k-shot 샘플링 | shot별 DER·Known Label Accuracy, 기존 라벨 성능 변화, onboarding cost | Week 9~10 |
| **E3** Unknown Label | 미등록 라벨을 기존 라벨로 오인하지 않는가 | RQ1 | Pilot/Main | Unknown 라벨은 `test`에만 | Unknown Label Detection Rate, 억지 분류 건수 | Week 11 |
| **E4** Unknown Defect | 본 적 없는 불량 유형도 잡는가 | RQ2 | Pilot synthetic (public은 결함 유형별 DER만) | Unknown 유형은 calibration에서 제외 | seen vs unseen DER 격차 | Week 6~ (public 유형별), Pilot 이후 |
| **E5** Similar Label | 거의 같은 라벨을 구별하는가 | RQ3, RQ1 | Pilot/Main (#35 난이도 구간) | 난이도별 `test` subset | 난이도별 Similar-label Confusion Rate, modality ablation | Week 12 |
| **E6** Domain Shift | 조명·LOT·카메라가 바뀌어도 버티는가 | RQ6, RQ2 | Public(후보: MVTec AD 2, VisA) + Pilot 촬영 조건 변경 | shift 요인별 `test` subset | in-domain 대비 DER/FPR 변화량 | Week 17~ |

> 현재 받아 둔 데이터(MVTec AD)로 바로 할 수 있는 것은 **E1과 결함 유형별 DER**이다. E2는 public few-shot 설정으로 일부 가능하다.
> E3는 Pilot benchmark(#33)의 미등록 라벨 row로, E4의 seen/unseen 비교는 synthetic defect(#34)로, E5는 난이도 구간(#35)으로 가능해졌다.

## 평가 범위

시나리오마다 test를 아래 범위로 잘라 따로 평가한다(ADR 0008, evaluation_protocol §4). **unit 단위로 고르고 한 unit의
row를 쪼개지 않는다.** 코드 정본은 `src/evaluation/scenarios.py`이고, MLflow 지표 이름에 `e1_` … 접두사가 붙는다.

| ID | 범위에 드는 unit | 쓰는 결과 |
|---|---|---|
| E1 | 미등록 라벨이 없고 모든 row가 `is_known_defect=true`이며 덧붙인 unit(`E5`·`GEOM-boundary`·`OCR-confusable` 태그)이 아닌 unit | F 판단, 헤드라인 DER·CDER·FPR·Review Rate |
| E3 | 미등록 라벨(`is_known_label=false`)이 하나라도 있는 unit | Unknown Label OK Rate, Detection·Forced Rate |
| E4 | 미등록 라벨이 없고 덧붙인 unit이 아닌 unit — E1에 hold-out 유형 unit을 더한 것. hold-out 유형이 하나도 없으면(public) 비운다 | 유형별 DER로 seen vs unseen |
| E5 | `E5-<구간>` 태그 row가 있는 unit (무작위 바꿔치기 + 전용 unit + `revision_mismatch`) | 구간별 Similar-label Confusion Rate |
| `GEOM-boundary` | 위치·각도가 허용 오차의 0.9~1.2배인 경계 unit (Pilot v0.4, test). 정답은 실제 값 — 정상과 불량이 섞인다 | 경계에서 DER·FPR·Review Rate (REVIEW가 하는 일) |
| `OCR-confusable` | 혼동 문자(0/O, 1/I, 5/S, 8/B, 2/Z, 6/G) 치환 `ocr_mismatch` unit (Pilot v0.4, test) | OCR이 실제로 틀리는 글자에서의 DER |

- 덧붙인 unit(E5 전용, `GEOM-boundary`, `OCR-confusable`)은 E1에서 뺀다 — 넣으면 E1의 불량 구성이 그쪽으로 쏠린다.
  무작위로 생긴 바꿔치기와 `revision_mismatch`(유형당 72 unit, 다른 유형과 같은 수)는 E1에 남는다.
- public track은 `is_known_label`이 비어 있고 태그가 없으므로 전부 E1이다. 범위가 빈 시나리오는 결과에 없다.
- E2·E6는 해당 데이터(reference k-shot, shift subset)가 생길 때 범위를 추가한다.

---

## E1 — Seen Label

- **입력**: 등록된 Label Identity의 정상 + Known defect 이미지.
- **분할**: `train`(정상) / `val`(calibration) / `test`. public은 train 정상 20%를 val로 뗀다 (schema §4.3).
- **지표**: DER(primary), CDER(Recipe가 있는 track만), FPR, Review Rate, AUPRC, AUROC(선행 연구 비교용),
  제품 1개당 P50/P95/P99 latency.
- **성공 기준**: **제품 단위 과검률 목표 F를 먼저 정하고**, 라벨 단위 f = 1 − (1 − F)^(1/L)로 역산해
  calibration에 쓴다 (L = 제품당 라벨 수. public은 L=1, f=1%). 그 조건에서 DER 최소.
  CDER 0건이면 상한과 n을 함께 보고한다. P95 < 1000 ms (RQ6 1차 목표).
  **Pilot의 F = 1%** (#33 확정). 정본은 Recipe `configs/recipes/pilot.yaml`의
  `product_false_reject_target`이고, 제품별 L에서 f를 역산한다 — A·B(L=3) f=0.334%, C(L=4) f=0.251%.
  분위수 해상도를 확보하려고 val 정상을 제품당 360~480 row로 잡았다.
- **주의**: public track은 CDER이 N/A다 (schema §3.1).

## E2 — Few-shot New Label

- **입력**: 신규 라벨 1개당 정상 reference k장 (k ∈ 1, 5, 10, 20, 50). 기존 라벨은 E1과 같다.
- **분할**: 신규 라벨의 reference는 `reference` split에서 샘플링한다. reference와 test는 unit·LOT가 겹치지 않는다 (schema §4.2).
- **지표**: shot별 DER / Known Label Accuracy 곡선, **신규 라벨 추가 전후 기존 라벨의 E1 지표 변화**,
  New-label onboarding cost(사람 시간 + 이미지 수 + 연산 시간, 재학습 여부).
- **성공 기준**: **목표 k = 10장, 도전 목표 5장.** 그 shot 수에서 신규 라벨의 DER이 E1 수준(신뢰구간 겹침)에
  도달하고, 신규 라벨 추가 후 기존 라벨의 E1 지표 저하가 신뢰구간 안에 있다.
- **주의**: seed ≥ 3. 샘플링한 reference 목록을 artifact로 남긴다.

## E3 — Unknown Label

- **입력**: prototype을 만들지 않은 라벨(`is_known_label=false`)을 test에 섞는다.
- **분할**: Unknown 라벨은 `test`에만 둔다. `reference`·`val`에 들어가면 안 된다 (schema §4.2-3).
- **지표**: Unknown Label Detection Rate, Open-set 3-state(`KNOWN_EXPECTED`/`KNOWN_WRONG`/`UNKNOWN`) 정확도,
  **Unknown을 기존 라벨로 억지 분류한 건수를 별도 실패 유형으로** 집계.
- **성공 기준**: **Unknown 라벨이 `OK`로 판정된 건수 0 (상한과 n 보고).** 등록되지 않은 라벨이 붙은 제품은
  출하되면 안 되므로 escape와 같은 성격으로 본다. Detection Rate와 Review Rate 증가는 보조 지표로 보고한다.

## E4 — Unknown Defect

- **입력**: 설계 시점에 없던 불량 유형(`is_known_defect=false`, `unknown_visual`).
- **분할**: Unknown 유형은 threshold calibration에서 뺀다 → `test`에만 둔다.
  **public track은 calibration이 정상만 쓰므로(schema §4.3) 모든 불량이 unseen이다 — seen/unseen 비교가 성립하지 않는다.**
  public에서는 **결함 유형별 DER**(어떤 유형이 새는가)만 보고하고, seen vs unseen 비교는 Pilot의 synthetic 불량으로 한다
  (일부 유형을 calibration에 쓰고 나머지를 hold-out).
- **지표**: seen defect DER vs unseen defect DER, 둘의 차이와 각각의 신뢰구간.
- **성공 기준** (Pilot): unseen DER의 신뢰구간이 seen DER과 겹친다.
- **Pilot 구성** (#34): 본 유형 9종은 val에 제품당 8 unit씩, hold-out `unknown_visual`(인쇄 줄무늬 탈락)은 test에만. 유형마다 test 72 unit
- **주의**: normal-only 모델은 학습 때 불량을 보지 않는다. 그래서 Known/Unknown 구분은 **calibration에서 본 적이 있는가**로 정의된다.

## E5 — Similar Label

- **입력**: 의도적으로 유사하게 만든 라벨 쌍. 난이도 4구간은 기준 문서 §30을 따른다.

  | 난이도 | 정의 |
  |---|---|
  | Easy | 외형이 완전히 다르다 |
  | Medium | Layout이 같다 |
  | Hard | 문자 한두 글자만 다르다 |
  | Extreme | Barcode/OCR 내용만 다르다 |

- **구간 규칙** (#35, 코드 `src/utils/pilot.py` `similarity_tier`): 사람이 쌍을 고르지 않고 카탈로그에서 정한다.
  위에서부터 첫 번째로 맞는 구간이다.

  | 구간 | 규칙 | Pilot 쌍 수 | 예 |
  |---|---|---:|---|
  | Easy | layout·palette·font 중 하나라도 다르다 | 59 | a-1 / c-1 |
  | Extreme | 겉모습과 인쇄 문자가 전부 같다 (바코드만 다름) | 1 | b-3 / b-4 |
  | Hard | 같은 field·같은 글자 수, 다른 글자 ≤ 2개 | 5 | a-2 / a-4, a-3 / b-3, a-3 / b-4, **a-2 / a-5**(바코드 같음), a-4 / a-5 |
  | Medium | 나머지 — 겉모습은 같고 내용이 여러 곳 다르다 | 13 | a-2 / b-2 |

  쌍 수는 Pilot v0.4 카탈로그 기준이다. a-5(v0.4)가 든 쌍에는 E5 전용 unit이 없다 — 전용 unit은 v0.3 카탈로그로
  배정해 그림을 유지한다. 대신 a-2 / a-5는 `revision_mismatch` 72 unit(test)이 E5-hard로 들어온다.

- **분할**: 난이도별 test subset을 `experiment_tags`(`E5-easy` … `E5-extreme`)로 표시한다. 바꿔치기 불량
  (`wrong_label` / `wrong_product_label` / `revision_mismatch`)은 전부 (요구, 실제) 쌍의 구간 태그를 받는다. 무작위 바꿔치기로는
  Extreme(1쌍)이 거의 생기지 않으므로 **구간마다 전용 unit 72개를 test에 추가**한다 (escape 0건이면 95% 상한 ≤ 5%).
  전용 unit은 모든 row에 `E5` 태그를 더 단다(Pilot v0.4~) — E1 범위에서 빼기 위해서다.
- **지표**: 난이도별 Similar-label Confusion Rate(= 구간별 바꿔치기 불량의 DER, evaluation_protocol §3), modality ablation(visual only → +OCR → +Barcode → +Context).
- **성공 기준**: Extreme 구간에서 visual only는 구별하지 못하고 OCR/Barcode를 더하면 구별한다 — 가설 검증형.
  Hard 구간의 a-2 / a-5는 바코드가 같아 **OCR만** 가른다 — modality ablation에서 OCR의 기여를 바코드와 분리해 본다.

## E6 — Domain Shift

- **입력**: 학습 조건과 다른 Lighting / Production LOT / Position / Rotation / Camera / Background / Reflection / Blur.
- **분할**: shift 요인별 test subset(`E6-lot`, `E6-light` …). **threshold는 in-domain `val` 값을 재조정 없이 쓴다** (schema §4.4).
- **지표**: 요인별 DER·FPR과 in-domain 대비 변화량. Review Rate 변화.
- **성공 기준**: shift 조건에서 늘어난 불량이 `OK`로 새지 않고 `REVIEW`로 흡수된다 — DER 증가가 in-domain
  신뢰구간 안이고 Review Rate 증가는 상한 이내. 상한 숫자 `[시작 시 확정, Week 17]`.
- **주의**: 조명·배경·반사는 `experiment_tags`로 표시한다 (schema §4.4). 모든 test LOT은 이미 새 LOT이므로
  `E6-lot`은 큰 LOT 변화를 뜻한다.

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-09-21 | 초안. E1~E6별 입력 / 분할 / 지표 / 성공 기준(제안) / 대응 RQ |
| v1.0 | 2026-09-21 | 성공 기준 형태 확정(#31): E1 제품 단위 과검률에서 역산, E2 k=10(도전 5), E3 Unknown→OK 0건, E4 public은 유형별 DER·seen/unseen은 Pilot, E6 escape 대신 REVIEW 흡수 |
| v1.1 | 2026-09-25 | E1의 Pilot 과검률 목표 **F = 1%** 확정(#33). 정본은 `configs/recipes/pilot.yaml`. E3·E5 입력이 되는 Pilot benchmark가 실제로 생성됨 |
| v1.2 | 2026-09-25 | Pilot에 synthetic defect 10종 추가(#34). E4 Pilot의 hold-out 유형은 `unknown_visual`(val에 없음, `is_known_defect=false`), 본 유형은 나머지 9종 |
| v1.3 | 2026-09-25 | E5 구간 규칙 확정, Pilot에 구간별 전용 unit 72개(#35). Confusion Rate = 구간별 바꿔치기 DER |
| v1.4 | 2026-10-27 | **평가 범위** 절 추가(ADR 0008, #69 T2): 시나리오별 unit 범위, E1은 미등록 라벨·hold-out 유형·E5 전용 unit 제외(결정 2). E5 전용 unit에 `E5` 태그(Pilot v0.4) |
| v1.5 | 2026-10-27 | Pilot v0.4(#69 T5~T7·T9): 공통 규칙에 `pilot_dev`·test 봉인, 평가 범위에 `GEOM-boundary`·`OCR-confusable` 묶음과 E1·E4 제외, E5에 `revision_mismatch`와 OCR-only 쌍 a-2 / a-5, 구간별 쌍 수 갱신 |
