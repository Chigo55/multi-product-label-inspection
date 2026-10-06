"""reports/evaluation_protocol.md §7 Latency의 코드 정본.

측정 단위는 **제품 1개**다 (라벨 1개가 아니다). pipeline 함수는 제품 하나를 끝까지 처리하고,
구간마다 `with stage("detection"):`으로 감싼다. 전체 시간은 구간 합이 아니라 처음부터 끝까지 잰
벽시계 시간이다 — 구간으로 감싸지 않은 부분(전처리 등)도 빠지지 않는다.

GPU는 비동기라 커널이 끝나기 전에 시계를 읽을 수 있다. `sync`에 `torch.cuda.synchronize`를 넘긴다.
"""

from __future__ import annotations

import platform
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import numpy as np

STAGES = (
    "acquisition", "transfer", "registration", "detection", "roi", "identity",
    "anomaly", "ocr", "barcode", "rule", "aggregation",
)  # fmt: skip
BANDS = (("<=100ms", 100), ("100-500ms", 500), ("500-1000ms", 1000), (">1000ms", float("inf")))
MIN_ITERS = 100

Stage = Callable[[str], AbstractContextManager[None]]


def measure(
    pipeline: Callable[[Any, Stage], object],
    products: Sequence[Any],
    warmup: int = 10,
    iters: int = 100,
    sync: Callable[[], object] = lambda: None,
    clock: Callable[[], float] = time.perf_counter,
) -> list[dict[str, float]]:
    """products를 돌아가며 warmup + iters번 처리하고, warm-up을 뺀 제품별 ms 기록을 낸다."""
    if iters < MIN_ITERS:
        raise ValueError(f"iters({iters}) < {MIN_ITERS}: protocol §7은 최소 {MIN_ITERS}회 반복")
    if not products:
        raise ValueError("측정할 제품이 없다")

    def now() -> float:
        sync()
        return clock()

    records = []
    for i in range(warmup + iters):
        spent: dict[str, float] = defaultdict(float)
        start = now()
        pipeline(products[i % len(products)], _recorder(spent, now))
        total = (now() - start) * 1000
        if i >= warmup:
            records.append({"total": total, **spent})
    return records


def _recorder(spent: dict[str, float], now: Callable[[], float]) -> Stage:
    """`with stage(name):` 블록 시간을 spent[name]에 ms로 더한다. 같은 구간을 여러 번 들어가면 합친다."""

    @contextmanager
    def stage(name: str) -> Iterator[None]:
        if name not in STAGES:  # 오타가 breakdown을 조용히 쪼개지 않게
            raise ValueError(f"알 수 없는 구간: {name} (가능: {STAGES})")
        start = now()
        yield
        spent[name] += (now() - start) * 1000

    return stage


def summarize(records: Sequence[dict[str, float]]) -> dict[str, Any]:
    """P50/P95/P99(제품 1개 기준), 구간별 평균, 시간대별 제품 수."""
    total = np.array([r["total"] for r in records])
    p50, p95, p99 = np.percentile(total, [50, 95, 99])
    bands = dict.fromkeys((name for name, _ in BANDS), 0)
    for t in total:
        bands[next(name for name, upper in BANDS if t <= upper)] += 1
    return {
        "latency_n": len(records),
        "latency_p50": float(p50),
        "latency_p95": float(p95),
        "latency_p99": float(p99),
        "latency_stage_mean_ms": {
            s: float(np.mean([r.get(s, 0.0) for r in records]))
            for s in STAGES
            if any(s in r for r in records)
        },
        "latency_bands": bands,
    }


def environment(device: str, batch_size: int, resolution: str, precision: str) -> dict[str, str]:
    """MLflow params용 측정 환경 (§7). GPU 이름은 torch가 있을 때만 붙는다."""
    env = {
        "device": device,  # protocol §9 param 이름
        "latency_batch_size": str(batch_size),
        "latency_resolution": resolution,
        "latency_precision": precision,
        "host_platform": platform.platform(),
        "host_cpu": platform.processor() or platform.machine(),
        "python": sys.version.split()[0],
    }
    try:
        import torch  # pyrefly: ignore[missing-import]  torch는 하드웨어별 설치 (AGENTS.md)
    except ImportError:
        return env
    env["torch"] = torch.__version__
    if torch.cuda.is_available():
        env |= {"gpu": torch.cuda.get_device_name(0), "cuda": str(torch.version.cuda)}
    return env
