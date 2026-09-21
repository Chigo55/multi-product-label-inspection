# 다품종·다라벨 제조 산업 불량 판독 연구 정리 문서

> 본 문서는 지금까지의 대화를 바탕으로 확정된 문제 정의, 조사 범위, 기술 후보, 연구 질문, 시스템 아키텍처, XAI 전략, 데이터 및 평가 설계, 논문화 전략, 24주 연구 로드맵을 하나의 기준 문서로 정리한 것이다.

---

# 1. 연구 배경

## 1.1 문제 상황

연구 대상은 제조 산업 현장에서 여러 품목에 부착된 여러 종류의 라벨을 자동으로 검사하는 비전 시스템이다.

예를 들어 다음과 같은 제품 구조를 가정한다.

```text
Product A
 ├─ a-1
 ├─ a-2
 └─ a-3

Product B
 ├─ b-1
 ├─ b-2
 ├─ b-3
 └─ b-4

Product C
 ├─ c-1
 └─ c-2

Product D
 ├─ d-1
 ├─ d-2
 └─ d-3
```

각 라벨은 다음과 같은 관계를 가질 수 있다.

- 같은 제품 안에서 서로 매우 유사할 수 있다.
- 같은 제품 안에서도 완전히 다른 디자인일 수 있다.
- 서로 다른 제품에 속하는 라벨끼리 매우 유사할 수 있다.
- 서로 다른 제품의 라벨끼리 완전히 다를 수 있다.
- 외형은 거의 동일하지만 OCR 문자열 한두 글자만 다를 수 있다.
- 외형은 동일하지만 Barcode/QR/DataMatrix 내용만 다를 수 있다.
- 외관은 정상인데 잘못된 제품에 부착될 수 있다.

따라서 이 문제를 단순한 이미지 분류 문제로 보면 안 된다.

핵심은 다음 네 문제를 동시에 다루는 것이다.

1. **라벨 자체의 외관 불량**
2. **라벨 종류의 식별**
3. **제품-라벨의 논리적 조합 검증**
4. **신규 품목·신규 라벨·미지 불량에 대한 확장성**

---

# 2. 최종 문제 정의

이번 연구의 최종 문제는 다음과 같이 정의한다.

> **다품종 제조 환경에서 제품별로 여러 라벨이 존재하고, 라벨 간 시각적 유사성과 차이가 혼재하며, 정상 데이터는 충분하지만 불량 데이터는 매우 희소한 조건에서, 신규 품목과 신규 라벨을 최소한의 재학습으로 추가할 수 있고, 미등록 라벨과 보지 못한 불량까지 검출하며, 판정 근거를 설명할 수 있는 산업용 Hybrid Inspection System을 연구한다.**

최종 시스템은 단순히 `OK / NG`만 출력하는 것이 아니라 다음 수준까지 출력하는 것을 목표로 한다.

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

판정이 불확실한 경우에는 강제 판정하지 않고 `REVIEW` 상태로 보내도록 한다.

---

# 3. 실제 적용 기본 시나리오

## 3.1 제품 ID

실제 생산 적용에서는 제품 ID가 이미 MES/PLC/ERP/Barcode 등의 외부 시스템에서 제공된다고 가정한다.

즉 기본 시나리오는 다음과 같다.

```text
MES / PLC / ERP
      ↓
Product ID
      ↓
해당 제품용 검사 Recipe 선택
```

그러나 연구 비교를 위해 이미지 자체에서 제품 종류를 판별하는 방식도 별도 후보로 포함한다.

---

## 3.2 촬영 환경

기본 현장 시나리오는 다음과 같다.

- 제품 전체가 촬영된다.
- 여러 카메라가 제품의 여러 면을 촬영할 수 있다.
- 컨베이어 이동 중 촬영될 수 있다.
- 제품별로 라벨의 위치가 서로 다를 수 있다.
- 조명, 반사, 그림자, 제품 위치, 회전, LOT, 카메라 조건 등이 변할 수 있다.

따라서 입력은 미리 잘라진 라벨 이미지 하나만을 가정하지 않는다.

---

# 4. 검사 대상 불량 범위

최종 조사 범위에는 다음 14가지 이상을 포함한다.

1. 라벨 누락
2. 다른 라벨 오부착
3. 위치 오류
4. 회전/기울기/방향 오류
5. 찢김
6. 구김
7. 오염/이물
8. 인쇄 흐림/번짐
9. 색상 이상
10. OCR 문자 내용 오류
11. Barcode/QR/DataMatrix 오류
12. Revision/Version 오류
13. 제품-라벨 조합 오류
14. 학습에서 보지 못한 Unknown defect

추가로 복수 라벨 관계 자체의 이상도 검사한다.

예:

```text
Expected:
a-1, a-2, a-3

Observed:
a-1, a-3

→ a-2 Missing
→ Product NG
```

---

# 5. 불량 유형의 구조화

불량은 크게 두 가지 축으로 나눈다.

## 5.1 Visual / Structural Defect

라벨 자체의 외관이 정상과 다른 경우이다.

예:

- Scratch
- Dirt
- Tear
- Blur
- Missing print
- Color anomaly
- Fold
- Occlusion
- Print degradation
- Unknown surface defect

이 부분은 주로 Industrial Anomaly Detection으로 다룬다.

---

## 5.2 Logical Defect

라벨 자체는 외관상 정상이어도 제품 문맥상 잘못된 경우이다.

예:

- Missing label
- Wrong label
- Wrong product-label combination
- Wrong position
- Wrong orientation
- OCR mismatch
- Barcode mismatch
- Revision mismatch

예를 들어 `b-3` 라벨이 매우 깨끗하게 인쇄되어 있어도 Product A에 붙어 있다면 NG다.

즉 다음 두 질문은 분리해야 한다.

```text
1. 이 라벨은 외관상 정상인가?
2. 이 라벨은 이 제품에 맞는 라벨인가?
```

---

# 6. 핵심 운영 요구사항

## 6.1 데이터 조건

기본 조건은 다음과 같다.

