# PatchCore

> *Towards Total Recall in Industrial Anomaly Detection*
> Roth, Pemula, Zepeda, Schölkopf, Brox, Gehler — CVPR 2022
> https://arxiv.org/abs/2106.08265 / 코드: https://github.com/amazon-science/patchcore-inspection
>
> **상태: 사전 정리 초안(Week 1).** 원문을 훑으면서 ✅ 확인 / ✏️ 정정한다. 숫자에는 `?`를 붙여 두었다.

---

## 오늘 집중해서 볼 질문

> **불량 샘플 없이 어떻게 정상 feature로 anomaly를 찾는가?**

한 줄 답: **"정상 패치들의 사전(memory bank)을 만들어 두고, 테스트 패치가 그 사전에서 얼마나 멀리 떨어져 있는지를 점수로 쓴다."**

수식을 다 이해할 필요는 없다. 다음 4개의 설계 결정만 이해하면 된다.

| 결정 | 무엇을 | 왜 |
|---|---|---|
| **① 중간층 feature 사용** | ImageNet pretrained WideResNet-50의 layer2+layer3 `?` | 너무 얕으면 일반적이고, 너무 깊으면(layer4) ImageNet class에 치우치고 해상도가 낮다 |
| **② Local neighborhood aggregation** | 이웃 패치들을 adaptive average pooling으로 묶음 `?` | 깊은 층을 쓰지 않고도 receptive field를 키운다 |
| **③ Greedy coreset subsampling** | 정상 패치 전체 대신 대표 부분집합만 저장 (예: 1~10%) `?` | 전부 저장하면 메모리/검색 비용이 폭발. coverage를 유지하며 압축 |
| **④ Nearest-neighbor + re-weighting** | 최근접 거리 = 이상 점수, 이웃 밀도로 보정 `?` | 메모리뱅크에서 그 자체로 고립된 패치와 매칭됐다면 신뢰도를 조정 |

**학습(gradient update)이 사실상 없다.** 정상 이미지를 통과시켜 feature를 모아 coreset으로 줄이는 것이 전부다.
→ 이 성질이 **RQ4(신규 라벨 등록)** 에 중요하다.

---

## 6항목 요약

### Problem
Cold-start industrial anomaly detection: **정상 이미지만** 주어진 상태에서 이상 탐지 + 국소화.

### Input
단일 이미지(주로 크롭된 단일 객체). MVTec AD 기준 제품 category별로 별도 모델.

### Training Data
정상 이미지만. category당 수백 장 수준. 추가로 **few-shot 조건**도 보고 `?`

### Method
`정상 이미지 → pretrained CNN 중간층 patch feature → neighborhood aggregation → coreset으로 memory bank 구성`
`테스트 이미지 → 같은 feature → 각 패치의 최근접 거리 → patch score map → image score = max`

### Output
- image-level anomaly score
- pixel-level anomaly map (patch score를 upsample) → **heatmap = L1 Spatial Explanation의 재료**

### 성능 `?`
MVTec AD image-level AUROC 약 99.1% (ensemble 99.6%) `?`

### ⭐ Limitation for my problem

1. **Label identity를 전혀 모른다.** "정상과 다른가"만 답하고 "이게 a-2인가 b-3인가"는 답하지 않는다.
   → `b-3`가 깨끗하게 인쇄되어 Product A에 붙어 있으면 **PatchCore는 정상이라고 말한다.** 이번 문제의 CRITICAL 결함을 원리적으로 놓친다.
2. **Logical defect를 못 잡는다.** 개수/조합/문맥 위반은 국소 패치 거리로 표현되지 않는다. (→ LOCO 논문이 지적한 바로 그 지점)
3. **Multi-class 확장 비용.** 기본 설계가 category당 1 모델이다.
   제품/라벨이 30~60종이면 memory bank가 몇 개가 되는가? **메모리와 검색 latency가 RQ1/RQ6의 직접 위험요소.**
   → Week 6에서 반드시 **bank 크기 × 검색 시간**을 측정할 것.
4. **위치/자세 정규화를 전제한다.** 제품 위치·회전이 흔들리는 컨베이어 환경에서는
   registration 없이 쓰면 정상 변동을 이상으로 잡는다(과검↑). → Architecture에 registration이 앞단에 필요한 이유.
5. **OCR/Barcode 내용 검증 불가.**
6. **설명이 heatmap 한 종류뿐이다.** "어디가 이상한가"(L1)까지만 답하고,
   "무엇과 달랐는가"(L2) / "왜 NG인가"(L4)는 답하지 않는다. → Evidence-based XAI가 필요한 이유.
7. **ImageNet feature 의존.** 라벨처럼 텍스트/선/코드가 지배적인 도메인에서 중간층 feature가 충분한지는 미검증.
   → DINOv2 backbone과의 비교가 필요한 이유(Week 9~10).

### 활용 계획
- **Week 6의 필수 baseline.** 이 연구의 모든 AD 비교는 PatchCore를 기준점으로 삼는다.
- 측정: AUROC / AUPRC / **DER** / latency / memory bank 크기 / FP·FN gallery 20장씩.
- 그리고 위 Limitation 1·2를 **정량적으로 재현**하는 것이 Week 6의 진짜 목적이다
  ("wrong label인데 anomaly score가 정상 범위"인 사례를 확보).

---

## 확인 체크리스트 (읽으면서)

- [ ] 사용 backbone / 사용 layer 정확히
- [ ] coreset 비율과 성능-비용 trade-off 곡선
- [ ] re-weighting 항의 정확한 정의
- [ ] few-shot(적은 정상 이미지) 성능이 실제로 보고되는가, 얼마나 떨어지는가
- [ ] inference latency 보고 값과 측정 조건
- [ ] 코드 라이선스 (Apache-2.0 여부) 및 anomalib 구현과의 차이
