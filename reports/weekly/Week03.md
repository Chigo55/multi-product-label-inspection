# Week 03 — Pilot Benchmark

- 기간: 2026-09-26 (토) ~ 2026-09-27 (일) 예정 → **2026-09-25 (금) 수행** (하루 앞당김)
- 주제: 자체 Multi-Product Multi-Label benchmark의 Pilot을 만든다. 3 products / 10~15 label identities
- 이슈: #8 (하위 #33, #34, #35) + #49(버그)

---

## Goal

public benchmark로는 할 수 없는 시나리오(E3 미등록 라벨, E4 seen/unseen 불량, E5 유사 라벨)의 입력을 만든다.
사내 데이터 승인 여부가 연구를 막지 않도록 **전부 합성**한다(기준 문서 §23). logical defect는 합성하면
ground truth가 정확하다는 이점을 최대한 쓴다(§25).

---

## Implemented

| 항목 | 파일 | 이슈 |
|---|---|---|
| Inspection Recipe — `expected_*`와 Label Identity 카탈로그의 정본 | `configs/recipes/pilot.yaml` | #33 |
| 라벨 렌더러(4 layout, Code128) + 촬영 nuisance(원근·조명·blur·노이즈) + row 생성 | `src/utils/pilot.py` | #33 |
| synthetic defect 10종 — 정상 라벨에 가하는 변형(Mutation) | `src/utils/synthetic.py` | #34 |
| E5 난이도 구간 규칙 + 구간별 전용 unit + `E5-<tier>` 태그 | `src/utils/pilot.py` `similarity_tier` | #35 |
| Similar-label Confusion Rate (구간별 바꿔치기 DER) | `src/evaluation/metrics.py`, protocol **v0.6** §3 | #35 |
| 생성 스크립트 — Recipe 해시가 registry와 다르면 멈춘다 | `experiments/build_pilot.py` | #33 |
| registry `pilot` v0.1 → v0.2 → **v0.3** | `datasets/registry.yaml` | #33~35 |
| 실험 스크립트 UTF-8 stdout 고정 (CP949 콘솔 exit 1) | `experiments/_bootstrap.py` | #49 |

테스트 90 → **132개**, skip 없음. 실데이터 생성은 테스트에서 하지 않고 규모를 줄인 Recipe로 세션당 한 번 만든다
(`tests/conftest.py`).

---

## Result

**Pilot v0.3** — `uv run experiments/build_pilot.py`, 약 6분, 로컬 1.1 GB(커밋하지 않음).

```text
8816 rows = 정상 7592 + 불량 1224, schema 위반 0건
제품  A 전장 부품(L=3) / B 화학 용기(L=3) / C 식품 포장(L=4)
split 제품당 reference 60 / train 200 / val 192 unit, test A 450 / B 486 / C 372 unit
      (E5 전용 unit은 요구된 라벨의 제품에 붙어서 test 크기가 제품마다 다르다)
LOT   L2601·L2602 (train/val/reference) ↔ L2603·L2604 (test)
라벨  14종 = 등록 12 + 미등록 2 (u-1, u-2 → test 전용 40 row, E3)
불량  10종, 유형마다 test 72 row 이상. unknown_visual은 test에만 (E4 hold-out)
E5    test row: easy 179 / medium 102 / hard 76 / extreme 75
```

| 확인 | 결과 |
|---|---|
| 재현성 — 디스크 이미지를 다시 렌더 | 3/3 바이트 일치 |
| v0.1 → v0.2 — 정상 unit이 그대로인가 (v0.1 코드로 재렌더) | 12/12 일치 |
| v0.2 → v0.3 — 기존 unit 전부 (v0.2 코드로 재렌더) | **7920/7920 일치** |
| val 정상 표본이 f를 표현하는가 | A·B 504 row(f=0.334%), C 696 row(f=0.251%) — ok |

모델은 아직 돌리지 않았다. 이번 주 숫자는 전부 **데이터 구성**에 관한 것이고, 성능 숫자는 없다.

---

## Problems

1. **10자 Code128은 256px ROI에서 판독이 불가능하다.** 모듈당 1.4px가 된다. → 값을 6자로 줄였다(`XA100-0003` → `XA1003`).
   6자도 모듈당 약 2px로 판독 하한에 가깝다. Week 13에 실제 디코더로 확인한다.
2. **원근 워프가 가장자리에 검은 쐐기를 만들었다.** 캔버스 밖을 끌어오기 때문이다. → 여유분까지 그린 뒤 가운데를 잘라낸다.
3. **바코드의 사람용 문자열(HRI)을 켜면 E5-extreme이 성립하지 않는다.** b-3/b-4가 OCR로도 구별되기 때문이다. → HRI를 끈다.
4. **#33에서 적어 둔 severity override가 아무 일도 하지 않았다.** `ocr_mismatch.EXP: CRITICAL`은 기본값과 같았고,
   occlusion 3건은 생성하지 않는 유형이었다. #34에서 실제로 쓰이는 override(상향·하향·OCR field 단위)로 바꿨다.
   형식만 먼저 정하면 이런 일이 생긴다.