- 정상 이미지는 비교적 많이 확보 가능
- 실제 불량 이미지는 극히 적음
- 일부 불량은 아예 학습 시점에 존재하지 않을 수 있음
- 신규 라벨은 정상 이미지 몇 장만 등록 가능한 상황을 고려
- Annotation 비용 최소화가 최우선

따라서 supervised defect classification만으로는 충분하지 않다.

---

## 6.2 신규 품목/라벨

신규 라벨 추가 시 목표는 다음과 같다.

```text
정상 reference 이미지 등록
↓
Embedding / Prototype 생성
↓
즉시 검사 시작
```

기본 방향은 **재학습 없는 C 방식**이며 필요할 때만 추가학습한다.

신규 라벨 대응 목표:

- 1-shot
- 5-shot
- 10-shot
- 20-shot
- 50-shot

조건을 비교한다.

---

## 6.3 Unknown Label

등록되지 않은 라벨은 기존 class 중 하나로 억지로 분류하지 않는다.

최소 세 상태를 구분한다.

```text
KNOWN_EXPECTED
KNOWN_WRONG
UNKNOWN
```

최종적으로는:

```text
OK
NG
REVIEW
```

상태로 매핑한다.

---

## 6.4 Unknown Defect

학습 중 본 적 없는 불량도 정상과 다르면 NG로 검출할 수 있어야 한다.

따라서 다음을 별도로 평가한다.

- Seen defect 성능
- Unseen / Unknown defect 성능

---

# 7. 우선순위

시스템 목표 우선순위는 다음과 같이 확정했다.

```text
A > B > D > E > C
```

의미:

1. **불량 유출 최소화 / False Negative 최소화**
2. **정상품 과검 최소화**
3. **신규 품목/라벨 추가 편의성**
4. **유지보수 편의성**
5. **속도**

속도는 중요하지만 정확성 및 불량 유출 방지가 더 높은 우선순위다.

---

# 8. 지연시간 목표

1차 목표는 **제품당 전체 판독 1초 이내**이다.

비교 구간:

```text
≤ 100 ms
100 ~ 500 ms
500 ~ 1000 ms
> 1000 ms
```

단, 모델 inference 시간만 측정하면 안 된다.

전체 pipeline latency는 다음을 포함한다.

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

가능하면 `P50 / P95 / P99` latency를 함께 기록한다.

---

# 9. 핵심 연구 질문 6개

최종 연구 질문은 다음 6개로 확정했다.

## RQ1

**수십~수백 개의 제품/라벨 종류를 하나의 시스템이 어떻게 확장성 있게 식별할 수 있는가?**

핵심 후보:

- DINOv2 embedding
- Prototype learning
- Metric learning
- Retrieval
- Open-set recognition

---

## RQ2

**정상 데이터는 많지만 불량 데이터가 거의 없을 때 알려진/알려지지 않은 불량을 어떻게 검출할 것인가?**

핵심 후보:

- PatchCore
- EfficientAD
- AnomalyDINO
- Dinomaly
- INP-Former
- 기타 Industrial AD

---

## RQ3

**서로 거의 동일하게 생긴 라벨을 제품 정보, 위치, OCR, Barcode, visual feature를 이용해 어떻게 구분할 것인가?**

추가 XAI 관점:

> 그 판단 근거를 작업자에게 어떻게 설명할 것인가?

---

## RQ4

**신규 라벨을 1/5/10/20/50장의 정상 샘플만으로 어떻게 추가하며 전체 모델 재학습을 피할 수 있는가?**

핵심 방향:

- Training-free
- Few-shot
- Prototype
- Embedding retrieval
- Reference bank

---

## RQ5

**하나의 End-to-End 모델과 여러 전문 모델을 결합한 Hybrid Pipeline 중 어느 방식이 산업 환경에서 더 적합한가?**

비교 항목:

- 정확도
- 불량 유출률
- 신규 품목 추가성
- 유지보수성
- Explainability
- Auditability
- Traceability
- Latency

---

## RQ6

**불량 유출률을 최소화하면서 1초 이하 latency와 유지보수성을 동시에 만족시키는 시스템 구조는 무엇인가?**

---

# 10. 조사 기술 범위

초기 1차 조사 대상은 다음 20개 기술군이다.

1. Object Detection
2. Instance Segmentation
3. Image Classification
4. Fine-grained Visual Classification
5. Metric Learning
6. Siamese / Triplet Network
7. Few-shot Learning
8. Prototype Learning
9. Open-set Recognition
10. Industrial Anomaly Detection
11. OCR / Scene Text Recognition
12. Barcode/QR/DataMatrix Recognition
13. Vision Transformer
14. CLIP 계열 Vision-Language Model
15. DINO/DINOv2 Foundation Model
16. SAM 계열 segmentation
17. Multimodal/VLM
18. Pose/Keypoint/Registration
19. Continual Learning
20. Synthetic Data / Augmentation

최종 보고서에서는 실제 문제와 직접 연관성이 높은 5~8개 핵심 기술군으로 압축한다.

---

# 11. 최종 핵심 기술군

현재 기준으로 다음 8개가 핵심이다.

| 우선순위 | 기술 | 역할 |
|---|---|---|
| P0 | Detection / Registration / Pose | 라벨 위치 및 제품 좌표계 |
| P0 | Foundation Embedding / Metric / Prototype | 라벨 identity |
| P0 | Industrial Anomaly Detection | 외관 및 unknown defect |
| P0 | Logical / Rule-based Inspection | 누락·오부착·조합 오류 |
| P0 | OCR + Barcode/QR/DataMatrix | 내용 검증 |
| P0 | Open-set + Calibration + REVIEW | Unknown 및 fail-safe |
| P1 | Domain Robustness / Continual / Synthetic | 환경 변화 |
| P2 | VLM / MLLM | 설명 및 REVIEW 보조 |

---

# 12. 비교할 큰 아키텍처

## Architecture A — Classical Vision

```text
Registration
→ Template Matching
→ Feature Matching
→ OCR
→ Barcode
→ Rule Engine
```

