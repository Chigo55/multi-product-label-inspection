# Primary Metric은 Defect Escape Rate로 한다

산업 검사에서 놓친 불량 1건의 비용은 과검 1건의 비용과 비교가 안 되므로, 모든 모델 비교표의
첫 번째 열을 **Defect Escape Rate**(= 불량 중 `OK`로 판정된 비율, FNR)로 고정하고
**Severity가 `CRITICAL`인 불량의 Escape Rate를 실질적 최우선 지표**로 둔다.

Accuracy는 대표 지표로 쓰지 않는다. 불량이 희소해서 전부 정상이라 답해도 높게 나오기 때문이다.
선행 연구(MVTec 계열)와 비교하기 위해 AUROC를 병기하되, 불량 희소 조건에서는 AUPRC를 더 신뢰한다.

## Consequences

threshold-free 지표(AUPRC/AUROC)와 threshold-dependent 지표(Escape Rate/FPR)를 항상 함께
보고해야 한다. 전자만으로는 실제 운용 지점의 성능을 알 수 없고, 후자만으로는 threshold 선택에
결과가 좌우된다.
