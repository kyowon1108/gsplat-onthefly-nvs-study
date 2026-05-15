# 260515 - OTF rig 품질 gap 분해 중간 경과

- 데이터셋: Insta360 X5 EQR -> 9 virtual pinhole view x 23 timestamp = 207 frame.
- 목적: native OTF rig 결과가 batch 3DGS 대비 낮게 나오는 원인을 **spawn / past-keyframe optimization / pose / point initialization** 으로 나누어 확인함.
- 2026-05-15 기준 진행 경과를 정리한 중간 보고.

## 진행 방식 요약

기존에 혼동이 있었던 5-way 비교 표현을 먼저 정정하고, native OTF 품질 저하의 원인을 분해하는 방향으로 실험을 진행함.

현재 기준 baseline 은 **legacy Bernoulli OTF native** 임. 즉, 이전에 실험했던 RASP / sph_strat / random / tile selection 을 main method 로 두지 않고, 원본 OTF 계열의 spawn 흐름 위에서 원인을 다시 확인하는 방향임.

본 문서의 metric 표기는 다음 기준으로 사용함.

| 용어 | 의미 |
|---|---|
| holdout PSNR | `High_Cam01` holdout-like view 기준 평가 |
| post-hoc PSNR | 학습 종료 후 207 frame 전체를 다시 render 하여 계산한 reconstruction metric |
| batch 3DGS PSNR | 30k 3DGS reconstruction / train metric. unseen trajectory generalization 으로 해석하지 않음 |

## 1. 기존 5-way 비교 표현 정정

이전 문서에서 "OTF points" 라고 표현했던 부분은 부정확했음. 현재 OTF export 는 `cameras.bin` / `images.bin` 만 저장하고, `points3D.bin` 은 비어 있음. 따라서 OTF 결과에서 직접 나온 COLMAP-style point cloud 를 썼다고 말하면 안 됨.

| 표현 | 정확한 의미 | 비고 |
|---|---|---|
| OTF pose | native OTF 가 추정한 camera pose 를 COLMAP frame 으로 Sim(3) 정렬한 것 | pose-only export |
| OTF-pose re-triangulated points | OTF pose 를 고정하고 COLMAP database / matches 로 다시 triangulate 한 sparse points | COLMAP feature track 기반 |
| OTF Gaussian-center init | OTF 가 학습한 Gaussian center 를 `points3D.ply` 형태로 변환한 3DGS 초기점 | COLMAP sparse reconstruction 은 아님 |

따라서 오늘의 batch 3DGS 비교는 "OTF points" 검증이 아니라, **OTF pose** 와 **OTF Gaussian-center initialization** 이 batch 3DGS 에서 얼마나 회복 가능한지를 보는 실험으로 정리함.

## 2. E0 / E1 / E2 / E3: streaming gap 분해

### 비교군 정의

| Cell | 설정 | 검증 질문 |
|---|---|---|
| E0 | legacy Bernoulli OTF native, `init_proba_scaler=2` | 현재 streaming baseline |
| E1 | Bernoulli intensity 증가, `init_proba_scaler=4/8` | 단순히 더 많이 spawn 하면 품질이 회복되는가 |
| E2-a | past-keyframe sliding-window replay loss 추가 | 과거 keyframe 을 다시 최적화하면 품질이 회복되는가 |
| E2-b | 최근 keyframe 만 replay pool 로 bias | 최근 view 중심으로 학습하면 도움이 되는가 |
| E3 | E2-a + E1 scaler 증가 | spawn 증가와 replay 가 additive 하게 작동하는가 |

여기서 E1 은 RASP 식 top-K spawn budget 실험이 아님. legacy Bernoulli 확률 강도를 키워 accepted spawn 수가 늘어날 때 품질이 같이 오르는지 확인한 실험임.

교수님 지시서의 E1 은 당시 260512 문서의 RASP / sph_strat 24k setting 을 기준으로 spawn budget 을 늘리는 형태였음. 다만 이번 정정 후 E0 baseline 을 legacy Bernoulli OTF native 로 다시 잡았기 때문에, 본 문서의 E1 은 top-K budget K 를 늘리는 실험이 아니라 Bernoulli sampling intensity 를 높여 accepted spawn 수가 실제로 증가하는지 보는 corrected E1-proxy 로 수행함.

### E1 결과

| config | init_proba_scaler | mean n_total_new | final n_gauss | holdout PSNR | post-hoc PSNR | SSIM | LPIPS | runtime | crash |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| E0 | 2 | 29,912 | 937k | 19.23 | 20.93 | 0.655 | 0.387 | 156s | no |
| E1a | 4 | 52,389 | 1,258k | 19.11 | 20.81 | 0.652 | 0.390 | 195s | no |
| E1b | 8 | 81,558 | 1,631k | 18.56 | 20.39 | 0.633 | 0.406 | 243s | no |