목적:

- 기존 산업 Machine Vision이 어느 정도까지 해결 가능한지 확인
- AI 적용의 실제 이점을 정량화

---

## Architecture B — Standard Deep Learning Pipeline

```text
Detector
→ Classifier
→ Anomaly Detector
→ OCR
→ Rule Engine
```

---

## Architecture C — Foundation / Few-shot Hybrid

```text
Registration / Detector
→ DINOv2 Prototype
→ Open-set Recognition
→ Anomaly Detection
→ OCR / Barcode
→ Logical Rules
→ OK / REVIEW / NG
```

현재 가장 유력한 최종 구조다.

---

## Architecture D — Unified Model

```text
Dinomaly / INP-Former / Unified AD
→ OCR / Rule
```

다품종을 하나의 unified model로 처리하는 연구 방향이다.

---

# 13. 최종 권장 시스템 아키텍처

현재 최종 권장 구조는 다음 Hybrid Pipeline이다.

```text
                MES / PLC / ERP
                     │
                  Product ID
                     │
                     ▼
            ┌──────────────────┐
            │ Inspection Recipe│
            │                  │
            │ Expected Labels  │
            │ Position Rules   │
            │ OCR Rules        │
            │ Barcode Rules    │
            │ Thresholds       │
            └────────┬─────────┘
                     │
     ┌───────────────┼───────────────┐
     │ Camera 1      │ Camera 2      │ Camera N
     ▼               ▼               ▼
   Image           Image           Image
     └───────────────┼───────────────┘
                     ▼
        Product Registration / Pose
                     │
          Coordinate Normalization
                     │
                     ▼
             Label ROI / Detection
                     │
       ┌─────────────┼───────────────┐
       │             │               │
       ▼             ▼               ▼
 Label Identity   Visual AD      OCR / Code
DINOv2 Prototype  Model          Verification
       │             │               │
       └─────────────┼───────────────┘
                     ▼
             Logical Rule Engine
                     │
         Evidence / Decision Fusion
                     │
      ┌──────────────┼──────────────┐
      ▼              ▼              ▼
     OK             NG            REVIEW
```

---

# 14. Inspection Recipe 개념

모델이 모든 제품 규칙을 기억하도록 하지 않고, 제품별 검사 설정을 Recipe로 관리한다.

예:

```yaml
product: A
label: a-2
camera: CAM02

expected_roi:
  x1: ...
  y1: ...
  x2: ...
  y2: ...

position_tolerance_mm: 5
rotation_tolerance_deg: 3

identity_method: dinov2_prototype

expected_text:
  MODEL: XA-100

barcode:
  type: DataMatrix
  prefix: XA100

anomaly_model: anomaly_dino

thresholds:
  ok: 0.31
  ng: 0.52
```

신규 제품 E 추가 절차는 다음과 같은 방향을 목표로 한다.

```text
E 생성
→ e-1/e-2/e-3 등록
→ 정상 reference 촬영
→ Prototype 생성
→ OCR/위치/Barcode Rule 설정
→ Threshold calibration
→ 배포
```

---

# 15. 주요 모델 후보

## 15.1 PatchCore

역할:

- 정상 데이터 기반 Industrial Anomaly Detection
- 강력한 baseline
- patch memory bank 방식
- anomaly heatmap 생성 가능

연구에서 반드시 포함할 baseline으로 판단했다.

---

## 15.2 EfficientAD

역할:

- 고속 anomaly detection
- Edge/실시간 후보
- 다중 ROI 처리 환경에서 중요

특히 100/500/1000ms latency 비교에서 중요한 후보다.

---

## 15.3 AnomalyDINO

역할:

- DINOv2 기반 few-shot anomaly detection
- 정상 reference 소량 사용
- 신규 라벨 onboarding과 잘 맞음
- 재학습 부담을 낮추는 방향

---

## 15.4 Dinomaly

역할:

- Multi-class unsupervised anomaly detection
- 여러 품종을 unified model로 다루는 후보
- Architecture D의 핵심 baseline

---

## 15.5 INP-Former

역할:

- Universal / multi-class / few-shot AD 비교 후보
- Dinomaly와 함께 unified anomaly model 비교군

---

## 15.6 DINOv2 Prototype Retrieval

라벨 identity의 핵심 후보다.

기본 구조:

```text
Normal Reference Images
        ↓
      DINOv2
        ↓
Embedding / Prototype DB
```

검사:

```text
Input label
   ↓
DINOv2
   ↓
Embedding
   ↓
Nearest Prototype Search
```

출력 예:

```text
Expected: a-2

Top-1: b-3 = 0.94
Top-2: b-3 = 0.92
Top-3: a-2 = 0.61

→ Wrong Label 또는 REVIEW
```

---

# 16. OCR 전략

라벨 종류에 따라 OCR을 선택적으로 사용한다.

최종 방향은:

> **제품/라벨별 검사 프로파일을 정의하고, 순수 비전 방식과 OCR/코드 결합 방식을 비교**

예:

```text
a-1: Vision only
a-2: Vision + OCR
a-3: Vision + Barcode

b-1: Vision + OCR + QR
b-2: Vision only
```

OCR 후보:

- PaddleOCR / PP-OCR 계열
- 상용 OCR 엔진
- HALCON / Cognex OCR 등

필드 단위로 Rule을 적용한다.

```text
Expected:
MODEL = XA-100
REV   = 03

Actual:
MODEL = XA-101
REV   = 03

→ MODEL_MISMATCH
→ NG
```

---

# 17. Barcode / QR / DataMatrix 전략

전용 decoder를 사용한다.

예:

- ZXing
- OpenCV
- 산업용 verifier

Barcode 내용 판독과 Barcode 인쇄 품질 검증은 별개의 문제로 본다.

---

# 18. 위치 및 자세 검사

제품 자체의 위치와 회전이 달라질 수 있으므로 이미지 절대 좌표만 사용하지 않는다.

추천 구조:

