# 260513 - Rig-Spherical Proposal 방식 비교

## 진행 방식 요약

이번 비교는 pose 구조나 전체 3DGS 학습 방식을 바꾼 실험이 아님. 같은 rig-aware OTF pipeline 안에서 **새 Gaussian 후보 pixel 을 고르는 policy** 만 바꿔 비교한 실험임.

| 단계 | 내용 |
|---:|---|
| 1 | 처음 가설: residual / LoG / depth confidence 가 높은 pixel 을 고르면 좋은 Gaussian 후보가 될 것이라고 봄 |
| 2 | 확인하고 싶은 점: confidence-only top-K 가 실제로 품질과 geometry 를 개선하는지 확인 |
| 3 | 수정 가설: zero-baseline EQR virtual rig 에서는 pixel 점수보다 rig direction support 를 넓게 유지하는 것이 더 중요할 수 있음 |
| 4 | 검증 방식: legacy, confidence, random, image-tile, rig-spherical, score-mixture 를 같은 safety stack 에서 비교 |

핵심 결론은 confidence-only top-K 가 MVS 에 받아들여지기 쉬운 후보를 고르더라도, 후보가 특정 방향이나 edge 근처에 몰리면 holdout 품질이 낮아질 수 있다는 점임.  
반대로 rig-spherical direction 을 기준으로 후보를 분산시키는 방식이 현재 sequence 에서 더 안정적인 PSNR / Gaussian 수 / runtime Pareto 를 보였음.

## 공통 설정

| 항목 | 설정 | 의미 |
|---|---|---|
| Pose 구조 | timestamp-shared rig pose | 같은 timestamp 의 9 view 가 하나의 rig pose 를 공유 |
| Same-ts depth 처리 | MVS / triangulation source 에서 제외 | 9 view 는 same-center zero-baseline 이므로 같은 timestamp 에서는 parallax depth 가 없음 |
| Spawn 단위 | atomic timestamp packet | 같은 timestamp 의 view 추가 순서가 spawn 결과를 바꾸지 않도록 함 |
| Depth source | cross-timestamp GuidedMVS + matched points | depth 는 시간축 baseline 에서만 얻음 |
| 안정화 | spawn sanity, artifact prune, hard-phys guard | method contribution 이 아니라 crash / outlier 방지용 safety stack |
| Iteration | 270 steps / keyframe | batch 30k 3DGS 와 달리 streaming 조건에서 제한된 local update 로 학습 |

## 비교군 정의

아래 비교군은 방법 이름을 나열한 것이 아니라, 하나의 가설을 단계적으로 검증하기 위한 ladder 임.

| 단계 | label | 쉽게 말하면 | 이 비교군이 답하는 질문 |
|---:|---|---|---|
| 1 | `legacy` | 원본 OTF-style 로 texture / LoG 기반 후보를 많이 생성 | 기존 density 방식이 얼마나 강한 기준선인가? |
| 2 | `full 12k` | heuristic confidence score 가 높은 pixel 만 top-K 로 선택 | 점수 높은 pixel 을 고르면 충분한가? |
| 3 | `random 12k` | LoG-positive pixel 안에서 uniform random | 점수 없이 넓게 퍼뜨리는 것만으로도 되는가? |
| 4 | `tile 12k` | image 를 tile 로 나누고 tile 마다 균등 선택 | image-plane spread 면 충분한가? |
| 5 | `sph_strat 12k` | pixel 을 rig 기준 3D ray 방향으로 바꾼 뒤, yaw / pitch 방향 구간별로 골고루 선택 | EQR virtual rig 에서는 direction spread 가 더 자연스러운가? |
| 6 | `sph_strat 24k` | direction spread 는 유지하고 budget 만 2배 | support 를 유지한 채 품질을 legacy 수준으로 올릴 수 있는가? |

- `sph_strat` : image 좌표에서 균등하게 고르는 방식이 아니라, 각 pixel 이 실제 rig 기준으로 어느 방향을 보는지 계산한 뒤 방향 구간별로 후보를 나누어 뽑는 방식임. 즉 texture 가 강한 한쪽 image 영역에만 Gaussian spawn 이 몰리지 않도록, 현재 rig 가 관측한 방향 support 를 골고루 유지하려는 정책임.
- `12k` : 최종 scene Gaussian 수가 아니라, 한 timestamp 의 9-view rig packet 전체에서 MVS-origin Gaussian 후보를 최대 12,000개 남기기 위한 spawn budget 임. 9-view 기준 view 당 약 1,333개를 목표로 후보 pixel 을 고르고, oversample / MVS / occlusion / sanity filter 이후 최종 후보를 제한함.

### 원본 OTF-style legacy spawn 방식

`legacy` 는 upstream OTF 의 새 Gaussian 생성 방식 중 **pixel spawn policy** 를 가져온 기준선임. 단, 본 실험에서는 pose / rig constraint / same-ts MVS exclusion / safety stack 은 현재 rig-aware pipeline 과 동일하게 두고, density sampling 만 기존 OTF-style 로 둔 것임.

