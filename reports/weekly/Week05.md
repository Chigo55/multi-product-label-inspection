# Week 05 — Classical Baseline

- 기간: 2026-11-14 (토) ~ 2026-11-15 (일) 예정 (#69 일정 재조정안의 주말 3)
- 주제: Registration·Geometry / Label Identity / OCR / Barcode / Rule Engine — Architecture A
- 이슈: #10 (하위 #63~#67). 선행 작업: #69 (리뷰 후속 P0)

---

## 일정 재조정 (#69 T17, 결정 5)

원래 일정으로는 Week 8 Gate가 10-31이었다. 저장소 리뷰(2026-10-26)에서 Linux에서 Pilot 생성이 막히는 문제(T1),
미등록 라벨 거부가 E1 FPR을 오염시키는 문제(T2), 단일 디코더 바코드 판정(T3), Jetson 측정 구조(T4)가 나왔고,
이것을 고치기 전에 Week 5 평가 run(#67)을 돌리면 첫 실제 모델 결과를 다시 만들어야 한다. 그래서 P0를 먼저 끝내고
약 3주 순연했다 — Week 5는 11-14 주말, Week 8 Gate는 11-28, Week 12 Gate는 12-19, Week 20 Feature Freeze는
2027-02-13, Week 24는 2027-03-13 주말이다. 순연폭을 줄이려고 Week 6~7과 Week 9~10을 각각 한 주로 묶고,
Raspberry Pi 측정과 Human study는 선택 항목으로 내렸다. 표는 README "진행 상황".

---

## 선행 작업 — Pilot v0.4 (#69 T2·T5~T9)

Week 5 baseline은 v0.4 위에서 돌린다. **v0.3 unit은 그대로이고 새 unit은 뒤에 붙었다** — v0.3 생성기로 다시 만든
8816 row와 metadata·이미지 바이트 차이 0. 테스트로는 두 가지를 고정한다 — v0.3 생성기에서 계산한 render 픽셀
해시(`test_render_matches_v03_generator`, 난수 순서)와 축소판에서 v0.4 추가분이 v0.3 unit을 흔들지 않는지
(`test_v03_units_are_unchanged`, 배정).

| 추가 | 내용 (test 기준) | 평가 범위 |
|---|---|---|
| E5 전용 unit `E5` 태그 (T2) | 288 unit | E5 (E1·E4에서 제외) |
| a-5 · revision "06" (T5) | a-2와 바코드가 같고 REV만 다른 새 revision. 정상 unit은 기존 revision 하나와 같은 수 | E1 |
| `revision_mismatch` (T5) | a-5 자리에 a-2 — 72 (val 24). E5-hard, **바코드가 같아 OCR만 가른다** | E1 · E5 |
| `GEOM-boundary` (T6) | 허용 오차 0.9~1.2배. 위치 72 unit(정상 29 / 불량 43), 각도 72(정상 15 / 불량 57) | 따로 |
| `OCR-confusable` (T7) | 0/O 1/I 5/S 8/B 2/Z 6/G 치환 `ocr_mismatch` 72 | 따로 |
| `nuisance.jsonl` (T8) | 샘플별 실제 warp·조명·blur·noise·offset·theta | — |
| `pilot_dev` (T9) | 같은 Recipe, seed 네임스페이스 `custom_pilot_dev/`, LOT L2691~L2694. `pilot` test는 봉인 | Week 5~16 보고·실패 분석 |

E1 범위(test, `pilot` v0.4): 1020 unit — 정상 300 / 불량 720 (유형당 72 × 10, hold-out 제외).
점검 run `36cae0d49c814e07bef12898af57c659` (week04_gate_check, `pilot_dev`, `citable=false`, git `3055f0a`): E1 product
정상 분모 300, 재현성 일치, 시나리오 접두사 지표 기록 확인. dummy라 지표 숫자는 의미가 없다.

---

## 선행 점검 — 바코드 판독률 (#66, #69 T3)

6자 Code128이 256px ROI(모듈당 약 2px)에서 읽히는지, 판독 규칙을 어느 디코더 조합으로 만들지 정했다.

- 실행: `uv run experiments/week05_barcode_check.py` (config `configs/week05_barcode_check.yaml`, RQ3 / E5)
- run: `311a55b22175473a97e2bc9dff2fa118` (`citable=false`, git `3055f0a`, `git_dirty=false`)
- 데이터: **Pilot v0.4** val, 바코드가 있는 라벨만 — 정상 1235행 + `barcode_mismatch` 24행.
  (첫 run `ea7e97f0…`은 v0.3 metadata에 `dataset_version=0.4`가 잘못 남아 태그 `actual_metadata_version=0.3`을
  달고 대체했다. 이후 스크립트는 `check_built_version`으로 생성 version을 registry와 대조한다. v0.3에서도
  정상 0/1007, 검출 23/24로 결론은 같았다.)
- 디코더: pyzbar 0.1.9 + **libzbar 0.10**(Windows wheel 동봉본), zxing-cpp 3.1.1 (원본 / 2배 bicubic 업스케일).
  Linux `libzbar0`는 0.23이라 판독률이 다를 수 있다 — 이후 run은 `zbar_version` param을 남긴다.

### 디코더 단독

판독 = 값을 정확히 하나 읽음. 오판독 = 실제 바코드와 다른 값을 (함께) 읽음.

| 대상 | layout | 디코더 | n | 판독 | 오판독 |
|---|---|---|---:|---:|---:|
| 정상 | plate | pyzbar | 640 | 636 (99.4%) | 0 |
| 정상 | plate | zxing | 640 | 460 (71.9%) | 1 |
| 정상 | plate | zxing_x2 | 640 | 626 (97.8%) | 1 |
| 정상 | tag | pyzbar | 595 | 587 (98.7%) | 0 |
| 정상 | tag | zxing | 595 | 582 (97.8%) | 0 |
| 정상 | tag | zxing_x2 | 595 | 584 (98.2%) | 0 |
| barcode_mismatch | plate | pyzbar | 9 | 8 (88.9%) | 0 |
| barcode_mismatch | plate | zxing | 9 | 5 (55.6%) | 0 |
| barcode_mismatch | plate | zxing_x2 | 9 | 9 (100.0%) | 0 |
| barcode_mismatch | tag | pyzbar | 15 | 15 (100.0%) | 0 |
| barcode_mismatch | tag | zxing | 15 | 14 (93.3%) | 0 |
| barcode_mismatch | tag | zxing_x2 | 15 | 15 (100.0%) | 0 |

zxing-cpp 원본은 plate에서 72%만 읽고, `XA1001`을 `XA1011`로 잘못 읽은 1건이 있다(`A/val/00324`). 업스케일하면
98%로 오르지만 다른 1건에서 값을 둘(`XA0228|XA1001`) 읽는다. 단일 디코더로 NG를 내면 이런 건이 과검이 된다.

### 합의 규칙 (두 디코더가 같은 값 하나를 읽어야 판독 성공)

| 대상 | 디코더 쌍 | MATCH | MISMATCH | CONFLICT | UNREADABLE |
|---|---|---:|---:|---:|---:|
| 정상 | pyzbar+zxing | 1033 | 0 | 1 | 201 |
| 정상 | **pyzbar+zxing_x2** | **1203** | **0** | 1 | 31 |
| 정상 | zxing+zxing_x2 | 1022 | 0 | 2 | 211 |
| barcode_mismatch | pyzbar+zxing | 0 | 19 | 0 | 5 |
| barcode_mismatch | **pyzbar+zxing_x2** | 0 | **23** | 0 | 1 |
| barcode_mismatch | zxing+zxing_x2 | 0 | 19 | 0 | 5 |

**채택: pyzbar + zxing-cpp 2배** (`src/models/barcode.py` `PAIR`).

- val 정상 오판독(MISMATCH → 과검) **0 / 1235 (95% CI 0.00%~0.30%)**.
- val `barcode_mismatch` 검출 23 / 24 = 95.8% (95% CI 78.9%~99.9%). 놓친 1건은 UNREADABLE → REVIEW라 escape가 아니다.
- 대가: 정상 바코드 row의 32 / 1235 = 2.6% (95% CI 1.8%~3.6%, UNREADABLE 31 + CONFLICT 1)가 REVIEW로 간다. 바코드 라벨이 있는 제품에서는
  Product-level Review Rate에 그대로 더해진다 — 제품 검토 예산 R(#69 T10)을 정할 때 이 몫을 뺀다.

### 남은 것

- `predictions.csv`의 `barcode_result` 열(protocol §9.1 v1.1)과 디코더 param(`decoder_params()`)은 #67 run에서 기록한다.
- 판독 불가 30건이 어떤 nuisance(blur·warp)에서 나오는지는 T8의 nuisance sidecar가 생긴 뒤 나눠 본다.
