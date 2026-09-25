# Evaluation Protocol v0.6

> 작성일: 2026-09-12 (Week 1)
> 목적: **무엇을 측정할지를 고정한다.** (계산 코드 구현은 Week 4)
> 이 문서에 없는 지표는 논문/보고서의 주장 근거로 쓰지 않는다.

---

## 0. 판정 상태 정의

시스템 출력은 3-state다.

```text
OK      : 통과
NG      : 불량으로 판정하여 배출
REVIEW  : 판정 보류 → 사람이 확인
```

집계 시 규칙:

- **Escape(불량 유출)** = 실제 불량인데 **`OK`로 판정**된 경우. `REVIEW`는 escape가 **아니다**(사람에게 도달했으므로).
- **False Reject(과검)** = 실제 정상인데 **`NG`로 판정**된 경우. `REVIEW`는 false reject가 **아니다**.
- `REVIEW`는 별도의 비용 지표(**Review Rate**)로 따로 보고한다.

> **중요**: 모든 지표는 반드시 `REVIEW` 처리 방식을 명시해서 보고한다.
> 2-state 비교(AUROC 등)가 필요할 때는 `REVIEW`를 NG로 합친 값도 함께 적는다.

지표별 `REVIEW` 처리 (코드 정본: `src/evaluation/metrics.py`):

| 지표 | `REVIEW` 처리 |
|---|---|
| DER / CDER / FPR | 3-state 그대로. `REVIEW`는 escape도 false reject도 아니다 |
| Precision / Recall / F1 | 2-state. **`REVIEW`를 NG로 합친다.** 따라서 Recall = 1 − DER |
| Review Rate | 전체 중 `REVIEW` 비율 |
| AUROC / AUPRC | threshold-free. score만 쓴다 |

Confusion matrix는 **실제(normal/defect) × 판정(OK/REVIEW/NG)의 2×3**으로 보고한다.

---

## 1. Primary Metric

```text
Defect Escape Rate (DER)
= FN / Actual Defects
```

$$\mathrm{DER} = \frac{|\{\text{defect samples judged OK}\}|}{|\{\text{all defect samples}\}|}$$

**Defect Escape Rate = False Negative Rate.** 이 연구의 단일 최상위 지표다.
모델 비교표의 **첫 번째 열**은 항상 DER이며, Accuracy는 대표 지표로 쓰지 않는다.

### Critical Defect Escape Rate (CDER) — 실질적 최우선

```text
CDER = (severity=CRITICAL 이면서 OK로 판정된 수) / (severity=CRITICAL 전체 수)
```

**목표: CDER = 0.** 단, 0을 관측했다고 "Recall 100%"로 보고하지 않는다 → §5 참고.

---

## 2. 검출 성능 지표

positive = defect 기준.

| 지표 | 정의 | 비고 |
|---|---|---|
| **Defect Escape Rate (FNR)** | FN / (TP+FN) | **Primary** |
| **Critical Defect Escape Rate** | severity=CRITICAL 한정 FNR | **Primary** |
| **False Positive Rate** | FP / (FP+TN) | 과검율. 라인 가동률에 직결 |
| Precision | TP / (TP+FP) | |
| Recall | TP / (TP+FN) = 1 − FNR | |
| F1 | 2PR/(P+R) | 참고용. 불균형 데이터라 단독 사용 금지 |
| **AUPRC** | Precision-Recall 곡선 아래 면적 | 불량 희소 → AUROC보다 신뢰 |
| AUROC | ROC 곡선 아래 면적 | 선행 연구 비교용 (MVTec 등) |

> threshold-free 지표(AUPRC/AUROC)와 threshold-dependent 지표(DER/FPR)를 **항상 함께** 보고한다.

**DER 분해**: `defect_escape_rate_by_category`(visual / logical), `defect_escape_rate_by_type`(대표 `defect_type`별)을
함께 낸다. 어떤 유형이 새는지가 E4(public)와 MVTec LOCO logical 축의 보고 단위다. 복수 불량 row는 대표값 하나로 센다.
> threshold는 어떻게 정했는지(§6) 반드시 명시한다.

