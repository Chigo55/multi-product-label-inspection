# Dataset Schema v0.2.1

> 작성일: 2026-09-12 (Week 1)
> 상태: **v0.2.1 — 변경 가능.** 이미지가 한 장도 없어도 스키마는 먼저 고정한다.
> 목적: Public benchmark(MVTec AD/LOCO, VisA ...)와 자체 Multi-Product Multi-Label benchmark를
> **동일한 metadata 형식**으로 다뤄서, 평가 코드를 한 번만 만들면 되게 한다.

저장 형식: 샘플 1건 = 1 row. 파일은 `metadata.csv` 또는 `metadata.jsonl` (권장: JSONL, 필드 추가에 강함).

---

## 1. 필드 정의

### 1.1 식별자

| 필드 | 타입 | 필수 | 설명 |
|---|---|:--:|---|
| `sample_id` | string | ● | 전역 고유 ID. 권장 형식 `{unit_id}/{label_slot}` |
| `unit_id` | string | ● | **Product Unit**(물리적 제품 1개) ID. 같은 제품에서 나온 모든 라벨·카메라 row가 공유한다. 권장 형식 `{dataset}/{product_id}/{split}/{seq}` |
| `product_id` | string | ● | **Product Type**(제품 종류, 예: `A`, `B`). Public 변환 시 MVTec category를 매핑 |
| `label_slot` | string | ● | 이 row가 검사하는 **라벨 자리**. Recipe가 정의하며, 라벨이 누락돼도 자리는 존재한다. 라벨 개념이 없는 데이터셋은 `-` |
| `camera_id` | string | ● | 촬영 카메라 (예: `CAM02`). 단일 카메라면 `CAM01` 고정 |
| `image_path` | string | ● | 데이터셋 루트 기준 상대 경로 |

> **집계 키**: Label-level(Level 2)은 `(unit_id, label_slot)`, Product-level(Level 3)은 `unit_id`로
> group by 한다. **Label Identity**(어떤 라벨인가)는 `expected_label_id` / `actual_label_id`가 담당한다 —
> 자리와 정체를 한 필드에 섞지 않는다 (`docs/adr/0003`).

### 1.2 기대값 vs 실제값 (Logical 검사의 핵심)

| 필드 | 타입 | 필수 | 설명 |
|---|---|:--:|---|
| `expected_label_id` | string | ● | Inspection Recipe가 요구하는 라벨 |
| `actual_label_id` | string | ● | 실제로 부착된 라벨 (ground truth) |
| `expected_text` | json | ○ | OCR 기대 field map. 예: `{"MODEL":"XA-100","REV":"03"}` |
| `actual_text` | json | ○ | 실제 인쇄 문자열 field map |
| `expected_barcode` | json | ○ | 예: `{"type":"DataMatrix","value":"XA100-0003"}` |
| `actual_barcode` | json | ○ | 실제 코드 내용 |
| `expected_position` | json | ○ | 제품 좌표계 기준. `{"x":..,"y":..,"theta":..,"unit":"mm|px"}` |
| `actual_position` | json | ○ | 실제 위치/자세 |

> **규칙**: `expected_*`는 Recipe에서, `actual_*`는 ground truth에서 온다.
> 모델 출력은 이 필드에 절대 쓰지 않는다 (predicted 값은 실험 결과 파일에 별도 기록).

### 1.3 판정 / 불량

| 필드 | 타입 | 필수 | 값 |
|---|---|:--:|---|
| `normal_or_defect` | enum | ● | `normal` \| `defect` |
| `defect_category` | enum | ○ | `visual` \| `logical` \| `none` (정상은 `none`) |
| `defect_type` | enum | ○ | `defect_taxonomy.md` 참고 |
| `defect_severity` | enum | ○ | `CRITICAL` \| `MAJOR` \| `MINOR` \| `none` |
| `defects` | list[json] | ○ | 관측된 **Defect Record** 전체. 각 원소는 `{"type":..., "severity":...}` |

> 한 샘플에 복수 불량이 있을 수 있다. **원본은 언제나 `defects[]`이고**,
> `defect_type` / `defect_severity`는 거기서 파생된 **대표값**이다:
> `defect_severity`는 가장 높은 severity, `defect_type`은 그 severity를 만든 type을 쓴다.
> 불량이 1건이면 `defects[]`는 원소 1개짜리 리스트다.
>
> `defect_severity`는 Defect Taxonomy의 기본값이 아니라 **Recipe override가 적용된 최종값**을
> 기록한다 (`docs/adr/0004`).

### 1.4 Known / Unknown (Open-set 평가용)

| 필드 | 타입 | 필수 | 설명 |
|---|---|:--:|---|
| `is_known_label` | bool | ● | 등록(prototype 존재)된 라벨인가 |
| `is_known_defect` | bool | ● | 학습/설계 시점에 존재하던 불량 유형인가 (정상 샘플은 `true`) |

### 1.5 추적 / 분할

| 필드 | 타입 | 필수 | 설명 |
|---|---|:--:|---|
| `production_lot` | string | ○ | LOT. Domain shift(E6) 분할 기준으로 사용 |
| `revision` | string | ○ | 라벨 도면 revision (예: `03`) |
| `split` | enum | ● | `train` \| `val` \| `test` \| `reference` |
| `experiment_tags` | list | ○ | 해당 샘플이 속한 시나리오. 예: `["E3","E5-hard"]` |