5. **CP949 콘솔에서 실험 스크립트가 exit 1로 끝났다(#49).** 기록은 다 끝난 뒤 마지막 안내문의 em dash에서 터졌다.
6. 문서 변경 이력에 작업 날짜를 계획일(09-26)로 잘못 적었다. 실제 수행일(09-25)로 정정했다.

---

## Decisions

1. **Recipe가 `expected_*`의 정본이다.** 좌표·폰트 같은 렌더링 세부는 domain spec이 아니라 코드(`pilot.py`)가 갖는다.
2. **바코드는 Code128.** 영숫자라 모델명을 그대로 인코딩한다. 리더는 Week 13에 정한다.
3. **정상 이미지에 촬영 nuisance를 준다.** 깨끗하면 AD baseline이 포화해서 E1/E4의 변별력이 사라진다.
   세기(`NUISANCE`)를 키운 subset이 E6가 된다.
4. **제품 단위 과검률 목표 F = 1%** (E1). 라벨 단위 f = 1 − (1 − F)^(1/L).
5. **미등록 라벨(E3)은 정상 row + `is_known_label=false`다.** Recipe가 요구하는 라벨이 실제로 붙어 있지만 onboarding만
   안 된 상태다. 불량으로 넣으면 DER에 섞여서 "미등록 라벨을 기존 라벨로 억지 분류했는가"라는 E3의 질문이 사라진다.
6. **불량 = 정상 라벨에 가하는 변형 1개.** 불량 unit은 Label Slot 한 곳만 불량이고, 정상 unit **뒤에** 붙는다.
   그래서 불량·E5를 추가해도 기존 그림이 바뀌지 않는다(위 표).
7. **E4 hold-out은 `unknown_visual`(인쇄 줄무늬 탈락)** — val에 없고 `is_known_defect=false`. 나머지 9종이 "본 유형"이다.
8. **E5 구간은 카탈로그에서 규칙으로 정한다.** 사람이 쌍을 고르지 않는다. 설계한 네 쌍이 규칙으로도 같은 구간이 됐고,
   설계 때 놓친 hard 쌍(a-3/b-3, a-3/b-4)을 규칙이 찾았다.
9. **Similar-label Confusion Rate = 구간별 바꿔치기 불량의 DER.** `decision`만 쓰므로 identity를 내지 않는 AD baseline에도
   적용된다. identity 혼동 행렬은 identity 모델이 생기는 Week 9에 보조 지표로 검토한다.
10. **registry의 `sha256`은 원본 아카이브 대신 Recipe 파일 해시다.** 생성 결과가 Recipe + 코드 + `sha256(sample_id)`
    seed만으로 정해지기 때문이다. 해시가 다르면 `build_pilot.py`가 멈추고 version을 올리게 한다.
11. 코드의 `DEFAULT_SEVERITY`는 `defect_taxonomy.md` 표의 사본이라, 테스트가 md를 파싱해서 대조한다.

---

## Next

- **Week 4 (#9, Month 1 Gate)**: #37 Label/Product-level 집계와 Unknown·REVIEW 지표 → #38 latency → #39 Gate 점검.
  Pilot은 제품당 라벨이 3~4장이라 **Product-level 집계를 처음으로 실제 데이터에서 확인할 수 있다**(public은 L=1).
- **#5 GPU 환경** — Week 5 전에 결정이 필요하다. latency 측정 환경이 중간에 바뀌면 앞선 결과를 버려야 한다.
- 완료 보고 방식(GitHub Wiki vs 저장소 안 문서)은 보류 중이다.

```text
이번 주에 결정한 것:
Recipe(configs/recipes/pilot.yaml)를 expected_*의 정본으로 두고, 3 products / 14 label identities의 Pilot을 전부
합성으로 만들었다(v0.3, 8816 rows, 위반 0건). 바코드는 Code128 6자, 정상 이미지에 촬영 nuisance, F=1%.
미등록 라벨은 정상 row + is_known_label=false. 불량은 정상 라벨에 가하는 변형 10종이고 unknown_visual이 E4
hold-out이다. E5 구간은 카탈로그 규칙으로 정하고 Similar-label Confusion Rate는 구간별 바꿔치기 DER로 정의했다.

아직 불확실한 것:
6자 Code128이 256px에서 실제 디코더로 읽히는가(모듈당 약 2px, Week 13). E5-extreme이 쌍 1개(b-3/b-4)뿐이라
그 구간 결과가 한 쌍의 특성일 수 있다 — Main benchmark(Week 17)에서 쌍을 늘려야 한다. hard 기준 "다른 글자 ≤ 2개"는
임의로 정한 값이다. 합성 불량이 실제 불량과 얼마나 닮았는가. GPU 환경(#5).

다음 주말 첫 번째 할 일:
Week 4 #37 — Label-level (unit_id, label_slot) / Product-level (unit_id) 집계를 구현하고, Pilot에서 Product-level
숫자가 실제로 나오는지 확인한다.
```