---

## 3. Identity / Open-set 지표

| 지표 | 정의 |
|---|---|
| **Known Label Accuracy** | `is_known_label=true` 샘플에서 `actual_label_id`를 맞춘 비율 |
| **Unknown Label Detection Rate** | `is_known_label=false` 샘플을 `UNKNOWN`으로 거부한 비율 (= 1 − 오분류율) |
| **Similar-label Confusion Rate** | E5 난이도 구간별로, `E5-<구간>` 태그가 달린 바꿔치기 불량(`wrong_label` / `wrong_product_label`) 중 `OK`로 나간 비율. 즉 **구간별 DER**이다 (아래) |
| Open-set 상태 정확도 | `KNOWN_EXPECTED` / `KNOWN_WRONG` / `UNKNOWN` 3-class 정확도 |

> **Unknown을 기존 class로 억지 분류한 경우는 단순 오분류가 아니라 별도 실패 유형으로 집계한다.**
> 이것이 현장에서 가장 위험한 실패 모드다.

**Similar-label Confusion Rate를 escape로 정의한 이유**: 라벨 A 자리에 A와 닮은 B가 붙었는데 `OK`가 나왔다면,
시스템이 B를 A로 혼동한 것이다. 이 정의는 판정(`decision`)만 쓰므로 identity를 출력하지 않는 AD 모델에도
적용된다 — E5 성공 기준("visual only는 Extreme에서 실패하고 +OCR/Barcode로 구별")을 같은 척도로 비교할 수 있다.
`REVIEW`는 혼동이 아니다(사람에게 갔다). 구간은 `experiment_scenarios.md` E5, 코드는 `src/utils/pilot.py`
`similarity_tier`. 태그가 없는 데이터(public track)는 빈 결과이며 0%로 보고하지 않는다.

---

## 4. 평가 단위 (3-Level)

동일 실험을 세 단위로 모두 보고한다.

| Level | 단위 | 집계 규칙 |
|---|---|---|
| **Level 1 — Defect-level** | 개별 결함 | localization 포함 (mask/bbox subset에 한함) |
| **Level 2 — Label-level** | 라벨 1개 (`unit_id`, `label_slot`) | 해당 라벨의 모든 검사 항목 중 최악값 |
| **Level 3 — Product-level** | Product Unit 1개 (`unit_id`) | 아래 집계 규칙 |

### Product-level 집계 규칙

```text
라벨 중 하나라도 NG      → Product NG        (severity 무관)
NG 없고 하나라도 REVIEW  → Product REVIEW
전부 OK                  → Product OK
```

**NG가 REVIEW보다 우선한다.** 한 제품에 NG 라벨과 REVIEW 라벨이 함께 있으면 Product NG다.

`CRITICAL`만 Product NG로 보는 안은 택하지 않았다 — 그러면 찢어진 라벨(`MAJOR`)이 붙은 제품이
Product-level에서 정상으로 집계된다. `CRITICAL`은 Critical Defect Escape Rate로 이미 별도
추적하므로 중복이 아니다. (`docs/adr/0003`)

> Product-level이 현장 KPI와 직결된다. Label-level 성능이 좋아도 제품당 라벨이 많으면 Product-level FPR이 급격히 악화된다 — 반드시 함께 본다.
> 집계에는 `unit_id`가 필요하다. Dataset Schema v0.2에서 추가됐다.

### 부가 지표

| 지표 | 정의 |
|---|---|
| **Review Rate** | REVIEW 판정 비율 (label-level / product-level 각각) |
| Localization | (annotation 있는 subset 한정) IoU 또는 sPRO |

---

## 5. 통계적 보고 규칙

**관측된 비율만 쓰지 않고 표본 수와 신뢰구간을 함께 적는다.**

보고 형식(필수):