accepted spawn 수는 약 2.7배까지 증가했지만, PSNR 은 회복되지 않고 오히려 낮아짐. 따라서 현재 sequence 에서는 단순히 Gaussian 수를 많이 늘리는 것만으로 batch 3DGS 와의 gap 을 줄이기 어렵다고 판단함.

### E2 / E3 결과

| config | knob | n_total_new | n_gauss | holdout PSNR | post-hoc PSNR | SSIM | LPIPS | n_opt_total | runtime | crash |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| E0 | scaler=2 | 29,912 | 937k | 19.23 | 20.93 | 0.655 | 0.387 | 3,949 | 156s | no |
| E2-a w=5 | replay loss window=5 | 28,996 | 951k | 19.60 | 21.41 | 0.678 | 0.371 | 8,247 | 236s | no |
| E2-a w=10 | replay loss window=10 | 29,549 | 978k | 19.62 | 21.34 | 0.678 | 0.370 | 8,257 | 243s | no |
| E2-a w=15 | replay loss window=15 | 29,255 | 937k | 19.61 | 21.30 | 0.674 | 0.374 | 8,250 | 243s | no |
| E2-b w=5 | replay-bias only | 27,843 | 927k | 16.54 | 18.31 | 0.516 | 0.449 | 3,933 | 152s | no |
| E3 | E2-a w=10 + scaler=4 | 51,677 | 1,307k | 19.40 | 21.18 | 0.672 | 0.374 | 8,257 | 309s | no |

E2-a 는 full sliding-window BA 가 아니라, step 수는 270으로 유지한 채 각 optimization step 에 window 내 과거 train keyframe 1개를 stochastic replay loss 로 추가한 lightweight approximation 임. 따라서 아래 결과는 "window BA 전체 효과"가 아니라, past-view photometric replay 를 추가했을 때의 1차 효과로 해석함.

E2-a 는 E0 대비 약 +0.4~0.5 dB 개선을 보임. 따라서 past-keyframe replay 는 실제로 도움이 되는 lever 임. 다만 window 를 5에서 10, 15로 늘려도 추가 개선은 거의 없었고, E3 에서 spawn 증가와 결합해도 E2-a 단독보다 좋아지지 않았음.

현재 해석은 다음과 같음.

| 관찰 | 해석 |
|---|---|
| spawn intensity 증가만으로 PSNR 회복 없음 | 단순 spawn 수 부족이 dominant 원인이라고 보기 어려움 |
| replay loss 는 +0.4~0.5 dB 개선 | 과거 keyframe 재최적화는 도움됨 |
| replay window 5 이후 거의 flat | 멀리까지 보는 것보다 추가 photometric update 자체가 중요함 |
| replay-bias only 는 크게 악화 | 최근 keyframe 만 보면 오래된 view 가 충분히 검증되지 못함 |
| E3 는 additive 하지 않음 | spawn 증가와 일반 replay 를 단순 결합하는 방식은 충분하지 않음 |

## 3. Pose / point initialization batch 3DGS audit

### 목적

OTF native 품질 저하가 pose 자체의 실패인지, OTF 가 만든 Gaussian geometry 의 실패인지, 아니면 streaming-time optimization 문제인지 분리하기 위해 30k batch 3DGS 비교를 진행함.

사용한 OTF source 는 legacy Bernoulli OTF native, iter=270, seed=0 결과임.

Sim(3) alignment 결과는 207 / 207 image pair 기준 RMSE 0.0209, scale 9.96 으로 확인됨.

### 비교군 정의

| variant | pose | init points | 의미 |
|---|---|---|---|
| A | COLMAP rig pose | COLMAP mapper sparse points | batch 3DGS 기준선 |
| D | Sim(3)-aligned OTF pose | COLMAP mapper sparse points | pose 만 OTF 로 바꿨을 때 영향 |
| C-matched | COLMAP rig pose | OTF Gaussian-center pseudo PLY, count-matched | point init 만 OTF 로 바꿨을 때 영향 |
| B-matched | Sim(3)-aligned OTF pose | OTF Gaussian-center pseudo PLY, count-matched | OTF pose + OTF Gaussian init 결합 영향 |
| C-full | COLMAP rig pose | full OTF Gaussian-center pseudo PLY | dense OTF warm-start 영향 |
| B-full | Sim(3)-aligned OTF pose | full OTF Gaussian-center pseudo PLY | OTF pose + dense OTF warm-start 영향 |

### 현재 완료 결과

| # | variant | n_init | iter 7,000 PSNR | iter 30,000 PSNR | delta vs A @30k |
|---:|---|---:|---:|---:|---:|
| 1 | A: COLMAP pose x COLMAP points | 41,678 | 22.89 | 26.49 | - |
| 2 | C-matched: COLMAP pose x OTF Gaussian init | 41,678 | 22.86 | 26.41 | -0.08 |
| 3 | D: OTF pose x COLMAP points | 41,678 | 22.46 | 26.03 | -0.46 |
| 4 | B-matched: OTF pose x OTF Gaussian init | 41,678 | 22.31 | 26.04 | -0.45 |

