# Week 02 — 평가 레일 + Schema/Scenario 초안

- 기간: 2026-09-19 (토) ~ 2026-09-20 (일) 예정 → **2026-09-21 (월) 수행** (일주일 지연)
- 주제: 모델을 붙이기 전에, 앞으로 모든 모델이 지나갈 **데이터 → 예측 → 평가 → MLflow** 레일을 깐다
- 이슈: #7 (하위 #30, #31, #32, #36, #40)

---

## Goal

MVTec AD를 Unified Schema 기반 평가 파이프라인에 끝까지 통과시킨다. 모델은 dummy다.

계획 변경: 원래 Week 2는 schema/split/시나리오 확정 주였다. Week 1에 문서가 먼저 끝나서
**Week 4의 핵심 metric(#36)을 당겨와** vertical slice(#40)로 함께 구현했다. split(#30)과 시나리오(#31)는
연구 결정이 필요한 문서라 **초안까지만** 썼다.

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
| Split/leakage 제안 (#30, 확정 전) | `datasets/schema.md` v0.3 §4 |
| E1~E6 시나리오 초안 (#31) | `reports/experiment_scenarios.md` |

테스트 53개(unit) + 실데이터 1개 통과. metric은 TDD로 썼고, 경계 조건(escape 0건 / 불량 0건 /
REVIEW만 / 단일 샘플)을 전부 테스트한다.

---

## Result

**레일 점검 run — 숫자는 dummy random score라 의미 없음. 인용 금지.**

```text
experiment : week02_pipeline_check   run_id 5938636a75b44860a9c360e8cdad3dcd
params     : git_commit=c121372 (clean), dataset=mvtec_ad v1.0 / bottle, model=dummy,
             threshold ok=0.3 ng=0.7 (fixed, not calibrated), num_train=209, num_test=83
confusion  : normal {OK 6, REVIEW 10, NG 4} / defect {OK 16, REVIEW 26, NG 21}
DER        : 16 / 63 escaped = 25.4%  95% CI [15.3%, 37.9%]
CDER       : N/A (public track — Recipe severity 없음)
artifacts  : predictions.csv (83 rows), metrics.json, config/
```

확인한 것: metadata 검증 → 예측 → 판정 → 지표 → MLflow 기록이 한 번에 돈다. 같은 seed로 두 번 돌려
같은 결과가 나온다.

---

## Problems

1. **MVTec AD에는 val split이 없다.** DER은 threshold가 있어야 계산되는데 calibration 데이터가 없다.
   → schema §4.3에 안 A/B/C를 정리했다 (#30에서 결정).
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

---

## Next

- #30 / #31 초안의 `[결정]` 항목 확정 → schema v1.0
- #32 MVTec LOCO / VisA 변환기 (LOCO는 다운로드가 신청서 방식이라 직접 받는 링크 확인 필요)
- Week 3 (#8): Pilot benchmark
- 모델(PatchCore)은 **Week 4 Gate(#39) 통과 후**

---

## 세 줄 정리

```text
이번 주에 결정한 것:
REVIEW 처리 규칙을 지표별로 고정하고(2-state 지표는 REVIEW→NG, DER/FPR은 3-state) 코드와 문서를 일치시켰다.
MVTec AD → schema 검증 → dummy 예측 → 평가 → MLflow 레일이 끝까지 돈다. dataset_version은 원본 해시로 정의한다.

아직 불확실한 것:
val이 없는 public 데이터에서 threshold를 어떻게 정할지(schema §4.3), unit 단위 단일 split 규칙과 LOT 규칙의 범위,
E1~E6 성공 기준 수치. GPU 환경(#5)도 미정.

다음 주말 첫 번째 할 일:
#30의 [결정] 항목을 확정해서 schema를 v1.0으로 올리고, 확정된 leakage 규칙을 검증기에 넣는다.
```
