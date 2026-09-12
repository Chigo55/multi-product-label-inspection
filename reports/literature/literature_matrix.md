# Literature Matrix

> 작성일: 2026-09-12 (Week 1) / 최종 목표: **30~50편**
> Week 1의 목적은 논문을 다 읽는 것이 아니라 **표 구조를 고정하고 Tier 1 목록을 등록**하는 것이다.
>
> ⚠️ **검증 규칙**: 아래 venue / arXiv ID / License는 등록 시점의 메모이며,
> 해당 논문을 실제로 읽을 때 원문에서 확인하고 정정한다. `?` 표시는 미확인이라는 뜻이다.
> **License와 Code는 후보 선정의 실질 기준이므로(기준 문서 §34) 반드시 원문/레포에서 직접 확인한다.**

## 범례

| 기호 | 의미 |
|---|---|
| ● | 해당 논문이 직접 다루는 핵심 축 |
| ○ | 부분적으로 다룸 / 확장 가능 |
| ✕ | 다루지 않음 |
| ? | 미확인 (읽고 채운다) |

컬럼 의미:

- **Normal-only**: 불량 샘플 없이 정상 데이터만으로 학습 가능한가 (RQ2)
- **Few-shot**: 소수 정상 reference만으로 동작하는가 (RQ4)
- **Multi-class**: 하나의 모델로 다품종을 처리하는가 (RQ1)
- **Open-set**: 미등록/미지 입력을 거부할 수 있는가 (RQ1, RQ3)
- **Logical**: 논리적/문맥적 이상을 다루는가 (RQ3)
- **XAI**: 판정 근거 설명을 제공하는가 (RQ6)
- **Latency**: 속도를 보고하는가 / 실시간성 (RQ6)

---

## Tier 1 — 필수 정독

| Paper | Year | Venue | Problem | Normal-only | Few-shot | Multi-class | Open-set | Logical | XAI | Code | License | Latency | Notes |
| ----- | ---: | ----- | ------- | ----------- | -------- | ----------- | -------- | ------- | --- | ---- | ------- | ------- | ----- |
| [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) | 2019 | CVPR (IJCV 2021 ext.) | Industrial AD benchmark (15 cat.) | ● | ✕ | ○ | ✕ | ✕ | ✕ | dataset | non-commercial? | ✕ | 사실상 표준 benchmark. **상업적 이용 조건 확인 필요** |
| [MVTec LOCO AD](https://www.mvtec.com/company/research/datasets/mvtec-loco) | 2022 | IJCV | Structural **vs Logical** anomaly benchmark | ● | ✕ | ○ | ✕ | ● | ✕ | dataset | non-commercial? | ✕ | **이번 연구의 logical 축과 직접 연결.** 평가지표 sPRO. 요약: [`mvtec_loco_ad.md`](mvtec_loco_ad.md) |
| [PatchCore](https://arxiv.org/abs/2106.08265) | 2022 | CVPR | Memory-bank 기반 normal-only AD | ● | ○ | ✕ | ✕ | ✕ | ○ heatmap | [amazon-science/patchcore-inspection](https://github.com/amazon-science/patchcore-inspection), anomalib | Apache-2.0? | ○ | **필수 baseline.** 요약: [`patchcore.md`](patchcore.md) |
| [EfficientAD](https://arxiv.org/abs/2303.14535) | 2024 | WACV | 밀리초급 AD | ● | ✕ | ✕ | ✕ | ○ | ○ heatmap | anomalib (비공식 재현) | ? | ● | **100/500/1000ms 비교의 핵심 후보** |
| [DINOv2](https://arxiv.org/abs/2304.07193) | 2023/24 | TMLR | Self-supervised visual foundation model | n/a | n/a | n/a | n/a | ✕ | ✕ | [facebookresearch/dinov2](https://github.com/facebookresearch/dinov2) | **요확인 (weights 라이선스)** | ○ | Label identity / AD의 공통 backbone. **상업적 사용 가능 여부 반드시 확인** |
| [AnomalyDINO](https://arxiv.org/abs/2405.14529) | 2025 | WACV | DINOv2 기반 **training-free few-shot** AD | ● | ● | ○ | ✕ | ✕ | ○ | ? | ? | ○ | **RQ4 신규 라벨 onboarding과 직결** |
| [Dinomaly](https://arxiv.org/abs/2405.14325) `arXiv ID?` | 2025 | CVPR? | Multi-class unsupervised AD (unified) | ● | ○ | ● | ✕ | ○ | ○ | ? | ? | ? | **Architecture D 핵심 baseline** |
| [INP-Former](https://arxiv.org/abs/2503.02424) `arXiv ID?` | 2025 | CVPR? | Intrinsic normal prototype / universal AD | ● | ● | ● | ✕ | ○ | ○ | ? | ? | ? | Dinomaly와 함께 unified 비교군 |
| [OpenMax](https://arxiv.org/abs/1511.06233) | 2016 | CVPR | Open-set recognition의 기초 | ✕ | ✕ | ● | ● | ✕ | ✕ | ? | ? | ● | **Unknown label 거부의 출발점 (RQ1/RQ3)** |
| [Prototypical Networks](https://arxiv.org/abs/1703.05175) | 2017 | NeurIPS | Few-shot metric learning | ✕ | ● | ● | ○ | ✕ | ✕ | 다수 공개 | MIT 계열? | ● | **Prototype 등록 구조의 이론적 근거 (RQ4)** |

---

## Tier 2 — 비교용 (Week 5~ 등록)

WinCLIP / PromptAD / AA-CLIP / UniAD / Reverse Distillation / FastFlow / CFLOW-AD / SimpleNet

## Tier 3 — 방향 확정 후 (Month 3~)

Logical AD / Continual Learning / Synthetic Anomaly / XAI / VLM-based AD / Domain Robustness

## 별도 조사군 — 상용 산업 비전 (논문 아님)

Cognex / KEYENCE / MVTec HALCON.
비교 질문: 정상 데이터만으로 학습 가능한가 / Rule+AI 결합 / OCR·Barcode / Logical anomaly 처리 /
REVIEW 상태 유무 / Edge 배포 / 설명가능성 / 신규 품목 추가 방식. (기준 문서 §68)

---

## 읽기 기록

각 논문은 읽은 뒤 `reports/literature/<slug>.md`에 6항목으로 요약한다.

```text
Problem / Input / Training Data / Method / Output / Limitation for my problem
```

**`Limitation for my problem`이 가장 중요하다.** 이 항목이 Research Gap의 원재료다.

| 논문 | 상태 | 요약 파일 |
|---|---|---|
| MVTec LOCO AD | 훑어봄 (Week 1) | [`mvtec_loco_ad.md`](mvtec_loco_ad.md) |
| PatchCore | 훑어봄 (Week 1) | [`patchcore.md`](patchcore.md) |
| 나머지 Tier 1 | 미착수 | - |
