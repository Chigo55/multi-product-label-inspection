# Week 05 — Classical Baseline

- 기간: 2026-11-14 (토) ~ 2026-11-15 (일) 예정 (#69 일정 재조정안의 주말 3)
- 주제: Registration·Geometry / Label Identity / OCR / Barcode / Rule Engine — Architecture A
- 이슈: #10 (하위 #63~#67). 선행 작업: #69 (리뷰 후속 P0)

---

## 선행 점검 — 바코드 판독률 (#66, #69 T3)

6자 Code128이 256px ROI(모듈당 약 2px)에서 읽히는지, 판독 규칙을 어느 디코더 조합으로 만들지 정했다.

- 실행: `uv run experiments/week05_barcode_check.py` (config `configs/week05_barcode_check.yaml`, RQ3 / E5)
- run: `ea7e97f0053f4101abf6eab5f703d1cf` (`citable=false`, git `cf1dbc8`, `git_dirty=false`)
- 데이터: Pilot val, 바코드가 있는 라벨만 — 정상 1007행 + `barcode_mismatch` 24행.
  이미지는 v0.3 생성분이다. registry는 이미 v0.4(구성 중)지만 v0.4는 test에 태그·unit만 더하므로 val은 같다.
- 디코더: pyzbar 0.1.9, zxing-cpp 3.1.1 (원본 / 2배 bicubic 업스케일)

### 디코더 단독

판독 = 값을 정확히 하나 읽음. 오판독 = 실제 바코드와 다른 값을 읽음.

| 대상 | layout | 디코더 | n | 판독 | 오판독 |
|---|---|---|---:|---:|---:|
| 정상 | plate | pyzbar | 496 | 492 (99.2%) | 0 |
| 정상 | plate | zxing | 496 | 362 (73.0%) | 1 |
| 정상 | plate | zxing_x2 | 496 | 483 (97.4%) | 1 |
| 정상 | tag | pyzbar | 511 | 503 (98.4%) | 0 |
| 정상 | tag | zxing | 511 | 500 (97.8%) | 0 |
| 정상 | tag | zxing_x2 | 511 | 500 (97.8%) | 0 |
| barcode_mismatch | plate | pyzbar | 9 | 8 (88.9%) | 0 |
| barcode_mismatch | plate | zxing | 9 | 5 (55.6%) | 0 |
| barcode_mismatch | plate | zxing_x2 | 9 | 9 (100.0%) | 0 |
| barcode_mismatch | tag | pyzbar | 15 | 15 (100.0%) | 0 |
| barcode_mismatch | tag | zxing | 15 | 14 (93.3%) | 0 |
| barcode_mismatch | tag | zxing_x2 | 15 | 15 (100.0%) | 0 |

zxing-cpp 원본은 plate에서 73%만 읽는다. 업스케일하면 97%로 오르지만 오판독이 1건 생긴다 — 단일 디코더로 NG를
내면 이 1건이 과검이 된다.

### 합의 규칙 (두 디코더가 같은 값 하나를 읽어야 판독 성공)

| 대상 | 디코더 쌍 | MATCH | MISMATCH | CONFLICT | UNREADABLE |
|---|---|---:|---:|---:|---:|
| 정상 | pyzbar+zxing | 853 | 0 | 1 | 153 |
| 정상 | **pyzbar+zxing_x2** | **976** | **0** | 1 | 30 |
| 정상 | zxing+zxing_x2 | 842 | 0 | 2 | 163 |
| barcode_mismatch | pyzbar+zxing | 0 | 19 | 0 | 5 |
| barcode_mismatch | **pyzbar+zxing_x2** | 0 | **23** | 0 | 1 |
| barcode_mismatch | zxing+zxing_x2 | 0 | 19 | 0 | 5 |

**채택: pyzbar + zxing-cpp 2배** (`src/models/barcode.py` `PAIR`).

- val 정상 오판독(MISMATCH → 과검) **0 / 1007, 95% 상한 0.37%**.
- val `barcode_mismatch` 검출 23 / 24. 놓친 1건은 UNREADABLE → REVIEW라 escape가 아니다.
- 대가: 정상 바코드 row의 3.1%(UNREADABLE 30 + CONFLICT 1)가 REVIEW로 간다. 바코드 라벨이 있는 제품에서는
  Product-level Review Rate에 그대로 더해진다 — 제품 검토 예산 R(#69 T10)을 정할 때 이 몫을 뺀다.

### 남은 것

- `predictions.csv`의 `barcode_result` 열(protocol §9.1 v1.1)과 디코더 param(`decoder_params()`)은 #67 run에서 기록한다.
- 판독 불가 30건이 어떤 nuisance(blur·warp)에서 나오는지는 T8의 nuisance sidecar가 생긴 뒤 나눠 본다.