```text
Camera Image
   ↓
Product Anchor / Keypoint
   ↓
Product Coordinate System
   ↓
Affine / Homography / Pose Normalize
   ↓
Expected Label ROI
```

정상 기준:

```text
Expected:
x, y, θ

Actual:
x', y', θ'
```

을 비교한다.

---

# 19. XAI 전략

XAI는 이번 연구에 포함하기로 확정했다.

단순 Grad-CAM 중심이 아니라 **Explainability-by-Design / Evidence-based XAI**를 목표로 한다.

최종 개념:

> **Evidence-based Explainable Multi-Product Multi-Label Industrial Inspection**

---

## 19.1 XAI 4단계

### L1 — Spatial Explanation

어디가 이상한가?

- anomaly heatmap
- defect mask
- bounding region

---

### L2 — Comparative Explanation

무엇과 달랐는가?

- nearest prototype
- 정상 reference 이미지
- similarity score

---

### L3 — Semantic Explanation

무엇이 잘못됐는가?

- OCR mismatch
- Barcode mismatch
- Position delta
- Rotation error

---

### L4 — Logical Explanation

왜 최종 NG인가?

예:

```text
Product A
Expected label: a-2
Observed label: b-3

Surface condition: Normal
Position: Normal
OCR: Mismatch

Rule violation:
Product A cannot contain b-3

→ NG: Wrong Label
```

---

# 20. XAI의 Evidence Graph

최종적으로 다음과 같은 설명 구조를 연구한다.

```text
NG
│
├─ Visual Evidence
│   └─ anomaly region
│
├─ Reference Evidence
│   └─ closest prototype
│
├─ Semantic Evidence
│   └─ OCR / barcode mismatch
│
├─ Geometric Evidence
│   └─ position / rotation difference
│
└─ Logical Evidence
    └─ violated product-label rule
```

판정과 설명의 역할은 분리한다.

```text
Models + Rules
→ OK / REVIEW / NG

Evidence
→ XAI explanation
```

XAI가 직접 최종 판정기를 흔들지 않도록 한다.

단, `REVIEW` 상태에서는 VLM이나 무거운 XAI를 추가 분석 도구로 사용할 수 있다.

---

# 21. VLM의 역할

VLM은 최종 판정기보다는 **설명자 또는 REVIEW 보조자**로 보는 것이 현재 방향이다.

예:

```text
Rule Engine
DINOv2
Anomaly Detector
OCR
↓
Evidence
↓
VLM
↓
Natural-language explanation
```

예시 설명:

> 제품 A에는 a-2 라벨이 요구되지만 현재 이미지는 b-3 reference와 가장 유사합니다. 외관 이상 점수는 정상 범위이므로 물리적 훼손보다는 오부착 가능성이 높습니다. OCR에서도 예상 값과 실제 값이 일치하지 않습니다.

---

# 22. XAI 평가

단순히 설명을 만든 것으로 끝내지 않고 XAI 자체를 평가한다.

평가 후보:

- Localization Fidelity
- Explanation Fidelity
- Stability
- Prototype Relevance
- Rule Trace Accuracy
- Human Agreement
- Decision Assistance
- Explanation Latency

현장 작업자를 확보할 수 있다면 작은 Human Study도 고려한다.

```text
Without XAI
vs
With XAI

측정:
- REVIEW 판단 시간
- 판단 정답률
- 설명 유용성
```

Human Study는 필수 dependency로 두지 않는다.

---

# 23. 데이터 전략

연구 데이터는 두 개 트랙으로 구성한다.

## Track A — 공개 Industrial AD Benchmark

후보:

- MVTec AD
- MVTec LOCO AD
- MVTec AD 2
- VisA
- Real-IAD
- MPDD
- BTAD

목적:

- 기존 연구와 공정한 비교
- AD baseline 검증
- Domain shift / logical anomaly 평가

---

## Track B — 자체 Multi-Product Multi-Label Benchmark

공개 가능한 synthetic/public-source 기반 benchmark를 제작한다.

사내 데이터는 가능할 경우 별도의 비공개 validation set으로 사용한다.

사내 데이터 사용 범위는 아직 확정되지 않았다.

기본 전략:

```text
Main Research
→ Public benchmark + Public/Synthetic custom benchmark

Optional External Validation
→ Internal manufacturing data
```

즉 사내 데이터 승인 여부가 연구 전체를 막지 않도록 한다.

---

# 24. 자체 Benchmark 규모

## Pilot

```text
3 products
3~5 labels/product
약 10~15 label identities
```

## Main Benchmark

```text
8~12 products
3~8 labels/product
약 30~60 label identities
```

다음 관계를 의도적으로 포함한다.

```text
Same product / visually similar
Same product / visually different
Different product / visually similar
Different product / visually different
OCR-only difference
Barcode-only difference
```

---

# 25. Synthetic Defect 전략

Synthetic defect를 적극 활용한다.

예:

- OCR 문자열 변경
- 위치 이동
- 회전
- 라벨 일부 제거
- 잘못된 라벨로 교체
- 오염
- Scratch
- Blur
- Print missing
- Color variation
- Occlusion

기본 전략:

> Synthetic으로 학습/실험을 구성하고 가능한 실제 defect로 최종 검증

특히 logical defect는 synthetic으로 정확한 ground truth를 만들기 쉽다.

---

# 26. Annotation 최소화

Annotation 최소화가 최우선이다.

전체 데이터:

```text
product_id
label_id
OK / NG
```

정도만 기본으로 유지한다.

일부 평가 subset:

```text
bounding box
defect type
defect mask
```

예시:

```text
10,000 images
→ image-level metadata

500~1,000 images
→ bounding box / defect type

100~300 images
→ pixel-level defect mask
```

---

# 27. 불량 Severity

불량을 동일하게 취급하지 않는다.

```text
Critical
Major
Minor
```

예시:

## Critical

- Wrong product-label
- Barcode content error
- Critical model number error
- Missing mandatory label

## Major

- Tear
- Significant print defect
- Wrong position

## Minor

- Small contamination
- Small print density variation

최우선 KPI는 Critical Defect Escape다.

---