| 단계 | 원본 OTF-style 동작 | 의미 |
|---:|---|---|
| 1 | GT image 에서 Laplacian / LoG 계열 texture response 를 계산해 `init_proba` 를 만듦 | edge / texture 가 강한 pixel 일수록 새 Gaussian 이 생길 확률이 커짐 |
| 2 | 현재 render 에서도 Laplacian response 를 계산해 `penalty` 로 사용 | 이미 현재 Gaussian 들이 sharp 하게 표현한 영역은 새 spawn 확률을 낮춤 |
| 3 | 각 pixel 마다 난수를 뽑아 `rand < init_proba - penalty` 이면 후보로 선택 | top-K 가 아니라 pixel별 Bernoulli 확률 sampling |
| 4 | 선택된 pixel 에 depth 를 붙여 MVS-origin Gaussian 으로 추가 | 선택 pixel 이 바로 point cloud 는 아니고, 이후 MVS / occlusion / sanity filter 를 거쳐 Gaussian 이 됨 |
| 5 | budget cap 없음 | `12k / 24k` 같은 timestamp별 spawn budget 을 두지 않으므로 Gaussian 수가 크게 늘 수 있음 |

따라서 `legacy` 는 uniform random 이 아니라, **texture 가 강하고 아직 충분히 표현되지 않은 pixel 에 더 높은 확률을 주는 확률 sampling** 임.

## 정량 요약

| method | n_seed | holdout PSNR | train PSNR | SSIM | LPIPS | Sim(3) residual | n_gauss | time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | 3 | 19.16 ± 0.15 | 21.05 ± 0.16 | 0.621 | 0.399 | 0.064 ± 0.018 | 1.14M | 175s |
| full 12k | 3 | 17.43 ± 0.40 | 19.27 ± 0.18 | 0.517 | 0.507 | 0.029 ± 0.013 | 121k | 78s |
| random 12k | 1 | 18.96 | 20.38 | 0.574 | 0.445 | 0.0114 | 158k | 78s |
| tile 12k | 1 | 18.96 | 20.40 | 0.575 | 0.446 | 0.0113 | 159k | 79s |
| sph_strat 12k | 1 | 18.98 | 20.40 | 0.576 | 0.445 | 0.0121 | 160k | 81s |
| sph_strat 24k | 3 | 19.22 ± 0.10 | 20.75 ± 0.05 | 0.597 | 0.425 | 0.010 ± 0.003 | 230k | 86s |

- `sph_strat 24k` 는 legacy 대비 holdout PSNR 은 유사하거나 소폭 높고, Gaussian 수와 runtime 은 크게 낮음. 반면 SSIM / LPIPS 는 아직 legacy 가 더 좋으므로, 모든 품질 지표에서 압도한다고 말하면 안 됨.

## 정성 비교

- 각 cell : `render | GT`

### 핵심 비교: legacy vs confidence-only vs rig-spherical support

![confidence vs support](/video_picture/260513/confidence_vs_support_grid.png)

### 5개 방식 비교

![method comparison](/video_picture/260513/method_comparison_grid.png)

정성적으로는 `full 12k` 가 구조적으로 흐려지는 구간이 있고, `sph_strat 24k` 는 전체 구조와 하늘 / 건물 / 나무 trunk 의 정합성이 안정적임. 다만 잔가지, 나뭇잎, 바닥 돌 경계처럼 high-frequency thin detail 에서는 legacy 가 여전히 더 날카로운 경우가 있음.

## 해석

| 관찰 | 의미 |
|---|---|
| `full 12k` 가 가장 약함 | confidence score top-K 만으로는 angular support 를 충분히 보존하지 못함 |
| `random / tile / sph_strat 12k` 가 비슷함 | 현재 sequence 에서는 score 보다 spread 자체가 더 중요하게 작동함 |
| `sph_strat 24k` | support 를 유지한 상태에서 budget 을 늘리면 PSNR / n_gauss / runtime 균형이 좋아짐 |
| SSIM / LPIPS 는 legacy 우세 | fine detail 과 perceptual sharpness 는 아직 legacy 의 많은 Gaussian 이 유리함 |

## 주장 가능한 것과 아닌 것

| 구분 | 보고 가능 | 피해야 할 표현 |
|---|---|---|
| Rig geometry | same-ts sibling 은 depth source 가 아니라 homography / coverage source 로 사용해야 함 | same-ts multi-view depth supervision |
| Proposal | observed rig-spherical support 를 유지하는 proposal 이 현재 sequence 에서 가장 안정적임 | 360도 전체 coverage 보장 |
| Pose | timestamp-shared rig pose constraint 로 view 간 독립 drift 를 줄임 | drift-free / global consistency |
| Stability guard | artifact prune / hard-phys / rotation guard 는 outlier 방지용 | main method contribution |

## 아직 해결하지 못한 것
| 항목 | 목적 |
|---|---|
| rig reboot / sliding-window BA | 전체적인 drift를 해결할 방안에 대한 고찰 |


## Appendix A. Confidence score baseline

`full 12k` 는 제안 method 가 아니라, "confidence score 가 높은 pixel 을 고르면 충분한가?" 를 확인하기 위한 비교군.  
구현상 score 는 render residual, LoG texture response, depth reliability, coverage 부족 신호를 조합함.

```text
score(u) = depth_confidence(u)
         * coverage_need(u)
         * (w_error * residual(u) + w_freq * LoG(u))
```

- `residual` : 현재 render 와 GT image 의 차이
- `LoG` : texture / edge response,
- `depth_confidence`, `coverage_need` : 후보가 depth 및 coverage 관점에서 얼마나 쓸 만한지를 나타내는 heuristic term.
