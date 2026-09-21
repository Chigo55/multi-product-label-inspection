# 다품종 라벨 검사 (Multi-Product Label Inspection)

여러 제품 종류에 부착된 다수의 라벨을, 정상 데이터만으로 학습한 상태에서 검사하는 시스템을
연구한다. 이 문서는 **용어집이다.** 측정 방법은 `reports/evaluation_protocol.md`,
데이터 형식은 `datasets/schema.md`, 결정 기록은 `docs/adr/`에 있다.

## Language

### 제품과 라벨

**Product Unit**:
검사 라인을 지나가는 물리적 제품 1개. Product-level 집계의 단위다.
_Avoid_: 제품(단독으로), unit(단독으로), item

**Product Type**:
제품의 종류(SKU). 하나의 Product Type은 여러 Product Unit으로 생산된다.
_Avoid_: 품목, category, SKU

**Label**:
Product Unit에 부착되는 물리적 라벨 1장. **머신러닝의 정답 class를 뜻하지 않는다.**
_Avoid_: class, 클래스, tag, sticker

**Label Slot**:
하나의 Product Type에서 라벨이 붙어야 할 자리. Recipe가 정의하며, 라벨이 누락돼도
자리는 존재한다.
_Avoid_: position(위치 좌표와 혼동), 라벨 번호

**Label Identity**:
어떤 라벨인지를 구별하는 식별값(예: `a-2`). 라벨이 몇 장 늘어나도 이 값으로 식별한다.
_Avoid_: label class, label category, 라벨 종류

**Inspection Recipe**:
Product Type별 검사 기준. 어느 Label Slot에 어떤 Label Identity가, 어떤 문자·코드·위치로
있어야 하는지를 규정한다. **모든 Expected 값의 유일한 출처이며 Severity를 정하는 주체다.**
_Avoid_: Recipe(문맥이 모호할 때), 제품 context, 검사 규격, spec

**Onboarding**:
신규 Label Identity를 시스템이 식별할 수 있도록 등록하는 행위. 전체 재학습 없이 하는 것이 목표다.
_Avoid_: 등록(단독으로), 학습, enrollment

### 기대값과 실제값

**Expected**:
Recipe가 요구하는 값. "이 자리에 무엇이 있어야 하는가."

**Actual**:
실제로 부착된 상태의 ground truth. **모델 출력은 Actual이 아니다.**
_Avoid_: 정답(모호), truth

**Prediction**:
모델이 내놓은 값. dataset metadata에 절대 기록하지 않고 실험 결과에만 남긴다.
_Avoid_: actual, 추론값

### 불량

**Visual Defect**:
라벨 자체의 외관이 정상과 다른 경우. "이 라벨은 외관상 정상인가"에 답한다.
_Avoid_: structural, appearance defect, 외관불량

**Logical Defect**:
외관은 정상이지만 제품 문맥상 잘못된 경우. "이 라벨은 이 제품에 맞는 라벨인가"에 답한다.
_Avoid_: contextual defect, semantic defect, 논리불량

**Defect Record**:
한 샘플에서 관측된 개별 불량 1건. 한 샘플에 여러 건이 존재할 수 있다.

**Severity**:
불량이 출하에 미치는 영향의 등급(`CRITICAL` / `MAJOR` / `MINOR`).
**불량 유형의 고유 속성이 아니라 Recipe가 정하는 값이다** (`docs/adr/0004`).
_Avoid_: 중요도, priority, 등급

### 판정

**OK / NG / REVIEW**:
시스템 출력의 3-state. `REVIEW`는 판정 보류이며 사람에게 넘긴다.
_Avoid_: PASS/FAIL, 양품/불량품, uncertain

**Escape**:
실제 불량인데 `OK`로 판정된 경우. **`REVIEW`는 Escape가 아니다**(사람에게 도달했으므로).
이 연구의 최상위 지표다.
_Avoid_: 미검출, 누락, miss

**Critical Escape**:
Severity가 `CRITICAL`인 불량의 Escape. 목표치는 0이다.

**False Reject**:
실제 정상인데 `NG`로 판정된 경우. `REVIEW`는 False Reject가 아니다.
_Avoid_: false alarm, 오검

**Review Rate**:
`REVIEW`로 판정된 비율. 정확도가 아니라 **사람이 부담하는 비용** 지표다.

### 평가 단위와 시나리오

**Defect-level / Label-level / Product-level**:
집계 단위 3종(Level 1/2/3). Product-level이 현장 KPI와 직결된다(`docs/adr/0003`).
_Avoid_: image-level, sample-level

**Reference**:
Onboarding 전용 정상 이미지 split. `train`과 분리해서 관리한다.
_Avoid_: support set, 등록 이미지

**Known Label / Unknown Label**:
Onboarding된 라벨인가 아닌가. Unknown을 기존 Label Identity로 억지 분류하는 것은
단순 오분류가 아니라 별도의 실패 유형으로 집계한다.

**Known Defect / Unknown Defect**:
설계 시점에 존재하던 불량 유형인가 아닌가. **정상 샘플은 Known으로 취급한다**
(불량이 없으므로 "해당 없음"을 이렇게 인코딩한다).

**Scenario**:
실험 시나리오 `E1`~`E6`. 모든 실험은 자신이 속한 Scenario를 선언한다.
_Avoid_: 실험 종류, experiment type

**Research Question**:
연구 질문 `RQ1`~`RQ6`. 어떤 RQ에도 연결되지 않는 실험은 하지 않는다.
_Avoid_: 연구 주제, 가설