# 28. 평가 단위

세 단계 모두 평가한다.

```text
Level 1: Defect-level
Level 2: Label-level
Level 3: Product-level
```

제품 단위에서는 여러 라벨 중 하나라도 Critical NG면 Product NG가 될 수 있다.

---

# 29. 핵심 평가 지표

Accuracy를 대표 지표로 사용하지 않는다.

우선순위:

1. Defect Escape Rate / False Negative Rate
2. Critical Defect Recall
3. False Reject / False Positive Rate
4. REVIEW Rate
5. AUPRC
6. F1
7. AUROC
8. Unknown Detection
9. Localization
10. Latency
11. New-label onboarding cost
12. Annotation cost
13. GPU/Memory requirement

Critical defect가 0 escape여도 단순히 `Recall = 100%`라고만 쓰지 않는다.

예:

```text
Critical defects:
0 / 1,200 escaped

Observed FNR:
0%

95% confidence upper bound:
...
```

처럼 표본 수와 신뢰구간까지 보고한다.

---

# 30. 6개 핵심 실험 시나리오

## E1 — Seen Label

기존 학습/등록 라벨 정상 및 불량 검사.

---

## E2 — Few-shot New Label

신규 라벨에 대해:

```text
1 / 5 / 10 / 20 / 50
```

개의 정상 reference만 제공.

---

## E3 — Unknown Label

등록되지 않은 라벨이 기존 라벨로 오인되는지 평가.

---

## E4 — Unknown Defect

학습에서 보지 못한 불량 검출.

---

## E5 — Similar Label

의도적으로 매우 유사한 라벨끼리 비교.

난이도:

```text
Easy
→ 외형 완전히 다름

Medium
→ 같은 Layout

Hard
→ 문자 한두 글자만 다름

Extreme
→ Barcode/OCR만 다름
```

---

## E6 — Domain Shift

다음 변화에서 robustness 평가.

- Lighting
- Production LOT
- Position
- Rotation
- Camera
- Background
- Reflection
- Blur

---

# 31. 연구용 하드웨어

초기 연구는 일반적인 NVIDIA GPU 1장 환경을 기준으로 설계한다.

현재 보유 장비:

- Jetson Nano
- Raspberry Pi

역할:

## GPU PC

Full Hybrid Pipeline 개발 및 benchmark.

## Jetson Nano

- 실제 Edge 후보
- 최종 후보 경량화 및 성능 비교
- 가능하면 실제 inference 실험

## Raspberry Pi

- Classical
- OCR
- Barcode
- Rule
- Lightweight inference
- 배포 가능성 확인

Raspberry Pi에서 전체 AI pipeline 1초 이내를 필수 목표로 하지는 않는다.

---

# 32. 실험 관리

기본 스택:

```text
Python
PyTorch
Anomalib
OpenCV
DINOv2
PaddleOCR
```

실험 관리:

```text
Git
+
YAML Config
+
MLflow
```

모든 실험에서 기록:

```text
Git commit
Dataset version
Model version
Hyperparameters
Threshold
FNR
FPR
AUPRC
AUROC
Latency
Artifacts
```

추천 repository 구조:

```text
industrial-label-inspection/
├── configs/
├── datasets/
├── models/
├── pipelines/
├── evaluation/
├── xai/
├── tools/
├── experiments/
├── reports/
└── tests/
```

---

# 33. 논문 조사 범위

기반 논문은 과거까지 추적하되 성능 비교와 최신 기술 동향은 최근 5년을 중심으로 본다.

주요 학회/저널:

- CVPR
- ICCV
- ECCV
- NeurIPS
- ICLR
- AAAI
- WACV
- BMVC
- IEEE TPAMI
- IEEE T-IE
- IEEE T-II
- Pattern Recognition
- Machine Vision and Applications

상용 산업 비전 접근법도 비교한다.

- Cognex
- KEYENCE
- MVTec HALCON
- 기타 산업용 Machine Vision

비교 축:

```text
Classical Vision
Deep Learning
Hybrid
```

---

# 34. 재현 가능성 정책

모든 연구를 조사하되 실제 후보 선정 시 다음을 우선한다.

- 공개 코드
- Pretrained weights
- 재현 가능성
- 라이선스 명확성
- 학습 비용
- 배포 난이도
- 상업적 활용 가능성

즉 논문 성능만 높은 방법보다 실제 재현 가능한 방법을 우선한다.

---

# 35. 논문화 전략

6개월 뒤 목표는 **논문 제출 직전 수준의 실험 결과**이다.

초기 목표 수준:

> 산업 AI/비전 분야에서 명확한 방법론 및 실험 기여가 가능한 수준

결과가 강하면 CVPR/ICCV/ECCV급 방향으로 확장한다.

---

## 35.1 연구 novelty 후보

세 방향을 검토했다.

### A — Few-shot / Training-free

정상 이미지 몇 장으로 신규 라벨 추가.

### B — Logical + Visual Hybrid

Visual AD와 제품/라벨/OCR/위치/Rule을 결합.

### C — Explainable Evidence Fusion

Visual / OCR / Position / Prototype / Rule evidence를 통합하고 설명.

최종 전략:

> **A + B를 연구 본체로 하고 C를 XAI contribution으로 추가**

---

## 35.2 논문 방향 결정 시점

Month 3 종료 시점에 Research Gap을 보고 최종 방향을 결정한다.

```text
Few-shot 성능이 부족
→ Training-free / Few-shot novelty

Logical anomaly에서 실패
→ Logical-Visual Fusion novelty

XAI가 강한 차별점
→ Evidence-based XAI novelty

방법론 novelty가 약함
→ Benchmark / System contribution 강화
```

---

# 36. 연구 시간

총 기간:

```text
6개월
24주
```

연구 가능 시간:

```text
주 10~15시간
주로 주말
```

운영 원칙:

> **한 주말 = 하나의 명확한 실험 목표**

---

# 37. 6개월 전체 Phase

