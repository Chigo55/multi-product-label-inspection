# Week 02 — 평가 레일 + Schema v1.0 / Scenario 확정

- 기간: 2026-09-19 (토) ~ 2026-09-20 (일) 예정 → **2026-09-21 (월) 수행** (일주일 지연)
- 주제: 모델을 붙이기 전에, 앞으로 모든 모델이 지나갈 **데이터 → 예측 → 평가 → MLflow** 레일을 깐다
- 이슈: #7 (하위 #30, #31, #32, #36, #40)

---

## Goal

MVTec AD를 Unified Schema 기반 평가 파이프라인에 끝까지 통과시킨다. 모델은 dummy다.

계획 변경: 원래 Week 2는 schema/split/시나리오 확정 주였다. Week 1에 문서가 먼저 끝나서
**Week 4의 핵심 metric(#36)을 당겨와** vertical slice(#40)로 함께 구현했다. split(#30)과 시나리오(#31)는
초안을 쓴 뒤 결정 항목 10개를 검토해서 확정했다.

---

## Implemented

| 항목 | 파일 |
|---|---|
| Dataset Registry — `dataset_version` = 원본 SHA256 + schema + 변환기 | `datasets/registry.yaml` |
| MVTec AD 변환기 (Week 1 #4) | `src/utils/mvtec.py` |
| metadata 입출력 + schema 검증기 | `src/utils/metadata.py` |
| 3-state 판정 + 지표 (DER/CDER/FPR/Review/P/R/F1/AUROC/AUPRC + Clopper-Pearson) | `src/evaluation/metrics.py` |
| MLflow 공통 (git commit, SQLite) | `src/utils/tracking.py` |
| 레일 점검 실험 | `experiments/week02_pipeline_check.py`, `configs/week02_pipeline_check.yaml` |
| 평가 프로토콜 v0.3 — 지표별 REVIEW 처리, `predictions.csv` 형식 | `reports/evaluation_protocol.md` |
| Split/leakage 확정 + 검증기 규칙 (#30) | `datasets/schema.md` **v1.0** §4, `src/utils/metadata.py` |
| val 분할(train 정상 20%) + 정상 분위수 threshold calibration | `src/utils/mvtec.py`, `calibrate()` in `metrics.py`, protocol **v0.4** §6 |
| E1~E6 시나리오 확정 (#31) | `reports/experiment_scenarios.md` **v1.0** |

테스트 73개(unit) + 실데이터 1개 통과. metric은 TDD로 썼고, 경계 조건(escape 0건 / 불량 0건 /
REVIEW만 / 단일 샘플)을 전부 테스트한다.

---

## Result

**레일 점검 run — 숫자는 dummy random score라 의미 없음. 인용 금지.**

```text
experiment : week02_pipeline_check   run_id 627eb5386dd84eeba77bf2d2f4bc55ad
params     : git_commit=374b9e6 (clean), dataset=mvtec_ad v1.1 / bottle, model=dummy,
             num_train=167, num_val=42, num_test=83
threshold  : ok=0.893 ng=0.976 — val 정상 42장 분위수 (f=1%, r=10%)
confusion  : normal {OK 19, REVIEW 1, NG 0} / defect {OK 60, REVIEW 3, NG 0}
DER        : 60 / 63 escaped = 95.2%  95% CI [86.7%, 99.0%]
CDER       : N/A (public track — Recipe severity 없음)
artifacts  : predictions.csv (83 rows), metrics.json, config/
```

확인한 것: metadata 검증 → score → val calibration → test 판정 → 지표 → MLflow가 한 번에 돈다.
같은 seed로 두 번 돌려 같은 결과가 나온다. **random score에 정상 분위수 threshold를 걸면 불량 대부분이
OK로 샌다 — 쓸모없는 모델은 DER에서 그대로 드러난다.** (고정 threshold 0.3/0.7이었던 첫 run은 DER 25%로
오히려 좋아 보였다. threshold를 정하는 규칙이 숫자를 얼마나 바꾸는지 보여 준다.)

MVTec AD 15개 category 전체(5,354장 → train 2,903 / val 726 / test 1,725)도 검증기 오류 0건.

---

## Problems

1. **MVTec AD에는 val split이 없다.** DER은 threshold가 있어야 계산되는데 calibration 데이터가 없다.
   → train 정상 20%를 val로 떼고 정상 분위수로 threshold를 정하기로 했다 (schema §4.3). 한계: val이
   작으면 분위수 해상도가 거칠다(bottle 42장 → 약 2.4% 단위).
2. **문서끼리 숫자가 달랐다.** ADR 0005의 "0/12 → 상한 약 22%"는 단측 95%, protocol의 "0/1200 → 0.31%"는
   양측 95%였다. 코드는 양측으로 구현하고 ADR을 "약 26%, ≈3.7/n"으로 정정했다.
3. `uv run experiments/x.py`로 실행하면 `src`를 import할 수 없다. 스크립트마다 `sys.path` 두 줄이 필요하다.

---

## Decisions

1. **Precision/Recall/F1은 REVIEW를 NG로 합친다** → Recall = 1 − DER. DER/FPR은 3-state 그대로.
   Confusion matrix는 실제 × 판정의 2×3이다.
2. **threshold 경계값(score == ok 또는 ng)은 REVIEW다.** protocol §6의 부등호를 그대로 따른다.
3. 신뢰구간은 **Clopper-Pearson 양측 95%**다. 분모가 0이면 지표는 `null`이다.
4. **Dataset Registry에는 실제로 받아서 해시를 확인한 데이터만 넣는다.** 계획 단계 항목은 넣지 않는다.
5. 데이터셋별 loader base class를 두지 않는다. 데이터셋끼리 맞추는 기준은 JSONL schema다 (ADR 0006).
6. 모든 run은 `predictions.csv`를 남긴다 — FN 샘플 추적과 Failure Gallery의 원본.
7. **Split / leakage (schema v1.0)**: 한 `unit_id`는 한 split에만. test의 LOT은 train/val/reference와 겹치지 않는다
   (과거 LOT으로 학습하고 미래 LOT을 검사). Unknown label/defect는 test에만. 전부 검증기가 검사한다.
8. **Calibration**: public은 train 정상 20% → val (`sha256(unit_id)` 순서라 버전·seed 무관).
   threshold는 val 정상 분위수 — f=1%(목표 과검률) → `ng`, r=10% → `ok`. f는 제품 단위 목표에서 역산한다.
9. **시나리오 성공 기준**: E1 제품 단위 과검률 목표에서 역산 / E2 k=10(도전 5) / E3 Unknown 라벨이 OK로 가는 건수 0 /
   E4 public은 결함 유형별 DER, seen·unseen 비교는 Pilot / E6 늘어난 불량이 escape가 아니라 REVIEW로 흡수.
10. E6 촬영 조건은 `experiment_tags`로 표시한다. Severity 규칙은 현행(taxonomy 기본값 + Recipe override) 확정,
    **Recipe 파일 형식은 Week 3(#8)** 에 정한다.

---

## 추가 — Public track 3종 연결 (#32, 2026-09-21)

| 데이터셋 | 원본 → split | rows | 불량 | 라이선스 |
|---|---|---:|---:|---|
| MVTec AD v1.1 | train 20% → val | 5,354 | 1,258 (visual) | CC BY-NC-SA 4.0 |
| MVTec LOCO v1.0 | 공식 validation → val | 3,651 | 993 (logical 561 / visual 432) | CC BY-NC-SA 4.0 |
| VisA v1.0 | 공식 1cls, train 20% → val | 10,821 | 1,200 (visual, 복수 불량 → `defects[]`) | **CC BY 4.0** |

세 데이터셋 모두 SHA256을 확인했고 검증기 오류는 0건이다. 공통 값은 `public_row()` 한 곳에서 만든다.

- **val은 제품별로 20%를 뗀다.** 처음에는 VisA 전체에서 20%를 뽑아서 object별 비율이 20.7% 등으로 들쭉날쭉했다.
  threshold를 제품별로 정하므로 제품별로 고쳤다.
- **LOCO 배포본은 3,651장**(train 1,778 / val 305 / test 1,568)으로, 논문 표기로 기억하는 3,644장과 7장 다르다.
  디스크 파일 수와 변환 결과는 일치한다. 논문 원문과의 대조는 #2에서 한다.
- 평가에 **DER 분해(불량 분류·유형별)**를 추가했다. LOCO juice_bottle에 dummy로 돌려서 logical 142건과 visual 94건이
  나뉘어 집계되는 것을 확인했다. logical 불량은 실제 불량이라 DER에 들어가는 것이 맞다. `expected_*`가 필요한
  logical 검사 항목(라벨·OCR·barcode 비교)은 아직 지표가 없고(#37), public row는 `expected_*`가 전부 null이라 자동으로 빠진다.
- `experiments/week02_mvtec_smoke.py`를 `experiments/build_metadata.py`로 대체했다. registry를 읽어서 데이터셋 전체를 변환하고,
  검증 오류가 0건일 때만 파일을 쓴다.

---

## Next

- Week 3 (#8): Pilot benchmark — Recipe 파일 형식, LOT 2개 이상 부여
- 모델(PatchCore)은 **Week 4 Gate(#39) 통과 후**

---

## 세 줄 정리

```text
이번 주에 결정한 것:
REVIEW 처리를 지표별로 고정하고 코드와 문서를 일치시켰다. schema v1.0으로 split/leakage를 확정했다(unit 단일 split,
test LOT 분리, Unknown test 격리). threshold는 val 정상 분위수로 정한다. MVTec AD → 검증 → calibration → 평가 → MLflow
레일이 끝까지 돌고, E1~E6 성공 기준의 형태를 확정했다.

아직 불확실한 것:
val이 작을 때 분위수 threshold가 얼마나 흔들리는지(bottle val 42장). LOCO/VisA 다운로드 경로. Pilot의 제품 단위
과검률 목표 F. GPU 환경(#5).

다음 주말 첫 번째 할 일:
Week 3 Pilot benchmark(#8) — Recipe 파일 형식을 정하고 LOT을 2개 이상 부여한다.
```
