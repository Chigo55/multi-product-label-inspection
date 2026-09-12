# Defect Taxonomy v0.1

> 작성일: 2026-09-12 (Week 1)
> 상태: **v0.1 — 변경 가능**
> 이 파일의 enum 값이 `schema.md`의 `defect_type` / `defect_severity`의 유일한 정의다.

불량은 두 축으로 나눈다. 두 질문이 분리되기 때문이다.

```text
1. 이 라벨은 외관상 정상인가?      → VISUAL
2. 이 라벨은 이 제품에 맞는 라벨인가? → LOGICAL
```

---

## 1. VISUAL / STRUCTURAL (`defect_category = "visual"`)

라벨 자체의 외관이 정상과 다른 경우. 주로 Industrial Anomaly Detection으로 다룬다.

| `defect_type` | 설명 | 기본 Severity |
|---|---|---|
| `scratch` | 긁힘 | MAJOR |
| `contamination` | 오염 / 이물 | MINOR |
| `tear` | 찢김 | MAJOR |
| `blur` | 인쇄 흐림 / 번짐 | MAJOR |
| `missing_print` | 인쇄 누락 (문자·그래픽 일부 빠짐) | MAJOR |
| `color_anomaly` | 색상 이상 | MINOR |
| `fold` | 구김 / 접힘 | MAJOR |
| `occlusion` | 가림 (다른 물체·라벨 겹침) | MAJOR |
| `unknown_visual` | 학습 시점에 정의되지 않은 외관 이상 | MAJOR |

> `unknown_visual`은 E4(Unknown Defect) 평가 전용이다.
> 이 타입이 붙은 샘플은 **어떤 형태로도 학습/threshold calibration에 사용하지 않는다.**

---

## 2. LOGICAL (`defect_category = "logical"`)

라벨 자체는 외관상 정상이어도 제품 문맥상 잘못된 경우.

| `defect_type` | 설명 | 기본 Severity |
|---|---|---|
| `missing_label` | 필수 라벨 누락 | CRITICAL |
| `wrong_label` | 같은 제품 내 다른 라벨 오부착 (예: A에 a-3 대신 a-1) | CRITICAL |
| `wrong_product_label` | 다른 제품의 라벨 오부착 (예: A에 b-3) | CRITICAL |
| `wrong_position` | 위치 허용 오차 초과 | MAJOR |
| `wrong_orientation` | 회전 / 기울기 / 방향 오류 | MAJOR |
| `ocr_mismatch` | OCR 문자 내용 불일치 | CRITICAL |
| `barcode_mismatch` | Barcode / QR / DataMatrix 내용 불일치 | CRITICAL |
| `revision_mismatch` | 구 revision 라벨 사용 | CRITICAL |

> 복수 라벨 관계 자체의 이상(예: `a-1, a-2, a-3` 중 `a-2` 누락)은
> **label-level `missing_label` + product-level NG**로 기록한다.

---

## 3. Severity

| Severity | 정의 | 대표 사례 |
|---|---|---|
| `CRITICAL` | 출하되면 안 되는 불량. 오식별·오부착·내용 오류 계열 | `wrong_product_label`, `barcode_mismatch`, `ocr_mismatch`(핵심 field), `missing_label`, `revision_mismatch` |
| `MAJOR` | 명확한 품질 불량. 외관 훼손·위치 오류 | `tear`, `missing_print`, `blur`, `wrong_position`, `fold` |
| `MINOR` | 경미한 편차. 기준에 따라 통과 가능 | `contamination`(소면적), `color_anomaly`(경미) |

**최우선 KPI는 Critical Defect Escape다.** (`evaluation_protocol.md` §1 참고)

### Severity 결정 규칙

1. 위 표의 **기본 Severity**를 출발점으로 한다.
2. 단, severity는 **defect type이 아니라 product/label별 Recipe에서 override 가능**하다.
   - 예: `ocr_mismatch`가 `MODEL` field면 CRITICAL, `DATE` field면 MAJOR.
   - 예: `contamination`이 barcode 영역을 덮으면 MINOR가 아니라 CRITICAL.
3. override는 Recipe(`configs/recipes/*.yaml`, Week 3~)에 명시하고, dataset metadata에는 **최종 severity**를 기록한다.

---

## 4. defect_type ↔ 검출 담당 모듈 (설계 가설, Week 12에서 검증)

| defect_type | Visual AD | Prototype Identity | OCR | Barcode | Geometry | Rule |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| scratch / tear / fold / blur / missing_print / contamination / color_anomaly / occlusion | ● | ○ | | | | |
| unknown_visual | ● | ○ | | | | |
| missing_label | ○ | ● | | | ● | ● |
| wrong_label / wrong_product_label | ○ | ● | ○ | ○ | | ● |
| wrong_position / wrong_orientation | | | | | ● | ● |
| ocr_mismatch | | ○ | ● | | | ● |
| barcode_mismatch | | | | ● | | ● |
| revision_mismatch | | ○ | ● | ○ | | ● |

● 주 담당 / ○ 보조 근거(evidence)

> 이 표가 곧 **Ablation study 설계도**다(Week 21). 어떤 모듈을 빼면 어떤 defect_type이 escape하는지를 예측하고 검증한다.

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-09-12 | VISUAL 9종 + LOGICAL 8종, Severity 3단계, 모듈 매핑 초안 |
