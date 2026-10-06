"""reports/evaluation_protocol.md §7 Latency. 가짜 시계로 시간을 정확히 정한다."""

from __future__ import annotations

import pytest

from src.evaluation.latency import environment, measure, summarize


def _fake() -> tuple:
    """detection 구간에 제품값 ms, 구간 밖 전처리에 1 ms를 쓰는 pipeline과 가짜 시계."""
    now = [0.0]

    def pipeline(ms: float, stage) -> None:
        now[0] += 0.001  # 구간으로 감싸지 않은 시간도 total에 들어가야 한다
        with stage("detection"):
            now[0] += ms / 1000

    return pipeline, lambda: now[0]


def test_total_is_wall_clock_and_warmup_is_dropped() -> None:
    pipeline, clock = _fake()
    products = [1000.0] * 3 + [9.0] * 100  # 앞 3개가 느린 warm-up
    rec = measure(pipeline, products, warmup=3, iters=100, clock=clock)
    assert len(rec) == 100
    assert rec[0]["total"] == pytest.approx(10.0)
    assert rec[0]["detection"] == pytest.approx(9.0)


def test_summary_percentiles_stage_means_and_bands() -> None:
    pipeline, clock = _fake()
    products = [float(ms) for ms in range(10, 1010, 10)]  # 10 ~ 1000 ms, total = +1
    s = summarize(measure(pipeline, products, warmup=0, iters=100, clock=clock))
    assert s["latency_n"] == 100
    assert s["latency_p50"] == pytest.approx(506.0)
    assert s["latency_p95"] == pytest.approx(951.5)
    assert s["latency_stage_mean_ms"] == {"detection": pytest.approx(505.0)}
    # total 11..1001: <=100은 11..91 (9개), 1001은 >1000
    assert s["latency_bands"] == {"<=100ms": 9, "100-500ms": 40, "500-1000ms": 50, ">1000ms": 1}


def test_sync_is_called_before_every_clock_read() -> None:
    """GPU 비동기: 시계를 읽기 전에 항상 sync해야 커널 시간이 잡힌다."""
    pipeline, clock = _fake()
    calls = []
    measure(pipeline, [1.0], warmup=0, iters=100, sync=lambda: calls.append(1), clock=clock)
    assert len(calls) == 100 * 4  # 제품마다 total 시작/끝 + detection 시작/끝


def test_rejects_too_few_iters_and_unknown_stage() -> None:
    pipeline, clock = _fake()
    with pytest.raises(ValueError, match="100"):
        measure(pipeline, [1.0], iters=99, clock=clock)

    def typo(_, stage) -> None:
        with stage("detecton"):
            pass

    with pytest.raises(ValueError, match="detecton"):
        measure(typo, [1.0], clock=clock)


def test_environment_records_measurement_conditions() -> None:
    env = environment("cpu", 1, "256x256", "fp32")
    assert {
        "device",
        "latency_batch_size",
        "latency_resolution",
        "latency_precision",
    } <= env.keys()
    assert env["python"]
