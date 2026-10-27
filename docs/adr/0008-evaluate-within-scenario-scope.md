# 평가는 시나리오 범위로 한다

test 전체를 한 번에 `evaluate()`하지 않고, **시나리오(E1·E3·E4·E5)마다 범위를 잘라 따로 평가한다.** E2·E6는 데이터가 생길 때 범위를 더한다.
미등록 라벨이 붙은 row는 `normal_or_defect=normal`이다. 시스템이 그 라벨을 올바르게 거부(NG)하면
전체 평가에서는 과검으로 잡힌다. Pilot v0.3 test의 정상 제품 300개 중 40개(13.3%)가 미등록 라벨
revision이라, E3를 잘할수록 제품 FPR이 13.3% 이상으로 올라가 F=1% 목표와 비교할 수 없었다.
**F 판단과 헤드라인 FPR·DER은 E1 결과만 쓴다.**

범위는 **unit 단위**로 고른다. 한 unit의 row를 쪼개면 Product-level 판정(ADR 0003)이 달라진다.
범위 규칙의 정본은 `reports/experiment_scenarios.md` "평가 범위", 코드는 `src/evaluation/scenarios.py`다.

E5 전용 unit(구간마다 72개, test에만)은 E1에서 뺀다. 넣으면 E1의 불량 구성이 바꿔치기 쪽으로
쏠린다. 일반 불량 unit에서 무작위로 생긴 바꿔치기는 E1에 남는다. 둘을 구별하려고 Pilot v0.4부터
전용 unit의 모든 row에 `E5` 태그를 단다 — 평가 코드는 metadata만 읽어야 하므로(ADR 0006)
생성 순서(unit 순번)로 추정하는 안은 택하지 않았다.

## Consequences

MLflow 지표 이름에 시나리오 접두사가 붙는다(`e1_false_positive_rate_product` …, protocol §9).
접두사 없는 전체 평가 지표는 더 기록하지 않는다 — Week 4 이전 run과 이름이 달라 직접 비교되지 않는다.
범위가 빈 시나리오(public track의 E3·E4·E5)는 결과에 없다. 0%로 보고하지 않는다.

Pilot v0.4(#69)에서 같은 이유로 덧붙인 unit 묶음이 늘었다 — 위치·각도 경계(`GEOM-boundary`)와 OCR 혼동 문자
(`OCR-confusable`). 둘 다 E1·E4에서 빼고 각자의 범위로 따로 평가한다(접두사 `geom_boundary_`, `ocr_confusable_`).