```text
Critical defects:
0 / 1,200 escaped

Observed CDER:
0.00%

95% confidence upper bound (Clopper-Pearson):
0.31%
```

- 이항 비율 신뢰구간은 **Clopper-Pearson(exact) 양측 95%** 를 기본으로 한다. 분모가 0이면 지표는 정의되지 않는다(`null`).
- escape가 0건인 경우 상한은 `1 − 0.025^(1/n)` ≈ `3.7/n`이다 (rule of three `3/n`은 단측 95%라 쓰지 않는다). → **"0 escape"는 n이 작으면 아무것도 증명하지 않는다.**
- 랜덤성이 있는 실험(few-shot 샘플링 등)은 **최소 3 seed**, 평균 ± 표준편차로 보고한다.

---

## 6. Threshold 정책

- threshold는 **test set으로 정하지 않는다.** 반드시 `val`(또는 calibration split)에서 결정한다.
- **기본 규칙: val 정상 score 분위수** (코드: `calibrate()` in `src/evaluation/metrics.py`)

  ```text
  t_ng = Q(1 − f)   f = normal_ng_rate     : val 정상 중 NG가 되는 비율 상한 = 목표 과검률 (기본 1%)
  t_ok = Q(1 − r)   r = normal_review_rate : val 정상 중 약 r이 REVIEW 이상 (기본 10%)
  Q    = 관측값 중에서 고르는 경험 분위수 (numpy method="higher"), 0 ≤ f ≤ r ≤ 1
  ```

  불량 없이 정상만으로 기준을 잡는다 — 불량이 희소한 현장 조건과 같다. 불량은 test에서 처음 본다.
- **f는 제품 단위 목표에서 역산한다.** 제품당 라벨이 L장이고 라벨 오류가 독립이면
  제품 과검률 ≈ 1 − (1 − f)^L 이다 (f=1%, L=5 → 약 4.9%). public track은 L=1이라 f가 곧 제품 과검률이다.
- val이 작으면 분위수 해상도가 거칠다 (n=42 → 약 2.4% 단위). 보고할 때 val 정상 수를 함께 적는다.
- `REVIEW` 구간은 두 threshold(`ok`, `ng`)로 정의한다: `score < ok → OK`, `score > ng → NG`, 사이는 `REVIEW`.
  **경계값(`score == ok` 또는 `== ng`)은 `REVIEW`** 다 — 애매하면 사람에게 보낸다.
- threshold 값과 결정 근거는 MLflow에 param으로 기록한다.

---

## 7. Latency

**모델 inference 시간만 측정하면 안 된다.** 전체 pipeline을 측정한다.

```text
Camera acquisition
+ Image transfer
+ Product registration
+ Detection
+ ROI extraction
+ Label identity
+ Anomaly detection
+ OCR
+ Barcode/QR
+ Rule engine
+ Multi-camera aggregation
```

보고 항목:

| 항목 | 내용 |
|---|---|
| **P50 / P95 / P99** | 제품 1개 처리 기준 (label 1개 기준이 아님) |
| 구간 breakdown | 위 단계별 평균 시간 |
| 구간 분류 | `≤100 ms` / `100~500 ms` / `500~1000 ms` / `>1000 ms` |
| 환경 | device(GPU PC / Jetson Nano / Raspberry Pi), batch size, 입력 해상도, precision(fp32/fp16/int8) |

- **Target: 제품당 P95 < 1000 ms** (1차 목표).
- warm-up 제외, 최소 100회 반복 측정.

---

## 8. 비용 지표 (RQ4/RQ5용)

| 지표 | 정의 |
|---|---|
| **New-label onboarding cost** | 신규 라벨 1개 추가에 드는 (사람 작업시간 + 필요 이미지 수 + 연산시간). 재학습 필요 여부를 명시 |
| **Annotation cost** | 필요한 annotation 수준(image-level / bbox / mask)과 장수 |
| GPU / Memory | peak VRAM, 모델 크기, prototype DB 크기 |
| Training time | 학습 필요 시 |

---

## 9. 실험별 필수 보고 세트

