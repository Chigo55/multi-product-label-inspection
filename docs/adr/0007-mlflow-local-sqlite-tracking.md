# 실험 추적은 로컬 SQLite MLflow로 한다

MLflow 3.x부터 파일 기반 tracking store(`./mlruns`)는 maintenance mode라 최신 기능을 쓸 수 없다.
그렇다고 tracking server나 Docker를 세우면 1인 연구에 비해 운영 부담이 크다. 그래서
**로컬 SQLite(`sqlite:///mlflow.db`)** 를 backend store로 쓴다 — 서버 없이 최신 기능을 그대로 쓴다.

재현성은 MLflow 단독이 아니라 **로컬 SQLite MLflow + YAML config + git commit** 세 가지를 함께
기록해서 확보한다. 모든 run은 `git_commit`, `dataset_version`, `config_path`를 param으로 남기고
config 파일 사본을 artifact로 저장한다.

## Consequences

`mlflow.db`와 `mlartifacts/`는 커밋하지 않는다. 따라서 **저장소를 clone해도 실험 이력은 따라오지
않는다.** 결과를 남기려면 논문/보고서에 인용할 숫자가 `reports/`에 텍스트로 들어가 있어야 한다.