> `reference`는 few-shot 등록용 정상 이미지 전용 split이다. `train`과 분리해서 관리한다
> (RQ4에서 shot 수를 바꿔가며 샘플링해야 하므로).

---

## 2. JSONL 예시

```json
{"sample_id":"custom/A/test/000123/slot-2","unit_id":"custom/A/test/000123",
 "product_id":"A","label_slot":"slot-2","camera_id":"CAM02",
 "image_path":"custom/images/A/test/000123_cam02.png",
 "expected_label_id":"a-2","actual_label_id":"b-3",
 "normal_or_defect":"defect","defect_category":"logical","defect_type":"wrong_product_label",
 "defect_severity":"CRITICAL",
 "defects":[{"type":"wrong_product_label","severity":"CRITICAL"}],
 "expected_text":{"MODEL":"XA-100"},"actual_text":{"MODEL":"XB-100"},
 "expected_barcode":{"type":"DataMatrix","value":"XA100-0003"},
 "actual_barcode":{"type":"DataMatrix","value":"XB100-0003"},
 "expected_position":{"x":42.0,"y":18.5,"theta":0.0,"unit":"mm"},
 "actual_position":{"x":41.6,"y":18.9,"theta":0.4,"unit":"mm"},
 "is_known_label":true,"is_known_defect":true,
 "production_lot":"L2603","revision":"03","split":"test",
 "experiment_tags":["E1","E5-extreme"]}
```

---

## 3. Public dataset 매핑 규칙 (v0.2.1)

Public benchmark에는 product/label 개념이 없으므로 다음과 같이 매핑한다.

| Public | `product_id` | `label_slot` | `defect_category` | 비고 |
|---|---|---|---|---|
| MVTec AD | category (예: `bottle`) | `-` | `visual` | `defect_type`은 원본 결함 폴더명 사용 |
| MVTec LOCO AD | category (예: `juice_bottle`) | `-` | `structural_anomalies`→`visual`, `logical_anomalies`→`logical` | 이번 연구의 logical 축과 직접 연결 |
| VisA | object 이름 | `-` | `visual` | Week 2 이후 |

> Public track은 `expected_*` 필드가 비어 있다(`null`). Logical 검사 항목은 평가에서 자동 제외된다.
> 제품당 라벨이 1개이므로 `unit_id`는 샘플마다 고유하고 Product-level은 Label-level과 같아진다
> (`docs/adr/0006`).

### 3.1 Public track 공통 값 (v0.2.1)

원본에 없는 정보는 지어내지 않고 `null`로 둔다. 필수(●) 필드도 **키는 항상 존재**하고 값만 `null`이다.

| 필드 | 값 | 이유 |
|---|---|---|
| `unit_id` | `{dataset}/{product_id}/{split}/{원본폴더}_{파일stem}` (예: `mvtec_ad/bottle/test/broken_large_000`) | MVTec은 결함 폴더마다 `000`부터 다시 센다. 폴더명을 넣어야 고유하고 원본 추적도 된다 |
| `image_path` | 변환 root(예: `datasets/public/mvtec_ad`) 기준 상대 경로. `metadata.jsonl`도 그 root에 둔다 | |
| `camera_id` | `CAM01` | 단일 카메라 |
| `expected_*` / `actual_*` / `is_known_label` | `null` | Recipe도 Label Identity도 없다 → Logical·Identity 지표에서 자동 제외 |
| `is_known_defect` | `true` | 원본 결함 폴더는 설계 시점에 정의된 유형이다 |
| `defect_type` (정상) | `null` | taxonomy enum에 정상용 값이 없다 |
| `defect_severity` / `defects[].severity` (불량) | `null` | **Severity는 Recipe가 정한다**(`docs/adr/0004`). public track에는 Recipe가 없으므로 **Critical Escape Rate를 계산하지 않는다.** Defect Escape Rate는 계산한다 |
| `split` | 원본 그대로(`train`/`test`) | MVTec AD에는 val이 없다. val/calibration 분할은 §4에서 확정 |

> 변환 시 `train`에 불량 폴더가 있으면 **에러로 멈춘다**(normal-only 전제 위반). 구현: `src/utils/mvtec.py`.

---

## 4. Split 정책 (초안 — Week 2에서 확정)

- **Leakage 금지 규칙**: 동일 Product Unit(`unit_id`) 또는 동일 LOT의 이미지가 `reference`와 `test`에
  동시에 들어가지 않는다. `unit_id`가 있으므로 이 규칙은 기계적으로 검증할 수 있다.
- `reference`는 **정상만** 포함한다.
- Unknown label(E3)용 라벨은 `reference`에 prototype을 만들지 않는다.
- Unknown defect(E4)용 불량 유형은 threshold calibration 데이터에 포함하지 않는다.
- Domain shift(E6)는 LOT / 조명 / 카메라 기준으로 test를 분리한다.

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-09-12 | 최초 정의. 필드 26개, public 매핑 규칙, split 정책 초안 |
| v0.2 | 2026-09-12 | `unit_id` 추가(Product-level 집계 키), `label_id`→`label_slot` 재정의, `defects[]`를 정식 필드로 선언 |
| v0.2.1 | 2026-09-21 | §3.1 public track 공통 값 명시(`unit_id` seq 형식, `image_path` 기준, severity `null` → public track은 CDER 미계산). 필드 변경 없음 |