| 기간 | Phase | 목표 |
|---|---|---|
| Month 1 | 문제·환경 구축 | 문헌/데이터/평가 인프라 |
| Month 2 | Baseline | Classical + AD baseline |
| Month 3 | 핵심 문제 검증 | Few-shot/Open-set/Logical |
| Month 4 | Proposed Method | Hybrid + XAI |
| Month 5 | Main Experiment | Benchmark + Ablation |
| Month 6 | Validation/Paper | Edge/XAI/논문화 |

---

# 38. Week 1 — Research Protocol

읽을 핵심 논문:

- MVTec AD
- MVTec LOCO AD
- PatchCore
- EfficientAD
- DINOv2

목표:

- Git repository
- Python/PyTorch
- MLflow
- YAML config
- RQ1~RQ6 정리
- Metric 정의

산출물:

```text
research_protocol_v1.md
```

Done:

```text
□ Repository
□ Environment
□ MLflow
□ Config format
□ Research Questions
□ Evaluation metrics
```

---

# 39. Week 2 — Dataset Schema / Benchmark Design

Public Track:

- MVTec AD
- MVTec LOCO
- VisA

Custom Benchmark schema:

```text
product_id
label_id
camera_id
expected_label
actual_label
expected_position
actual_position
expected_text
actual_text
expected_code
actual_code
defect_type
defect_severity
is_known_label
is_known_defect
split
```

Done:

```text
□ Dataset schema
□ Severity
□ Split policy
□ E1~E6
□ Leakage rule
```

---

# 40. Week 3 — Pilot Benchmark

Pilot:

```text
3 products
약 10~15 label identities
```

반드시 포함:

- same-product similar
- cross-product similar
- OCR-only difference
- Barcode-only difference
- Unknown label

Synthetic defect generator 최소 3종 구현.

---

# 41. Week 4 — Evaluation Pipeline

자동 계산:

- Defect Escape
- Critical Escape
- FPR
- Precision
- Recall
- F1
- AUPRC
- AUROC
- Unknown metrics
- REVIEW rate
- Label-level
- Product-level
- P50/P95/P99 latency

Month 1 Gate:

> 평가 파이프라인이 완성되기 전에는 모델을 늘리지 않는다.

---

# 42. Week 5 — Classical Baseline

구현:

```text
Registration
Template Matching
Feature Matching
OCR
Geometry Rule
Barcode
```

실험:

- Seen label
- Similar label
- Position
- Orientation
- OCR mismatch

---

# 43. Week 6 — PatchCore

실험:

```text
Normal-only
→ Seen defect
→ Unknown defect
```

측정:

- AUROC
- AUPRC
- FNR
- latency
- FP/FN gallery

---

# 44. Week 7 — EfficientAD

PatchCore와 동일 protocol로 비교.

핵심:

- FNR
- FPR
- unknown defect
- latency
- training time
- memory

---

# 45. Week 8 — Baseline Gate

새 모델을 늘리기보다 실패 사례를 분석한다.

최소:

```text
False Negative 20
False Positive 20
```

실패 카테고리:

- Lighting
- Reflection
- Position
- Similar label
- OCR difference
- Small defect
- Logical anomaly
- Unknown

Gate:

> Baseline 재현이 불안정하면 Month 3로 진행하기 전에 수정.

---

# 46. Week 9 — DINOv2 Prototype Retrieval

Reference count:

```text
1
5
10
20
50
```

평가:

- Known label accuracy
- Similar label confusion
- Unknown rejection
- New-label onboarding time

---

# 47. Week 10 — AnomalyDINO

비교:

```text
PatchCore
EfficientAD
AnomalyDINO
```

Few-shot 조건:

```text
1 / 5 / 10 / 20 / 50
```

핵심 질문:

> 신규 라벨 정상 이미지 몇 장만으로 외관 검사까지 가능한가?

---

# 48. Week 11 — Open-set Recognition

상태:

```text
KNOWN_EXPECTED
KNOWN_WRONG
UNKNOWN
```

핵심은 threshold calibration이다.

---

# 49. Week 12 — Logical Inspection / Research Gap Gate

비교:

```text
A. Vision only
B. Vision + Product Context
C. Vision + Product + OCR
D. Vision + Product + OCR + Rules
```

Month 3 종료 시 논문 방향 결정.

---

# 50. Week 13 — Hybrid Pipeline v1

연결:

```text
Product ID
→ Registration / ROI
→ DINOv2 Identity
→ Open-set
→ Anomaly Detector
→ OCR
→ Barcode
→ Rule Engine
→ Fusion
```

출력:

```text
OK / REVIEW / NG
```

---

# 51. Week 14 — Evidence Fusion

Evidence:

```text
Visual identity score
Anomaly score
OCR match
Barcode match
Position score
Open-set score
```

방향:

```text
Critical deterministic rule
+
Calibrated probabilistic evidence
```

Critical rule 예:

```text
Barcode mismatch
→ Immediate NG
```

---

# 52. Week 15 — Evidence-based XAI

설명 요구사항:

```text
왜 NG인가?
어디가 NG인가?
무엇과 비교했는가?
어떤 Rule을 위반했는가?
```

출력 예:

```text
NG
Reason: WRONG_LABEL

Expected: a-2
Nearest Prototype: b-3 / 0.947

OCR
Expected: XA-100
Actual: XB-100

Surface anomaly: Normal

Rule:
Product A cannot contain b-3
```

---

# 53. Week 16 — Proposed Method Gate

비교:

```text
Classical
PatchCore
EfficientAD
DINOv2 Prototype
Hybrid
```

GO 기준:

Hybrid가 최소 하나 이상의 핵심 축에서 명확한 장점이 있어야 한다.

예:

- Critical escape 감소
- Unknown detection 향상
- Few-shot 성능 향상
- Annotation cost 감소
- Explainability 향상

---

# 54. Week 17 — Main Benchmark 확장

Pilot:

```text
3 products
10~15 labels
```

에서 Main:

```text
8~12 products
30~60 labels
```

로 확대.

---

# 55. Week 18 — E1~E3

집중 실험:

- E1 Seen Label
- E2 Few-shot New Label
- E3 Unknown Label