모든 실험은 최소 다음을 MLflow에 기록한다.

```text
[params]  git_commit, dataset_version, config_path, model_name,
          threshold_ok, threshold_ng, n_shot, seed, device

[metrics] defect_escape_rate, critical_defect_escape_rate,
          false_positive_rate, precision, recall, f1, auprc, auroc,
          known_label_accuracy, unknown_label_detection_rate,
          review_rate_label, review_rate_product,
          latency_p50, latency_p95, latency_p99

[artifacts] config 사본, FP/FN gallery, latency breakdown, evidence 예시
```

비율 지표는 `{name}`(값) 외에 `{name}_k`, `{name}_n`, `{name}_ci95_low`, `{name}_ci95_high`를 함께
기록한다. 분모가 0인 지표(예: public track의 CDER)는 값을 기록하지 않고 `metrics.json`에 `null`로 남긴다.

### 9.1 예측 파일 (`predictions.csv`)

모든 run은 샘플별 예측을 artifact로 남긴다. **FN(escape) 샘플 추적과 Failure Gallery의 원본**이다.
예측값은 metadata(`expected_*`/`actual_*`)에 쓰지 않고 이 파일에만 쓴다.

| 열 | 내용 |
|---|---|
| `sample_id` | metadata 조인 키 |
| `decision` | `OK` / `REVIEW` / `NG` |
| `anomaly_score` | 판정 전 score (클수록 이상) |
| `predicted_label_id` | Label Identity 예측. 없으면 빈 값 |
| `latency_ms` | 샘플 1건 처리 시간 |
| `image_path`, `normal_or_defect`, `defect_type` | 실패 분석용으로 metadata에서 복사한 ground truth |

모델이 늘어나면 열을 **추가**한다(예: `prototype_score`, `open_set_score`, `ocr_result`,
`barcode_result`, `rule_violations`). 기존 열의 의미는 바꾸지 않는다.

함께 저장: `metrics.json`(지표 전체 + confusion matrix + REVIEW 처리 규칙), config 사본,
`datasets/registry.yaml` 사본.

---

## 10. XAI 평가 (Week 15, 22에서 구체화)

| 지표 | 내용 |
|---|---|
| Localization Fidelity | 설명 영역이 실제 결함 위치와 일치하는가 |
| Explanation Fidelity | 설명이 실제 판정 근거와 일치하는가 |
| Rule Trace Accuracy | 위반했다고 제시한 rule이 실제 위반 rule인가 |
| Prototype Relevance | 제시한 nearest prototype이 타당한가 |
| Stability | 입력 미세 변화에 설명이 안정적인가 |
| Explanation Latency | 설명 생성에 걸리는 추가 시간 |
| (optional) Human Agreement / Decision Assistance | 소규모 Human Study. **필수 dependency 아님** |

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-09-12 | Primary metric(DER/CDER) 확정, REVIEW 집계 규칙, 3-level, CI 보고 규칙, latency 정의 |
| v0.2 | 2026-09-12 | Product-level 집계 규칙 확정(severity 무관 NG 우선), 집계 키를 `unit_id`/`label_slot`으로 명시 |
| v0.3 | 2026-09-21 | 코드(`src/evaluation/metrics.py`)와 정의 일치: 지표별 REVIEW 처리표, 2×3 confusion, threshold 경계값=REVIEW, CI는 양측 95%(0건 상한 ≈3.7/n으로 정정), §9.1 `predictions.csv` 형식 |
| v0.4 | 2026-09-21 | §6 threshold 기본 규칙 확정: val 정상 분위수(f=1%, r=10%), f는 제품 단위 목표에서 역산 (#30) |
| v0.5 | 2026-09-21 | §2 DER 분해(defect_category별 / defect_type별) 추가 (#32) |
| v0.6 | 2026-09-26 | §3 Similar-label Confusion Rate 정의: E5 구간별 바꿔치기 불량의 DER (#35). 코드 `similar_label_confusion_rate` |
