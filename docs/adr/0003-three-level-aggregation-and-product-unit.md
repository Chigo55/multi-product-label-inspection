# 집계는 Defect/Label/Product 3-level로 하고 Product Unit을 명시적 키로 둔다

동일한 실험을 Defect-level(개별 결함), Label-level(라벨 1장), **Product-level(물리적 제품 1개)**
세 단위로 모두 보고한다. Label-level 성능이 좋아도 제품당 라벨이 많으면 Product-level 과검률이
급격히 악화되므로, 현장 KPI와 직결되는 것은 Product-level이다.

**Product-level 판정 규칙: 제품에 속한 라벨 중 하나라도 `NG`면 제품은 `NG`다 (Severity 무관).**
`NG`가 없고 `REVIEW`가 하나라도 있으면 제품은 `REVIEW`다. 즉 `NG`가 `REVIEW`보다 우선한다.
`CRITICAL`만 제품 `NG`로 보는 안도 검토했으나, 그렇게 하면 찢어진 라벨(`MAJOR`)이 붙은 제품이
Product-level에서 정상으로 집계되어 지표가 현장 감각과 어긋난다. `CRITICAL`은 Critical Escape
Rate로 이미 따로 추적하므로 이 규칙과 중복되지 않는다.

## Consequences

집계하려면 **여러 라벨·여러 카메라 row가 같은 물리적 제품에서 나왔다는 사실**을 알아야 한다.
Dataset Schema v0.1에는 그 키가 없어 Product-level 계산이 불가능했다. v0.2에서 `unit_id`를
추가해 Level 2는 `(unit_id, label_slot)`, Level 3는 `unit_id`로 group by 한다. `sample_id`
문자열 파싱으로 대신하는 안은, 파싱 규약이 깨졌을 때 조용히 틀린다는 이유로 택하지 않았다.