Reference:

```text
1 / 5 / 10 / 20 / 50
```

가능하면 multiple seed.

---

# 56. Week 19 — E4~E6

집중 실험:

- E4 Unknown Defect
- E5 Similar Label
- E6 Domain Shift

특히 E5가 중요한 핵심 시험이다.

---

# 57. Week 20 — Feature Freeze

이 시점 이후 새로운 기능 추가를 거의 중단한다.

남은 작업:

```text
Experiments
Ablation
Statistics
Failure Analysis
Paper
```

---

# 58. Week 21 — Ablation Study

Full system에서 하나씩 제거한다.

```text
Full

- Product Context
- OCR
- Prototype
- Anomaly Detection
- Open-set
- Logical Rule
```

목표:

> Hybrid가 왜 필요한가를 정량적으로 입증

---

# 59. Week 22 — XAI / Human-in-the-loop

정량평가:

- Explanation correctness
- Localization
- Rule trace accuracy
- Prototype relevance

가능하면 소규모 Human Study:

```text
Without explanation
vs
With explanation
```

측정:

- 판단 정답률
- 평균 REVIEW 시간

---

# 60. Week 23 — Edge / Latency / Failure Analysis

GPU PC:

- Full pipeline

Jetson Nano:

- Edge optimized pipeline

Raspberry Pi:

- Classical/OCR/Barcode/Lightweight

Latency:

```text
P50
P95
P99
```

및:

```text
<100 ms
100~500 ms
500~1000 ms
>1000 ms
```

---

# 61. Week 24 — Paper Packaging

논문 구조:

```text
1. Introduction
2. Related Work
   2.1 Industrial AD
   2.2 Few-shot / Open-set
   2.3 Logical Inspection
   2.4 XAI
3. Problem Definition
4. Benchmark
5. Proposed Method
6. Experimental Setup
7. Results
8. Ablation
9. Explainability
10. Failure Analysis
11. Limitations
12. Conclusion
```

이 시점에는 새 실험을 무한히 추가하지 않고 현재 결과로 논문 초안을 완성한다.

---

# 62. 논문 읽기 순서

## Tier 1 — 필수 정독

- MVTec AD
- MVTec LOCO AD
- PatchCore
- EfficientAD
- DINOv2
- AnomalyDINO
- Dinomaly
- INP-Former
- OpenMax
- Prototypical Networks

---

## Tier 2 — 비교용

- WinCLIP
- PromptAD
- AA-CLIP
- UniAD
- Reverse Distillation
- FastFlow
- CFLOW-AD
- SimpleNet

---

## Tier 3 — 방향 확정 후

- Logical AD
- Continual Learning
- Synthetic Anomaly
- XAI
- VLM-based AD
- Domain Robustness

---

# 63. 주말 연구 루틴

권장 패턴:

| 시간 | 작업 |
|---|---|
| 토 오전 | 관련 논문 정독 |
| 토 오후 | 구현 |
| 토 저녁 | 첫 실험 |
| 일 오전 | 본 실험 |
| 일 오후 | 결과/실패 분석 |
| 일 저녁 | MLflow + 연구노트 + 다음 주 계획 |

매주 1페이지 Research Note를 남긴다.

템플릿:

```text
Question
이번 주 무엇을 검증했나?

Hypothesis
예상은 무엇이었나?

Experiment
어떻게 테스트했나?

Result
숫자는?

Failure
어디에서 실패했나?

Interpretation
왜 그런 것 같은가?

Next Question
다음 주 무엇을 검증할 것인가?
```

---

# 64. Go / No-Go 기준

## Week 8

> 기존 모델을 재현하지 못했다면 신규 모델 개발 금지.

## Week 12

> 명확한 Research Gap이 보이지 않는다면 Proposed Method 개발 금지.

## Week 16

> 새 방법이 baseline 대비 의미 있는 장점이 없다면 복잡도를 더 늘리지 않고 방향 수정.

## Week 20

> 기능 개발 종료. 실험·Ablation·논문화 집중.

## Week 24

> 추가 실험 욕심보다 현재 결과로 논문 초안 완성.

---

# 65. 최종 산출물

6개월 종료 시 다음을 목표로 한다.

## 65.1 Literature Review

- 30~50편
- 기술 taxonomy
- 데이터셋
- 모델
- 코드 공개 여부
- 라이선스
- 재현성
- 속도
- 이번 문제 적합도

---

## 65.2 Benchmark

- Public Industrial AD Track
- Multi-Product Multi-Label Track
- Synthetic defect generator
- Evaluation protocol

---

## 65.3 Baseline

- Classical
- Standard Deep Learning
- Foundation/Few-shot
- Hybrid
- Unified

---

## 65.4 Proposed Method

현재 가장 유력한 방향:

> **Context-aware Training-free Visual-Logical Hybrid Inspection**

---

## 65.5 XAI

최종 방향:

> **Hybrid Inspection Pipeline + Evidence-based XAI + Human-in-the-loop**

---

## 65.6 논문 수준 결과

- Full benchmark
- Ablation
- Failure analysis
- Few-shot analysis
- Unknown label
- Unknown defect
- Similar label
- Domain shift
- Latency
- Edge feasibility
- XAI evaluation

---

# 66. 현재 가장 유력한 최종 연구 방향

현재까지의 논의를 한 문장으로 정리하면 다음과 같다.

> **정상 reference 몇 장만으로 신규 라벨을 등록할 수 있는 DINOv2 기반 prototype/open-set 구조와, normal-only industrial anomaly detection, OCR/Barcode/Position/Product Context 기반 logical inspection을 결합하고, 각 판정의 visual·semantic·geometric·logical evidence를 설명하는 다품종·다라벨 제조용 Explainable Hybrid Inspection Framework를 구축하고 평가한다.**

---

# 67. 현재 가장 유력한 최종 시스템