위 PSNR 은 207 frame reconstruction / train metric 기준임. 또한 B/C-matched 의 OTF Gaussian init 은 OTF Gaussian 의 **center 위치**를 count-matched sparse initialization 으로 사용한 것임. Scale / opacity / SH 를 포함한 full OTF primitive quality 는 C-full / B-full 결과로 별도 확인 중임.

### 현재 해석

| 비교 | 결과 | 해석 |
|---|---:|---|
| A -> C-matched | -0.08 dB | OTF Gaussian center 위치 분포는 batch 3DGS init 으로 거의 손색 없음 |
| A -> D | -0.46 dB | OTF pose 는 약간의 손실을 만들지만, native OTF 의 약 6 dB gap 을 설명할 정도는 아님 |
| A -> B-matched | -0.45 dB | OTF pose + OTF init 을 같이 써도 손실은 D 와 거의 같음 |
| D vs B-matched | 26.03 vs 26.04 | 같은 OTF pose 에서는 COLMAP sparse 와 OTF Gaussian init 차이가 거의 없음 |

즉, 현재까지 완료된 결과만 보면 OTF Gaussian 의 center 위치 분포는 count-matched sparse initialization 으로 사용할 때 batch 3DGS 수렴에 큰 손실을 주지 않음. OTF pose 도 batch 3DGS 에서는 약 0.45 dB 정도의 손실만 만듦. OTF native 가 약 19~20 dB 대에 머무는 큰 차이는 pose / point initialization 대실패라기보다, streaming 과정에서의 제한된 photometric refinement, selective revisit 부재, primitive lifecycle 정책 쪽으로 좁혀짐.

## 4. 현재 기준 중간 결론

| 원인 후보 | 현재 판정 |
|---|---|
| 단순 spawn 수 부족 | accepted spawn 을 2.7배 늘려도 PSNR 이 오르지 않아 dominant 원인으로 보기 어려움 |
| 일반 past-keyframe replay 부족 | +0.4~0.5 dB 개선이 있어 실제 lever 이지만, gap 전체를 설명하지는 못함 |
| OTF pose 대실패 | batch 3DGS 에서 26.03 dB 까지 수렴하므로 대실패는 아님 |
| OTF Gaussian geometry 실패 | count-matched init 에서 26.41 dB 까지 수렴하므로 큰 실패는 아님 |
| 남은 주요 후보 | streaming-time optimization budget 배분, selective revisit, primitive lifecycle, confidence signal |

따라서 현재 단계에서는 "더 많이 spawn 한다" 보다는, 제한된 streaming budget 안에서 **어떤 keyframe / view / Gaussian 을 다시 최적화하거나 유지할지 결정하는 selective revisit / lifecycle / confidence signal** 쪽을 다음 검증 축으로 두는 것이 타당해 보임.

## 5. 현재 수행 상태

| 요청 항목 | 현재 상태 | 비고 |
|---|---|---|
| 기존 5-way 비교 표현 정정 | 수행 | OTF points 표현을 OTF pose / re-triangulated points / Gaussian-center init 으로 분리 |
| E0 baseline 확인 | 수행 | seed=0 기준 |
| E1 spawn 증가 확인 | 수행 | seed=0 기준, 단순 intensity 증가는 negative |
| E2 sliding-window replay 확인 | 수행 | seed=0 기준, +0.4~0.5 dB |
| E3 결합 확인 | 수행 | seed=0 기준, additive 하지 않음 |
| pose / point initialization 분리 | 일부 수행 | A, D, C-matched, B-matched 완료 |
| 3-seed 반복 | 미수행 | 현재 핵심 결과 대부분 seed=0 diagnostic |
| full OTF warm-start 비교 | 진행 중 | C-full 진행 중, B-full 대기 |
| P0-3 confidence signal prototype | 미수행 | S6 gradient EMA / S7 rendering contribution / S2 cross-view coverage 는 아직 구현 전 |
| P1 우선순위 조정 제안 | 초안 수준 | 현재 결과상 단순 spawn 증가보다 selective revisit / lifecycle 쪽이 후보이나, seed 보강 후 확정 필요 |

## 6. 아직 진행 중인 항목

| 항목 | 상태 | 목적 |
|---|---|---|
| C-full | 진행 중 | COLMAP pose 에 full OTF Gaussian-center warm-start 를 넣었을 때 batch 3DGS 가 얼마나 회복되는지 확인 |
| B-full | 대기 | OTF pose + full OTF Gaussian-center warm-start 결합 영향 확인 |
| E variant | 필요 시 수행 | OTF pose 로 COLMAP matches 를 다시 triangulate 한 sparse points 와 COLMAP sparse points 비교 |
| E0 / E1 / E2 / E3 seed 1,2 | 미수행 | single-seed 착시 제거 |
| matched pose/point audit seed 1,2 | 미수행 | OTF pose / init 결론의 seed robustness 확인 |
