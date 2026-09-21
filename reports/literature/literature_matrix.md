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
| [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) | 2019 | CVPR (IJCV 2021 ext.) | Industrial AD benchmark (15 cat.) | ● | ✕ | ○ | ✕ | ✕ | ✕ | dataset | **CC BY-NC-SA 4.0** (상업 이용 금지) | ✕ | 사실상 표준 benchmark. **벤치마크 전용** — 배포 모델 학습 데이터로 쓰지 않는다 |
| [MVTec LOCO AD](https://www.mvtec.com/company/research/datasets/mvtec-loco) | 2022 | IJCV | Structural **vs Logical** anomaly benchmark | ● | ✕ | ○ | ✕ | ● | ✕ | dataset | **CC BY-NC-SA 4.0** (상업 이용 금지) | ✕ | **이번 연구의 logical 축과 직접 연결.** 평가지표 sPRO. 요약: [`mvtec_loco_ad.md`](mvtec_loco_ad.md) |
| [PatchCore](https://arxiv.org/abs/2106.08265) | 2022 | CVPR | Memory-bank 기반 normal-only AD | ● | ○ | ✕ | ✕ | ✕ | ○ heatmap | [amazon-science/patchcore-inspection](https://github.com/amazon-science/patchcore-inspection), anomalib | Apache-2.0 (코드) ⚠️ backbone weights 별도 | ○ | **필수 baseline.** backbone이 ImageNet 사전학습 WideResNet50 → 아래 §라이선스 확인 결과. 요약: [`patchcore.md`](patchcore.md) |
| [EfficientAD](https://arxiv.org/abs/2303.14535) | 2024 | WACV | 밀리초급 AD | ● | ✕ | ✕ | ✕ | ○ | ○ heatmap | **공식 구현 없음.** [anomalib](https://github.com/open-edge-platform/anomalib/tree/main/src/anomalib/models/image/efficient_ad), [nelson1425/EfficientAD](https://github.com/nelson1425/EfficientAD) (둘 다 비공식) | Apache-2.0 (비공식 코드) ⚠️ teacher weights·ImageNet 별도 | ● | **100/500/1000ms 비교의 핵심 후보.** 학습에 ImageNet(anomalib은 Imagenette) 이미지가 들어간다 |
| [DINOv2](https://arxiv.org/abs/2304.07193) | 2023/24 | TMLR | Self-supervised visual foundation model | n/a | n/a | n/a | n/a | ✕ | ✕ | [facebookresearch/dinov2](https://github.com/facebookresearch/dinov2) | **Apache-2.0 (코드+weights)** | ○ | Label identity / AD의 공통 backbone. **상업 이용 가능.** 2023-08 CC-BY-NC→Apache-2.0 변경. 같은 레포의 XRay-DINO·Cell-DINO weights는 FAIR Noncommercial — 혼동 주의 |
| [AnomalyDINO](https://arxiv.org/abs/2405.14529) | 2025 | WACV | DINOv2 기반 **training-free few-shot** AD | ● | ● | ○ | ✕ | ✕ | ○ | [dammsi/AnomalyDINO](https://github.com/dammsi/AnomalyDINO) (공식) | Apache-2.0 | ○ | **RQ4 신규 라벨 onboarding과 직결.** backbone DINOv2(Apache-2.0) |
| [Dinomaly](https://arxiv.org/abs/2405.14325) | 2025 | CVPR | Multi-class unsupervised AD (unified) | ● | ○ | ● | ✕ | ○ | ○ | [guojiajeremy/Dinomaly](https://github.com/guojiajeremy/Dinomaly) (공식) | Apache-2.0 | ? | **Architecture D 핵심 baseline.** backbone DINOv2(Apache-2.0). 확장판 Dinomaly2 별도 레포 |
| [INP-Former](https://arxiv.org/abs/2503.02424) | 2025 | CVPR | Intrinsic normal prototype / universal AD | ● | ● | ● | ✕ | ○ | ○ | [luow23/INP-Former](https://github.com/luow23/INP-Former) (공식) | MIT | ? | Dinomaly와 함께 unified 비교군. 배포된 학습 weights는 MVTec/VisA/Real-IAD로 학습 → 데이터셋 조건을 따른다 |
| [OpenMax](https://arxiv.org/abs/1511.06233) | 2016 | CVPR | Open-set recognition의 기초 | ✕ | ✕ | ● | ● | ✕ | ✕ | [abhijitbendale/OSDN](https://github.com/abhijitbendale/OSDN) (공식) | BSD-3-Clause ⚠️ 번들 libMR은 **비상업 전용** | ● | **Unknown label 거부의 출발점 (RQ1/RQ3).** Weibull fitting을 libMR 대신 직접 구현해야 한다 |
| [Prototypical Networks](https://arxiv.org/abs/1703.05175) | 2017 | NeurIPS | Few-shot metric learning | ✕ | ● | ● | ○ | ✕ | ✕ | [jakesnell/prototypical-networks](https://github.com/jakesnell/prototypical-networks) (공식) | MIT | ● | **Prototype 등록 구조의 이론적 근거 (RQ4)** |

### 라이선스 확인 결과 (2026-09-21, #6)

원문(데이터셋 공식 페이지, 레포 LICENSE/README)에서 직접 확인했다. **법률 자문이 아니라 공개 조건의
기록**이며, 특허는 조사하지 않았다.

판단 기준(#6): 논문·벤치마크 목적이면 non-commercial도 쓴다. **최종 파이프라인에 들어갈 구성요소**
(backbone, 모델 코드, 배포 weights)만 상업 이용 가능해야 한다.

| 구분 | 대상 | 조건 | 판단 |
|---|---|---|---|
| 벤치마크 | MVTec AD, MVTec LOCO AD | CC BY-NC-SA 4.0 — "not allowed to use the dataset for commercial purposes" | 벤치마크로만 쓴다. 이 데이터로 학습한 weights는 배포하지 않는다 |
| 벤치마크 | VisA (참고) | CC BY 4.0 (amazon-science/spot-diff) | 상업 이용 가능한 public benchmark. Week 2 이후 후보 |
| 배포 가능 | DINOv2 backbone (`dinov2_vit*14`, `*_reg`) | Apache-2.0, 코드+weights | **최종 파이프라인 backbone으로 사용 가능** |
| 배포 가능 | anomalib, PatchCore 공식 코드, AnomalyDINO, Dinomaly | Apache-2.0 | 코드는 사용 가능 |
| 배포 가능 | INP-Former, Prototypical Networks | MIT | 코드는 사용 가능 |
| ⚠️ 조건부 | PatchCore / EfficientAD의 ImageNet 사전학습 weights | torchvision: "pre-trained models ... may have their own licenses ... derived from the dataset used for training" | 불명확. **대체: backbone을 DINOv2로 교체**하거나 배포 전 법무 확인 |
| ⚠️ 조건부 | EfficientAD 학습 | ImageNet(anomalib은 Imagenette) 이미지를 loss에 사용 | 위와 같음. 배포용이면 상업 이용 가능한 일반 이미지셋으로 교체 |
| ✕ 불가 | OpenMax 공식 구현의 libMR | "For-profit companies may not use this source code", 특허 출원(CU TTO File CU2338C) 언급 | libMR 대신 `scipy.stats`로 Weibull fitting 직접 구현. **특허 등록 여부는 배포 전 확인** |
| 참고 | DINOv3 | 자체 "DINOv3 License" (Apache 아님). NC 조항은 없고 ITAR·무역 제재 용도 금지 | 도입 시 원문 재확인 |

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