```text
MES / PLC Product Context
        +
Inspection Recipe
        +
Product Registration
        +
Label ROI / Detection
        +
DINOv2 Prototype Identity
        +
Open-set Recognition
        +
Normal-only Anomaly Detection
        +
OCR / Barcode
        +
Logical Rule Engine
        +
Evidence Fusion
        +
Explainable Evidence
        ↓
OK / REVIEW / NG
```

---

# 68. 상용 시스템 비교 방향

연구 모델만이 아니라 실제 산업 솔루션도 조사 대상으로 포함한다.

비교:

```text
Cognex
KEYENCE
MVTec HALCON
기타 Machine Vision
```

핵심 비교 질문:

- 정상 데이터만으로 anomaly 학습 가능한가?
- Rule과 AI를 결합하는가?
- OCR/Barcode 지원은?
- Logical anomaly는 어떻게 처리하는가?
- REVIEW / Unclassified 상태가 있는가?
- Edge 배포 가능한가?
- 설명 가능성은?
- 유지보수와 신규 품목 추가 방식은?

---

# 69. 연구에서 하지 않을 것

현재 6개월 범위에서 우선순위를 낮춘 항목도 명확하다.

- 처음부터 End-to-End 거대 모델 신규 설계
- 모든 프레임에 SHAP/LIME 적용
- 실제 컨베이어/PLC 통합을 필수 성공조건으로 설정
- 모든 불량에 pixel-level annotation 생성
- 사내 데이터 승인을 기다리느라 연구 중단
- Raspberry Pi에서 Full Pipeline 1초 내 실행을 필수조건으로 설정
- 논문 방향을 Month 1부터 고정
- Benchmark 수치만 보고 실제 현장 성능을 추정

---

# 70. 확정된 주요 의사결정 로그

## 문제 정의

- 제품 정보는 외부 시스템 제공을 기본으로 하되 이미지 기반 식별도 비교
- 제품 전체 이미지 + 다중 카메라 + 컨베이어 환경 고려
- 라벨 위치는 품목마다 다름
- 14개 이상 불량 유형 포함
- Unknown defect 포함
- Unknown label 포함
- OK/NG뿐 아니라 원인/위치/실제·예상 라벨까지 출력
- REVIEW 상태 포함

## 데이터

- 정상 많음, 불량 희소
- 신규 라벨 few-shot
- Annotation 최소화
- Public + Custom benchmark 병행
- Synthetic defect 허용
- 사내 데이터는 optional external validation

## 연구

- End-to-End와 Pipeline 모두 조사
- Classical / Deep / Hybrid 비교
- 실제 후보는 재현성 우선
- 상용 산업 비전 접근법도 비교
- 최근 5년 중심 + foundational paper 추적
- 최종 5~8개 핵심 기술군으로 압축

## 시스템

- Hybrid Pipeline이 현재 최종 권장
- DINOv2 Prototype
- Open-set
- AnomalyDINO / EfficientAD / PatchCore / Dinomaly 등 비교
- OCR/Barcode/Rule 결합
- XAI는 Evidence-based 구조
- VLM은 REVIEW 및 explanation 보조

## 평가

- 불량 유출률 최상위
- Critical/Major/Minor
- Defect/Label/Product 3-level
- E1~E6
- 100/500/1000ms
- P50/P95/P99
- confidence interval 포함
- Ablation 필수

## 일정

- 6개월
- 24주
- 주말 10~15시간
- Week 8 / 12 / 16 / 20 / 24 Gate
- Month 3에 논문화 방향 확정

---

# 71. 자동 추적 Task

대화 중 다음 자동화 Task를 생성했다.

**이름**

```text
산업 이상탐지 신논문 추적
```

**목적**

다음 분야의 최신 논문을 지속적으로 확인한다.

- Industrial Anomaly Detection
- Manufacturing Vision Inspection
- Few-shot Anomaly Detection
- Open-set Recognition
- Multi-class Anomaly Detection
- Logical Anomaly Detection

새롭고 의미 있는 논문이 발견될 경우 다음 내용을 요약한다.

- 핵심 기여
- 사용 데이터셋
- 공개 코드 여부
- 제조 다품종·다라벨 검사 문제와의 관련성

의미 있는 신규 논문이 없으면 알림을 보내지 않는 조건으로 설정했다.

---

# 72. 첫 번째 실제 실행 목표

24주 계획에서 가장 먼저 해야 할 일은 모델 학습이 아니다.

첫 주말의 목표:

> **Research Repository + MLflow + Dataset Schema + Evaluation Metrics + Literature Matrix의 뼈대를 완성한다.**

초기 완료조건:

```text
□ Git repository 생성
□ Python/PyTorch 환경 구축
□ MLflow 연결
□ YAML config 정의
□ Dataset schema 정의
□ RQ1~RQ6 README 작성
□ 핵심 metric 구현
□ 첫 Literature Matrix 작성
```

---

# 73. 최종 요약

이번 연구의 핵심은 단순한 “불량 이미지 분류”가 아니다.

다음 문제를 하나의 시스템에서 동시에 해결해야 한다.

```text
다품종
+
제품별 복수 라벨
+
유사 라벨
+
다른 제품 간 유사 라벨
+
불량 데이터 희소
+
신규 라벨 지속 추가
+
Unknown Label
+
Unknown Defect
+
Logical Defect
+
OCR / Barcode
+
Position / Rotation
+
Domain Shift
+
Annotation 최소화
+
1초 이하 판독
+
Evidence-based Explainability
```

현재 가장 적합하다고 판단한 연구 방향은:

> **Few-shot / Training-free Label Identity + Normal-only Anomaly Detection + Logical Rule/Metadata + Evidence-based XAI를 결합한 Explainable Hybrid Industrial Inspection Framework**

이다.

그리고 연구의 성공 기준은 MVTec 등의 공개 benchmark에서 가장 높은 AUROC를 기록하는 것이 아니라,

> **실제 다품종·다라벨 제조 환경에서 신규 라벨을 쉽게 추가하면서 Critical Defect Escape를 최소화하고, Unknown 상황을 안전하게 거부하며, 작업자에게 판정 근거를 설명할 수 있는 구조를 검증하는 것**

이다.
