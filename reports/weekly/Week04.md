# Week 04 — Evaluation Pipeline (Month 1 Gate)

- 기간: 2026-10-03 (토) ~ 2026-10-04 (일) 예정 → **2026-10-06 (화) 수행** (사흘 지연), Gate PR 머지는 2026-10-22 (목)
- 주제: 평가 프로토콜의 지표를 전부 코드로 만들고, Pilot에서 끝까지 돌려 Month 1 Gate를 점검한다
- 이슈: #9 (하위 #37, #38, #39)

---

## Goal

> **평가 파이프라인이 완성되기 전에는 모델을 늘리지 않는다.**

Week 5부터 붙는 모든 모델이 같은 척도로 비교되도록, `evaluation_protocol.md`에 정의만 있고 코드가 없던 지표
(Label/Product-level 집계, Unknown·Identity, latency)를 채운다. 핵심 metric(#36)은 Week 2에 당겨서 끝냈으므로
이번 주는 그 나머지와 Gate 점검이다.

---

## Implemented

| 항목 | 파일 | 이슈 |
|---|---|---|
| Label-level `(unit_id, label_slot)` / Product-level `unit_id` 집계 — 최상위와 같은 지표 묶음 | `src/evaluation/metrics.py` `evaluate()` | #37 |
| FPR 2-state (REVIEW → NG, 선행 연구 비교용) | `src/evaluation/metrics.py` | #37 |
| Identity 지표: Known Label Accuracy / Unknown Label Detection Rate / Unknown Forced Rate | `src/evaluation/metrics.py` | #37 |
| 제품 단위 latency — P50/P95/P99, 구간 breakdown, 시간대별 제품 수, 측정 환경 기록 | `src/evaluation/latency.py` | #38 |
| `calibrate()`가 `split != "val"` row를 거부 — val 전용 threshold를 코드로 강제 | `src/evaluation/metrics.py` | #39 |
| E3 주 성공 기준 `unknown_label_ok_rate`, Open-set 3-class `open_set_accuracy` | `src/evaluation/metrics.py` | #39 |
| Gate 점검 실험 — Pilot 전체, 제품별 threshold, 같은 seed 2회 비교 | `experiments/week04_gate_check.py`, `configs/week04_gate_check.yaml` | #39 |
| `flat_metrics` / `write_predictions` / `PRED_COLUMNS`를 두 실험이 같이 쓰도록 이동 | `src/utils/tracking.py` | #39 |
| 코드가 읽지 않던 `percentiles` 제거, latency 환경 키 추가 | `configs/base.yaml` **v0.3** | #38 |
| protocol v0.7 → v0.8 → **v0.9** | `reports/evaluation_protocol.md` | #37~#39 |

테스트 132 → **147개**, skip 없음. latency는 가짜 시계를 주입해서 warm-up 제외·분위수·sync 횟수를 테스트한다.

---

## Result

**Gate 점검 run — score와 identity가 seed 고정 random이라 성능 숫자는 의미 없음. 인용 금지 (`citable=false`).**

```text
experiment : week04_gate_check   run_id 8efd4b440d4843169f6042a3542daa47 (2026-10-06)
params     : git_commit=4d19677 + 미커밋 변경(dirty → ea8d330으로 커밋), dataset=pilot v0.3 (schema v1.1),
             model=dummy, seed=42, device=cpu
test       : 4,296 row (정상 3,288 / 불량 1,008) = 1,308 제품 (정상 300 / 불량 1,008), L=3 936개 · L=4 372개
threshold  : 제품별 val 정상 분위수, f = 1 − (1 − F)^(1/L), F = 1%, r = 10%
             A f=0.334% (val 정상 504) / B f=0.334% (504) / C f=0.251% (696)
재현성     : 같은 seed 2회 → metrics JSON 완전 일치 (reproducible=True)
artifacts  : config·registry·recipe, predictions.csv (4,296 rows), metrics.json, latency.json, gallery (FN 20 / FP 9)
```

| #39 점검 항목 | 결과 |
|---|---|
| 지표가 Pilot에서 실제로 계산되는가 | Defect·Label·Product 3-level, DER 분해(category·type), Identity 3종, E3, E5 4구간 모두 값이 나온다 |
| 같은 입력에 항상 같은 숫자 | 같은 seed 2회 → 일치. 다르면 스크립트가 멈춘다 |
| MLflow에 §9 필수 보고 세트 | params·metrics 누락 0. evidence 예시는 XAI(Week 15) 이후라 아직 없다 |
| threshold를 val에서만 정하는 경로 | `calibrate()`가 강제하고 테스트가 고정한다 |
| `Week04.md` | 이 문서 |

### 집계 규칙이 숫자를 얼마나 바꾸는가

모델은 random이지만, 아래 차이는 모델이 아니라 **집계 규칙과 Pilot 구성**에서 나온다.

| 지표 | Label-level | Product-level |
|---|---:|---:|
| FPR (NG만) | 9 / 3,288 = 0.27% | 3 / 300 = **1.0%** [0.2%, 2.9%] |
| 정상 중 REVIEW | 373 / 3,288 = 11.3% | 105 / 300 = **35.0%** |
| DER | 917 / 1,008 = 91.0% | 703 / 1,008 = **69.7%** |
| Precision (REVIEW → NG) | 91 / 473 = 19.2% | 305 / 413 = 73.8% |
| AUPRC | 0.22 | 0.75 |

1. **f를 F에서 역산하는 규칙은 맞았다.** 라벨 단위 f ≈ 0.3%로 정했더니 제품 단위 FPR이 목표 F = 1%(3/300)로 나왔다.
   다만 정상 제품이 300개뿐이라 신뢰구간이 [0.2%, 2.9%]로 넓다.
2. **r은 역산하지 않았다.** 라벨 단위 r = 10%가 제품 단위에서는 정상 제품의 35%를 REVIEW로 보낸다
   (라벨 오류가 독립이면 1 − 0.887^3.28 ≈ 33%). 정상 제품 셋 중 하나를 사람이 보는 라인은 운영되지 않는다.
3. **Product-level DER은 불량이 아닌 슬롯 덕분에 좋아질 수 있다.** 제품 단위로 잡힌 불량 제품 305개 중
   **214개(70%)는 불량 슬롯이 OK였고**, 같은 제품의 정상 슬롯이 REVIEW/NG였다. ADR 0003상 올바른 판정이지만,
   Product-level DER만 보면 과검이 많은 모델이 유리해 보인다.
4. **Pilot test는 제품의 77%(1,008/1,308)가 불량이다.** 유형별 DER의 n을 확보하려고 불량 unit을 많이 만든 결과다
   (Week 3, 유형마다 72 row 이상). Product-level Precision·AUPRC가 이 비율에 끌려 올라간다 — random인데 AUPRC 0.75.
   현장 불량률과 거리가 멀어서 Pilot의 Product-level Precision/AUPRC는 근거로 쓸 수 없다.

latency는 dummy pipeline이라 `latency_*`가 기록되는 경로만 확인했다(device=cpu, 100회).

---

## Problems

1. **`calibrate()`가 어떤 split이든 받았다.** "threshold를 test로 정하지 않는다"는 규칙이 문서에만 있었다.
   test row를 실수로 넘기면 숫자가 조용히 좋아진다. → `split != "val"`이면 `ValueError`(#39).
2. **E3의 주 성공 기준("Unknown 라벨이 OK로 간 건수 0")을 계산하는 코드가 없었다.** Open-set 3-class 정확도도
   scenario 문서에만 있었다. → `unknown_label_ok_rate`, `open_set_accuracy`를 추가했다.
3. **#37 이슈 본문의 Product-level 규칙이 ADR 0003과 달랐다**("CRITICAL NG면 Product NG"). 이슈 본문을 ADR에 맞춰 고쳤다.
4. **`configs/base.yaml`의 `latency.percentiles`는 어떤 코드도 읽지 않았다.** 바꿔도 아무 일이 일어나지 않는 설정이라
   지웠다(P50/P95/P99는 protocol §7에 고정). Week 3의 severity override와 같은 종류의 문제다.
5. **Gate run이 커밋 전 작업 트리(`git_dirty=True`)에서 돌았다.** 인용하지 않는 run이라 결과가 무효는 아니지만,
   인용할 run은 깨끗한 트리에서 돌린다는 규칙과 어긋난다.
6. **Gate PR(#61)이 10-06에 열린 뒤 10-22에야 머지됐다.** 그 사이 Week 5(10-10)와 Week 6(10-17) 일정이 지나갔다.
   Gate 규칙상 Week 5를 시작하지 않은 것은 맞지만, 일정은 약 2주 밀렸다.

---

## Decisions

1. **Label/Product-level 정답 묶기**: 하나라도 불량이면 불량, `CRITICAL`이 하나라도 있으면 CDER 분모, score는 최댓값.
   같은 `(unit_id, label_slot)`의 카메라 여러 대 row는 판정 최악값 하나로 합친다. 판정 규칙은 ADR 0003 그대로다.
2. **2-state(REVIEW → NG)는 FPR만 따로 낸다.** DER은 REVIEW가 escape가 아니라서 두 방식의 값이 같다.
3. **identity를 내지 않는 모델의 identity 지표는 `null`이다. 0%가 아니다.** 거부는 문자열 `UNKNOWN`이고,
   `missing_label`(맞힐 라벨이 없다)은 Known Label Accuracy 분모에서 뺀다.
4. **Unknown Forced Rate를 별도 실패 유형으로 둔다.** 미등록 라벨을 등록 라벨로 억지 분류하는 것은 단순 오분류가 아니다.
5. **E3의 주 기준은 Unknown Label OK Rate다.** 판정만 쓰므로 identity가 없는 AD baseline(Week 5~8)도 E3에서 비교된다.
6. **latency P50/P95/P99는 제품 1개를 처음부터 끝까지 잰 벽시계 시간이다.** 구간 합이 아니다. 구간 이름은 §7의
   11개로 고정, 100회 미만이면 오류, GPU는 시계를 읽기 전에 sync한다.
7. **보고용 latency는 Jetson Nano에서만 잰다(#5).** 학습용 대여 GPU는 host가 매번 달라 비교가 성립하지 않는다.
8. **Pilot threshold는 제품별로 정한다.** f = 1 − (1 − F)^(1/L), L은 그 제품의 라벨 수.
9. **Month 1 Gate의 점검 항목 5개를 모두 채웠다.** Week 5(Classical Baseline)로 넘어간다.

---

## Next

- **일정 재조정** — 10-22 기준 약 2주 지연. Week 5를 10-24(토)에 시작하고 이후 일정을 미룰지, Week 5~6을
  압축할지 정해야 한다. Week 20 Feature Freeze까지의 여유가 그만큼 줄었다.
- **Week 5 (#10) Classical Baseline** — Month 2 Phase 시작이므로 #10~#13을 분해한다. 첫 실제 모델로 Pilot E1의
  Product-level FPR과 REVIEW율을 확인한다.
- **r(normal_review_rate)을 제품 단위 목표에서 역산할지** — 첫 baseline의 실제 REVIEW율을 본 뒤 정한다.
- **Product-level DER을 Label-level과 함께 보고하는 방식** — "정상 슬롯 때문에 잡힌 불량 제품 수"를 보조 지표로
  둘지 검토한다. protocol 변경이라 이슈로 분리한다.
- **#5 GPU** — 학습은 대여 GPU로 정했다(09-25). Week 6 PatchCore 전에 torch·anomalib 설치까지 끝내야 한다.
  Classical baseline은 CPU로 된다.
- #3 PatchCore 정리 확정이 Month 1 milestone에 아직 열려 있다.

```text
이번 주에 결정한 것:
Label/Product-level 집계(정답은 하나라도 불량이면 불량, score는 최댓값), FPR 2-state, identity 지표(identity를 안 내면
null), Unknown Forced Rate를 별도 실패 유형으로, E3 주 기준은 Unknown Label OK Rate. latency는 제품 1개 벽시계 기준이고
보고용은 Jetson만. threshold는 val에서만 — calibrate()가 강제한다. Pilot에서 3-level 지표가 전부 계산되고 재현됨을
확인해서 Month 1 Gate 점검 항목을 모두 채웠다.

아직 불확실한 것:
라벨 단위 r=10%가 제품 단위로는 정상 제품 35%를 REVIEW로 보낸다 — r도 제품 목표에서 역산해야 하는가. Product-level
DER이 정상 슬롯의 과검 덕분에 좋아지는 효과(random에서 잡힌 불량 제품의 70%)를 어떻게 보고할 것인가. Pilot test의
제품 단위 불량 비율 77%가 Product-level Precision·AUPRC를 부풀린다. 일정 약 2주 지연. GPU 환경 설치(#5).

다음 주말 첫 번째 할 일:
일정을 재조정하고 Week 5 Classical Baseline(#10)을 분해한다. 첫 실제 모델로 Pilot E1의 Product-level FPR과
REVIEW율을 확인한다.
```
