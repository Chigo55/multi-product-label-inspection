# Pilot-Real 촬영 프로토콜 v0.1

> 작성일: 2026-10-27 / 이슈: #69 T14 (결정 6 "진행", 2026-10-27)
> 계획 확정: Week 12 Gate 전 / 촬영 완료: Week 16 / 결과: E6 보조 (`reports/experiment_scenarios.md` E6)

벤치마크가 전부 렌더링이라 "실제 인쇄·촬영에서도 성립하는가"에 답하지 못한다. Pilot 라벨은 Recipe
(`configs/recipes/pilot.yaml`)에서 그려지므로, 같은 그림을 출력해 실물에 붙이면 **같은 Label Identity·같은
Recipe를 가진 실물 세트**가 된다. 회사 데이터가 아니라 사용 승인 문제가 없다.

## 1. 구성

| 항목 | 내용 |
|---|---|
| Label Identity | Pilot 등록 라벨 13종(a-1~a-5, b-1~b-4, c-1~c-4). 미등록 라벨(u-1, u-2)은 1차에 넣지 않는다 |
| 제품 대용물 | 3종 — A(금속 느낌 상자), B(어두운 플라스틱 통), C(종이 상자). Recipe `products.*.body`와 비슷한 표면 |
| Label Slot | Recipe `products.*.slots` 좌표(mm)를 대용물에 표시한다. 네 모서리에 위치 기준 마커를 붙인다 |
| Product Unit | 제품당 20 unit = 정상 12 + 불량 8. revision은 Recipe 순서대로 돌린다(A: 03/04/06, B: 01/02, C: 01) |
| 불량 (물리적으로 만든다) | 제품당 바꿔치기 2(A는 `revision_mismatch` a-5→a-2 1건 포함, B는 b-3↔b-4 1건 포함), `missing_label` 2, `wrong_position` 2(허용 오차의 약 1.5배), `wrong_orientation` 2(약 3배) |
| 카메라 | 1대(`CAM01`) 삼각대 고정. 거리는 ROI가 **6 px/mm 이상**이 되게 맞추고 기종·초점거리·노출을 기록한다 |
| 조명 | 고정 조명 1조(확산판). 촬영 중 바꾸지 않는다 — 조명 변화는 E6의 다른 요인이다 |
| 수량 | 60 unit, 약 190 라벨. 인쇄는 identity별 필요 수의 120% |

## 2. 인쇄

```bash
uv run experiments/export_pilot_real_labels.py   # → datasets/custom/pilot_real/print/<label_id>.png
```

- PNG에 DPI(609.6)가 적혀 있다. **100%(실제 크기)로 인쇄**하면 Recipe 좌표계와 같은 mm 크기다.
- 바코드는 같은 값·같은 심볼로지(Code128)를 **모듈당 정수 px로 다시 그린다.** Pilot 래스터(모듈당 약 2px)를 그대로
  키우면 9개 중 3~4개만 읽힌다(2026-10-27). 그래서 실물 바코드는 Pilot 그림과 막대 폭이 조금 다르다 — 이 차이도
  domain gap의 일부로 보고한다.
- 스크립트가 내보낸 그림을 같은 판독 규칙(`src/models/barcode.py`)으로 다시 읽는다. 2026-10-27 기준 9개 모두 `MATCH`.
- **인쇄 후 판독 확인**: 첫 촬영분에서 바코드 라벨 전부를 `read_barcode`로 읽는다. 하나라도 `UNREADABLE`이면
  인쇄 해상도·용지를 바꾸고 다시 찍는다.

## 3. 촬영과 기록

1. unit마다 사진 1장(`raw/<unit_id>.jpg`). 촬영 직전 기록지에 **실제로 붙인 것**을 적는다 — 자리별 Label Identity,
   누락, 의도한 이동·회전. 이 기록이 `actual_*`의 정답이다(`expected_*`는 Recipe에서 온다).
2. 위치·각도 불량은 자로 실제 offset(mm)과 각도를 재서 적는다.
3. 마커 4개로 원근을 펴고, 슬롯 기준 위치를 중심으로 256×256 ROI를 잘라 낸다(Week 16 변환기).

## 4. metadata (schema v1.1.2 그대로)

| 필드 | 값 |
|---|---|
| `unit_id` | `custom_pilot_real/<product>/test/<seq>` |
| `split` | 전부 `test` — threshold는 Pilot val 값을 재조정 없이 쓴다(E6 규칙, schema §4.4) |
| `production_lot` | `LREAL1` (Pilot LOT과 겹치지 않는다) |
| `camera_id` | `CAM01` |
| `experiment_tags` | `["E6-real"]` |
| `actual_*` | 기록지 값. 위치·각도 불량은 잰 값 |

변환기는 Week 16에 `src/utils/pilot_real.py`로 만든다. **registry 항목은 첫 촬영분이 생기고 해시를 확인한 뒤에
추가한다** — registry는 "실제로 받은 데이터만 등록"한다(#69 T14의 "registry 항목"은 이 시점으로 미룬다).

## 5. 보고

같은 모델의 Pilot(렌더) 대비 Pilot-Real의 DER·FPR·Review Rate 차이를 E6 보조 결과로 낸다. 표본이 작으므로
(정상 36 unit, 불량 24 unit) 분자·분모와 95% CI를 반드시 함께 적고, 차이를 주장할 때는 CI가 겹치지 않을 때만 한다.

## Week 12 전 체크리스트

- [ ] 대용물 3종 준비, 슬롯 좌표·마커 표시
- [ ] 라벨 인쇄(100%), 인쇄본 바코드 판독 확인
- [ ] 카메라·조명 고정, 6 px/mm 이상 확인
- [ ] 기록지 양식

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-10-27 | 초안 (#69 T14): 구성, 인쇄(바코드 정수 모듈 재렌더), 촬영·기록, metadata 매핑, registry는 첫 촬영분 후 |
