# Jetson Nano latency는 Python 3.12 본 프로세스 + Python 3.6 TensorRT worker로 잰다 (초안)

> 상태: **초안** (2026-10-27, #69 T4). 주말 4(11-21~22) spike 결과로 확정하거나 C로 바꾼다 — #69 결정 4.

보고용 latency는 Jetson Nano 한 대에서만 잰다(#5). 그런데 저장소는 `requires-python >= 3.12`이고, Jetson Nano
1세대의 마지막 JetPack 4.6은 Ubuntu 18.04 / **Python 3.6** / CUDA 10.2이며 TensorRT Python 바인딩도 3.6용뿐이다.
protocol §7은 구간 합이 아니라 **제품 1개를 처음부터 끝까지 잰 벽시계 시간**을 요구하므로, 두 런타임을 한 측정으로
묶는 방법을 정해야 한다.

| 안 | 구조 | 장점 | 단점 |
|---|---|---|---|
| **A (권장)** | uv로 설치한 Python 3.12 본 프로세스가 파이프라인 전체를 돌리고 시계를 쥔다. CPU 구간(registration, OCR, 바코드, rule)은 그대로 `src/`를 쓰고, AD 추론만 Python 3.6 TensorRT worker에 IPC로 보낸다 | 측정 대상 코드가 실험 코드와 같다. IPC 비용이 벽시계에 들어가 숨지 않는다 | IPC(직렬화·복사)가 latency에 더해진다. Nano에 3.12와 aarch64 wheel이 올라가야 한다 |
| B | Jetson 전용 runner를 Python 3.6 호환 코드로 따로 유지한다 | 프로세스 하나라 IPC가 없다 | 같은 파이프라인을 두 벌 유지한다. 실험 코드와 측정 코드가 갈라져 "잰 것이 그 시스템인가"를 보장하지 못한다 |
| C | 장비를 바꾼다 (Orin Nano 등, JetPack 6 = Python 3.10) | 최신 TensorRT, 여유 있는 성능 | 비용. Python 3.10이라 3.12 본 프로세스와의 간극은 여전히 남을 수 있다. 기준 문서 §31의 보유 장비 전제가 바뀐다 |

A를 권장한다. B는 측정 결과가 실험 코드를 대표하지 못하는 것이 치명적이고, C는 비용이 들면서도 버전 간극을 완전히
없애지 못한다. A의 IPC 비용은 숨길 대상이 아니라 실제 배포 구조에서도 생기는 비용이므로 벽시계에 그대로 넣는다.
`src/evaluation/latency.py`는 이미 벽시계를 재므로, worker 호출을 `with stage("anomaly"):`로 감싸면 구간 breakdown에
IPC가 포함된 AD 시간이 나온다.

## spike에서 확인할 것 (주말 4, `citable=false`)

1. PatchCore backbone을 ONNX로 export → Nano에서 `trtexec --fp16` latency.
2. Nano(Ubuntu 18.04, glibc 2.27, aarch64)에 uv로 Python 3.12 설치, `uv sync`가 되는가.
   특히 manylinux 2.28 이상만 내는 wheel(zxing-cpp 등)이 막히는지. pyzbar는 시스템 `libzbar0`(18.04는 0.10).
3. 3.12 본 프로세스 ↔ 3.6 worker 왕복 IPC 비용 (256×256 ROI × 제품당 라벨 수).

결과는 #5에 기록한다. 2가 막히면 C를 검토한다.

## Consequences

확정되면 보고용 latency run은 `latency.device=jetson`이고 params에 worker 런타임(Python, TensorRT, JetPack 버전)과
IPC 방식을 남긴다. 대여 GPU에서 잰 latency는 여전히 참고치다(#5).
