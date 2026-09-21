# 판정은 OK/NG/REVIEW 3-state로 하고 REVIEW를 분리 집계한다

이진 판정만 두면 애매한 샘플을 반드시 `OK` 아니면 `NG`로 밀어넣어야 하고, 그 강제 선택이 그대로
Escape나 과검으로 계상된다. 그래서 두 개의 threshold로 판정 보류 구간을 만들어
`score < ok → OK`, `score > ng → NG`, 그 사이는 **`REVIEW`(사람이 확인)** 로 둔다.

집계 시 `REVIEW`는 **Escape도 False Reject도 아니다** — 사람에게 도달했기 때문이다. 대신
`REVIEW` 비율을 **Review Rate**라는 별도의 비용 지표로 보고한다.

## Consequences

- 모든 지표는 `REVIEW`를 어떻게 처리했는지 명시해야 의미가 있다. 2-state 비교(AUROC 등)가
  필요하면 `REVIEW`를 `NG`로 합친 값을 함께 적는다.
- Review Rate를 함께 보지 않으면 "전부 REVIEW로 보내서 Escape 0" 같은 무의미한 최적해를
  걸러낼 수 없다.
- threshold는 `val`(또는 calibration) split에서만 정한다. `test`로 정하면 위 세 값이 전부
  낙관적으로 편향된다.
