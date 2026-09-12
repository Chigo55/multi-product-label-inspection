# Public benchmark와 자체 benchmark를 하나의 metadata 스키마로 다룬다

MVTec AD/LOCO, VisA 같은 public benchmark와 자체 Multi-Product Multi-Label benchmark는 원본
디렉터리 구조와 annotation 형식이 전부 다르다. 각각에 맞춰 평가 코드를 따로 만드는 대신,
모두 **동일한 metadata 형식(1 샘플 = 1 row, JSONL)** 으로 변환해서 평가 코드를 한 번만 만든다.

public benchmark에는 product/label 개념이 없으므로 `product_id`에 category를 매핑하고
Label Identity는 비워 둔다. Expected 값이 없으므로 **Logical 검사 항목은 평가에서 자동 제외된다.**

## Consequences

새 데이터셋을 붙이는 비용이 "변환기 1개"로 고정되는 대신, 스키마가 두 세계의 교집합에 맞춰
움직인다. 어느 한쪽에만 있는 정보를 쓰려면 스키마를 바꿔야 하고, 그때마다 버전을 올린다.
