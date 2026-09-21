# MVTec LOCO AD

> *Beyond Dents and Scratches: Logical Constraints in Unsupervised Anomaly Detection and Localization*
> Bergmann, Batzner, Fauser, Sattlegger, Steger — IJCV 2022
> [https://www.mvtec.com/company/research/datasets/mvtec-loco](https://www.mvtec.com/company/research/datasets/mvtec-loco)
>
> **상태: 사전 정리 초안(Week 1).** 아래 내용은 읽기 전 정리용이며,
> 원문을 훑으면서 ✅ 확인 / ✏️ 정정한다. 숫자에는 `?`를 붙여 두었다.

---

## 오늘 집중해서 볼 질문

> **Structural anomaly와 Logical anomaly를 왜 구분했는가?**

정리(확인 대상):

1. **원인이 다르다.** Structural은 표면의 국소적 훼손(스크래치, 찍힘, 오염)이고,
 Logical은 물체 자체는 멀쩡한데 **전역 제약(개수, 순서, 위치 관계, 조합)** 을 위반한 것이다.
2. **필요한 receptive field가 다르다.** Local patch 비교로 잡히는 것과, 이미지 전체 문맥을 봐야 잡히는 것.
 → 그래서 baseline(GCAD)도 local branch + global branch **두 갈래**로 설계했다 `?`
3. **Localization ground truth의 정의가 다르다.** "부품이 빠졌다"의 결함 위치는 어디인가?
 픽셀 단위 정답이 애매하다 → 그래서 **sPRO(saturated PRO)** 라는 새 지표를 도입했다 `?`
4. **기존 방법의 성능이 갈린다.** MVTec AD에서 잘 되던 방법들이 logical anomaly에서 크게 떨어진다 `?`
 → 이것이 이 데이터셋의 존재 이유.

---

## 6항목 요약

### Problem

정상 데이터만 주어진 unsupervised 조건에서, 표면 훼손(structural)뿐 아니라
**논리적 제약 위반(logical)** 까지 탐지·국소화하는 문제를 정식화하고 benchmark를 제공.

### Input

RGB 이미지 (제품 전체 장면). 5개 category `?`:
breakfast box / juice bottle / pushpins / screw bag / splicing connectors.
총 약 3,600장 규모 `?`

### Training Data

**정상 이미지만.** 불량은 test에만 등장. (normal-only 조건 = 이번 연구와 동일)

### Method (baseline)

GCAD (Global Context Anomaly Detection) `?` — student-teacher 계열.

- local branch: 작은 receptive field → structural anomaly
- global branch: 큰 receptive field / bottleneck → logical anomaly
두 branch의 점수를 결합.

### Output

image-level anomaly score + anomaly map. 평가지표는 sPRO `?`
(PRO에 saturation threshold를 도입해, 논리적 결함처럼 "영역 전체를 정확히 맞출 수 없는" 경우를 다룸)

### ⭐ Limitation for my problem

이번 연구와의 간극 — **여기가 핵심이다.**

1. **제품-라벨 조합 개념이 없다.** LOCO의 logical anomaly는 *한 장면 내부*의 제약(개수/순서/색 조합)이다.
 이번 문제의 logical defect는 **외부 컨텍스트(MES가 준 product\_id)와의 불일치**다.
 → `b-3`가 완벽하게 인쇄되어 있어도 Product A에 붙으면 NG. LOCO에는 이런 축이 없다.
2. **expected vs actual 구조가 없다.** LOCO는 "무엇이 정상인지"를 데이터에서 암묵적으로 학습한다.
 이번 연구는 Recipe에 **명시적 기대값**(expected\_label / expected\_text / expected\_barcode / expected\_position)이 있다.
 → 명시적 기대값을 쓰면 더 쉬워야 정상인데, 기존 AD 방법은 이 정보를 **받을 입구 자체가 없다.**
3. **OCR / Barcode 축이 없다.** 문자 한두 글자, 코드 내용만 다른 경우는 LOCO의 범위 밖이다.
4. **few-shot / 신규 class 추가를 다루지 않는다.** category가 5개로 고정이다. RQ4(1/5/10/20/50-shot)에 직접 답하지 않는다.
5. **Open-set(미등록 라벨 거부) 개념이 없다.**
6. **sPRO를 그대로 쓸 수 있는가?** 이번 연구의 Primary metric은 Defect Escape Rate다.
 sPRO는 localization 지표이므로 **보조 지표**로만 쓴다. → `reports/evaluation_protocol.md` §4

### 활용 계획

- **Week 6\~7**: PatchCore / EfficientAD를 MVTec AD**와** LOCO 양쪽에서 돌려
"구조적 이상은 되는데 논리적 이상은 안 된다"를 **우리 손으로 재현**한다. → Research Gap의 첫 근거.
- LOCO의 logical anomaly 분류 방식(개수/순서/조합)을 자체 benchmark의 logical defect 설계에 참고.

---

## 확인 체크리스트 (읽으면서)

- [x] category 수 / 이미지 수 정확한 값
- [x] sPRO의 정확한 정의와 saturation threshold의 의미
- [x] GCAD의 두 branch 구조와 결합 방식
- [x] 기존 방법들이 logical에서 얼마나 떨어지는지 (구체 수치)
- [x] 데이터셋 라이선스 — **상업적 이용 조건**

