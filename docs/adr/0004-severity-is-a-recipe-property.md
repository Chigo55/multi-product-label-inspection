# Severity는 불량 유형이 아니라 Recipe가 정한다

Defect Taxonomy의 Severity 열은 **기본값일 뿐이고**, 최종 Severity는 Product Type별
Inspection Recipe에서 override할 수 있다. 같은 `ocr_mismatch`라도 `MODEL` field가 틀리면
`CRITICAL`이지만 `DATE` field면 `MAJOR`이고, 같은 `contamination`이라도 barcode 영역을 덮으면
`MINOR`가 아니라 `CRITICAL`이기 때문이다. 불량 유형만 보고 Severity를 정하면 이 구분이 사라진다.

dataset metadata에는 **override가 적용된 최종 Severity**를 기록한다.

## Consequences

Critical Escape Rate는 Recipe에 상대적인 지표다. Recipe가 다른 두 데이터셋의 Critical Escape
Rate를 나란히 놓고 비교하면 안 되며, 비교할 때는 Recipe 버전을 함께 명시해야 한다.
