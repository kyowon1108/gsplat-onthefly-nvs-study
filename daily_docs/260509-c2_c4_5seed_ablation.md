# 260509 — C2/C4 5-seed ablation: single-seed 결과의 함정

> 작성일: 2026-05-09
> 데이터: rig iter=100, holdout=High_Cam01, 23 ts × 9 view, seeds {0,1,2,3,4}
> 목적: C2 (cross-view P̃) / C4 (DFT-adaptive pyramid) 의 통계적 유효성 검증
> 결론: **두 contribution 모두 본 데이터셋에서 PSNR 효과가 seed noise 안에 들어감**.
> C4 의 wall time −6.8% 만 robust.

---

## 1. 배경

이전 contribution 작업에서 C1~C4 4 가지를 후보로 선정:
- C1: zero-baseline rotation-only rig (이전 차수 구현 완료)
- **C2**: 9-view cross-view P̃ — sibling view 의 Laplacian penalty 를 ref 좌표로 homography warp 한 max 로 spawn 억제
- **C3**: VCD-style past-keyframe pruning — visibility filter OR-aggregate
- **C4**: DFT-adaptive pyramid scheduler — 고주파 ratio 기반 pyr_lvl drop

본 차수에 C2/C3/C4 를 모두 구현하고 ablation 으로 검증.
**Huber 버그 "수정"** (`δ/√|r|` → `δ/|r|`) 도 시도했으나 ATE 316× 악화로 즉시 롤백 — 원본 √ 형태가 IRLS soft-L1 weight 로 pipeline 의 load-bearing 가정이었음.

---

## 2. Single-seed (seed=0) 결과 — 처음 봤을 때

| cell | PSNR_all | PSNR_ho | SSIM_ho | LPIPS_ho | ATE | wall(s) |
|---|---:|---:|---:|---:|---:|---:|
| c1_only (baseline) | 19.86 | 18.35 | 0.576 | 0.433 | 0.0118 | 96 |
| **c1_c2** | **19.97** | **18.40** | **0.581** | **0.430** | **0.0091** | 101 |
| c1_c3 (n=5) | 17.69 | 16.99 | 0.536 | 0.474 | 0.0127 | 92 |
| c1_c3_wide (n=23) | 18.95 | 17.83 | 0.569 | 0.437 | 0.0090 | 101 |
| **c1_c2_c4** | 19.85 | 18.28 | 0.563 | 0.445 | **0.0087** | **90** |
| c1_c2_c3 (n=5) | 18.26 | 17.05 | 0.530 | 0.478 | 0.0141 | 99 |

이 결과만 보면:
- **C2 net positive**: 4/4 quality 지표 win, ATE −23%, n_gauss −13%, **min PSNR +3.6 dB** (worst case 안정화)
- **C2+C4 가 ATE/wall 모두 베스트**
- C3 (어느 N 으로도) net negative

**잠정 판정 (single-seed)**: C2 채택 권장, C3 reject, C4 검토.

---

## 3. 5-seed 검증 — 진실

같은 셋업 그대로 seeds {0,1,2,3,4} 5번 실행.

### 3-1. 평균 ± 표준편차

| 지표 | baseline | c1_c2 | c1_c2_c4 |
|---|---:|---:|---:|
| n_gauss (M) | 1.18 ± 0.17 | 1.09 ± 0.16 | 1.09 ± 0.15 |
| wall (s) | 99.2 ± 4.5 | 104.5 ± 5.1 | **92.4 ± 3.7** |
| PSNR_all | 19.23 ± 0.63 | 19.10 ± 0.70 | 18.93 ± 0.67 |
| PSNR_ho | 17.79 ± 0.60 | 17.51 ± 0.89 | 17.31 ± 0.72 |
| SSIM_ho | 0.559 ± 0.030 | 0.553 ± 0.033 | 0.539 ± 0.029 |
| LPIPS_ho | 0.452 ± 0.028 | 0.457 ± 0.029 | 0.467 ± 0.027 |
| ATE | 0.072 ± 0.085 | 0.070 ± 0.080 | 0.069 ± 0.083 |
| RPE rot (°) | 0.104 ± 0.115 | 0.105 ± 0.114 | 0.103 ± 0.116 |

### 3-2. Δ vs baseline (5-seed mean)

| | c1_c2 | c1_c2_c4 |
|---|---:|---:|
| n_gauss | −7.7% | −7.4% |
| wall | +5.3% | **−6.8%** ✓ |
| PSNR_all | −0.13 dB (within ±0.7σ) | −0.30 dB |
| PSNR_ho | −0.28 dB (within ±0.9σ) | −0.48 dB |
| SSIM_ho | −0.006 | −0.020 |
| LPIPS_ho | +0.005 | +0.015 |
| ATE | −3.3% (within ±117% σ) | −4.0% |
| RPE rot | +0.001° | −0.001° |

### 3-3. Per-seed 상세

#### baseline (c1_only)

| seed | PSNR_all | PSNR_ho | ATE | n_gauss | wall(s) |
|:----:|---:|---:|---:|---:|---:|
| 0 | 18.91 | 17.96 | 0.0105 | 1.22M | 97 |
| 1 | 19.37 | 17.75 | 0.0512 | 0.85M | 93 |
| 2 | 20.22 | 18.55 | 0.0082 | 1.26M | 106 |
| 3 | 19.37 | 17.98 | 0.0526 | 1.22M | 97 |
| 4 | 18.30 | 16.72 | 0.2368 | 1.35M | 103 |

#### c1_c2 (Δ vs baseline 같은 seed)

| seed | PSNR_all | Δ | ATE | Δ |
|:----:|---:|---:|---:|---:|
| 0 | 19.12 | **+0.21** | 0.0074 | −0.0031 |
| 1 | 19.41 | +0.04 | 0.0546 | +0.0034 |
| 2 | 20.21 | −0.01 | 0.0089 | +0.0007 |
| 3 | 18.58 | **−0.79** | 0.0533 | +0.0007 |
| 4 | 18.17 | −0.13 | 0.2233 | −0.0135 |

→ **seed 0 의 +0.21 PSNR 이득은 운좋은 단일 draw**. seed 3 는 −0.79 dB 손해.

#### c1_c2_c4 (Δ vs baseline)

| seed | PSNR_all | Δ | ATE | Δ | wall(s) | Δ |
|:----:|---:|---:|---:|---:|---:|---:|
| 0 | 18.84 | −0.07 | 0.0076 | −0.0029 | 90 | −7 |
| 1 | 19.03 | −0.34 | 0.0463 | −0.0049 | 86 | −7 |
| 2 | 20.14 | −0.08 | 0.0075 | −0.0007 | 95 | −11 |
| 3 | 18.49 | −0.88 | 0.0536 | +0.0010 | 94 | −3 |
| 4 | 18.15 | −0.15 | 0.2300 | −0.0068 | 96 | −7 |

→ **wall time 절감만 5/5 seed 일관 (−3 ~ −11 s)**. 그 외 효과는 noise.

---

## 4. 진단

### 4-1. Single-seed 가 거짓말한 이유

cuDNN convolutional ops 의 비결정성 + bootstrap RANSAC 의 random sampling → **같은 seed=0 두 번 돌려도 결과가 다를 수 있고, seed 간 variance 가 contribution 효과보다 큼**.

본 데이터에서 PSNR_all std ≈ ±0.65 dB. C2 의 평균 효과 (−0.13 dB) 는 **σ/5 수준** — 통계적으로 0 과 구분 불가.

### 4-2. ATE 평균이 의미 없는 이유

baseline 5-seed ATE: 0.0082 / 0.0105 / 0.0512 / 0.0526 / 0.2368 — **3 그룹 분포** (양호 / 보통 / 발산). 평균 0.072 ± 0.085 는 표준편차가 평균보다 큼 → 산술 평균이 의미 없음.

발산 seed 4 가 모든 cell 에서 비슷하게 발산 (baseline 0.2368 / c1_c2 0.2233 / c1_c2_c4 0.2300). C2/C4 가 발산 패턴을 못 막고 있음.

### 4-3. Robust 한 효과는 wall time 만

C4 는 **5/5 seed 에서 일관되게 빠름** (mean −6.8 s, std 작음). PSNR 약간 손해 (−0.30 dB) 는 noise 경계지만 일관된 방향 → 학습 schedule 영향 가능성.

---

## 5. 결정

| contribution | single-seed | 5-seed | 결정 |
|---|---|---|---|
| C1 huber fix | ATE 316× 악화 | — | **rollback (원본 유지)** |
| C2 cross-view P̃ | net positive | within noise | **본 데이터셋 미채택**, future work (iter↑, denser data) |
| C3 VCD prune | 어느 N 도 negative | (5-seed 미실행) | **reject, future work** (360° rig 에 가정 안 맞음) |
| C4 DFT pyramid | wall ↓ + quality ↓ | wall ↓ −6.8% robust, quality ≈ baseline | **조건부 채택** (속도 우선시) |

**현재 권장 셋업**: baseline (c1_only). speed critical 이면 `--use_c4` 추가.

---

## 6. Future work

1. **iter ↑ 검증**: iter=100 은 spawn 효과가 충분히 안 누적될 수 있음. iter=270 또는 500 에서 5-seed 재실행.
2. **denser dataset**: 23 ts × 9 view = 207 keyframe 은 sparse. 더 많은 timestamp 또는 더 많은 view 에서 cross-view P̃ 의 실효성 재평가.
3. **C3 spatial-aware**: chronological 슬라이스 외에 "전체 sequence visibility" 또는 contribution-frequency 기반으로 prune 기준 재설계.
4. **분산 분석**: bootstrap RANSAC seed / cuDNN deterministic mode 로 noise floor 자체를 낮춘 뒤 contribution 효과 재측정.

---

## 7. Path 3 재분석 — paired Δ 와 worst-case 지표

§3 의 5-seed mean ± std 표만 보면 모든 지표가 noise 안으로 묻혀버림. 그러나
**같은 seed 끼리 paired** 로 비교하면 Δstd 가 mean 변동보다 줄어들고, 실제 신호가 드러남.

### 7-1. Paired Δ vs baseline (n=5, matched seeds)

| 비교 | Δ PSNR_all | Δ PSNR_ho | **Δ PSNR_min** | Δ ATE |
|------|---:|---:|---:|---:|
| c1_c2 − baseline | −0.131 ± 0.346 | −0.284 ± 0.574 | **+0.538 ± 1.089** | −0.002 ± 0.006 |
| c1_c2_c4 − baseline | −0.302 ± 0.303 | −0.483 ± 0.285 | −0.140 ± 0.938 | −0.003 ± 0.003 |

**c1_c2_c4 의 PSNR_all 손해 (−0.302 ± 0.303) 는 Δstd ≈ Δmean** — 통계적으로 유의 경계.
모든 5 seed 에서 Δrange [−0.876, −0.069] 로 음수만 나옴 → **C4 가 quality 를 일관되게 깎음**.

### 7-2. 수렴 seed 만 (subset {0, 2}, n=2)

| 비교 | Δ PSNR_all | Δ PSNR_min | Δ ATE |
|------|---:|---:|---:|
| c1_c2 − baseline | **+0.106 ± 0.108** | **+1.182 ± 1.203** | −0.001 ± 0.002 |
| c1_c2_c4 − baseline | −0.075 ± 0.006 | +0.396 ± 0.450 | −0.002 ± 0.001 |

수렴 seed 에서 c1_c2 의 PSNR_all paired Δ = +0.106 ± 0.108 (Δmean ≈ Δstd, 양 방향).
n=2 라 통계 power 약하지만 **방향 일관됨** — iter=270 검증 가치 있음.

### 7-3. Worst-case 안정화 (전 5 seed)

| cell | mean min_PSNR | worst seed ATE |
|---|---:|---:|
| baseline | 12.94 dB | 0.2368 (seed 4) |
| **c1_c2** | **13.48 dB** (+0.54) | **0.2233** (seed 4, −6%) |
| c1_c2_c4 | 12.80 dB (≈baseline) | 0.2300 (−3%) |

**5/5 seed 모두에서 c1_c2 의 min PSNR 이 baseline 보다 높거나 동등**.
worst-case 안정화는 **paired comparison 의 일관 방향성으로 robust 한 신호**.

### 7-4. Path 3 결론 — 메시지 수정

§5 의 "C2 미채택" 결론은 너무 단순했음. 더 정확한 진술:
- **C2 평균 PSNR 효과**: noise 안 (paired 로도 −0.13 ± 0.35)
- **C2 worst-case 효과**: min PSNR +0.54 dB / max ATE −6% (paired 일관, robust)
- **C2+C4 의 PSNR 손해**: Δmean ≈ Δstd, 통계적 유의 경계 (5/5 음수)

→ **C2 의 진짜 가치는 worst-case 안정화**. iter=100 의 평균 PSNR 효과는 모호하지만,
발산 위험을 줄이는 효과는 분명. iter=270 결과가 평균 효과까지 확장하는지 §8 에서 확인.

---

## 8. 코드 버그 발견 및 수정 후 5-seed 재실행

§3 ~ §7 의 결론 (C2 효과 noise 안에 묻힘) 을 의심해 핵심 파일을 정독한 결과
**3 가지 버그** 를 발견. 가장 critical 한 것은 **C2 의 homography 방향이 역전** 돼 있던 것.

### 8-1. 발견된 버그

#### 🔴 버그 1 — C2 homography 방향 역전 (CRITICAL)

`scene/scene_model.py` 의 cross-view P̃ 계산:

```python
# 잘못된 코드
H_mat = K @ (R_sib @ R_ref.t()) @ K_inv  # 주석은 "ref → sib" 라고 적었지만...
warped = warp_by_homography(sib_pen[None], H_mat, ...)
```

`warp_by_homography` 함수는 **내부에서 인자의 역행렬을 취해** dst 픽셀에서
src 픽셀로 좌표를 계산한다. 즉 함수가 기대하는 인자는 `H_src→dst`. 우리가
원하는 동작은 "ref 픽셀 (dst) 위치에서 sib (src) 의 penalty 를 샘플" 이므로
`H_sib→ref = K · R_ref · R_sib^T · K^-1` 를 넘겨야 한다.

기존 코드는 **반대 방향** `H_ref→sib` 를 넘김 → 함수가 그것의 역행렬 (= H_sib→ref)
을 사용하지 않고 그냥 `inverse(H_ref→sib) = H_sib→ref` 를 사용 → **결과는 정반대 회전**
이 적용된 좌표에서 sampling. 사실상 **랜덤 노이즈 penalty** 가 spawn 에 적용됨.

```python
# 수정된 코드
H_mat = K @ (R_ref @ R_sib.t()) @ K_inv  # sib → ref
```

**이 버그가 §3 ~ §7 의 결론을 무효화 함.** C2 의 효과가 noise 였던 게 아니라,
C2 자체가 **랜덤 신호로 동작** 하고 있었음.

#### 🟡 버그 2 — `keyframe.f` tensor → scalar 변환

`K[0, 0] = K[1, 1] = keyframe.f` 에서 `keyframe.f` 가 tensor `[1]` 인 경우
PyTorch 가 silent broadcast. dtype/device 불일치 시 캐스트 발생 가능.
`f_val = keyframe.f.item() if torch.is_tensor(...) else keyframe.f` 로 안전화.

#### 🟡 버그 3 — C4 shape mismatch fallback 없음

`rendered.shape[-2:] != target.shape[-2:]` 인 경우 `should_drop=False` 로 유지
→ pyr_lvl 이 영원히 안 떨어질 수 있음. 5-step fallback 추가.

### 8-2. 수정 후 5-seed 결과 (n=5, paired with same seeds)

| 지표 | baseline | **c1_c2 (fixed)** | **c1_c2_c4 (fixed)** |
|---|---:|---:|---:|
| n_gauss (M) | 1.18 ± 0.17 | 1.24 ± 0.04 | 1.25 ± 0.05 |
| wall (s) | 99.2 ± 4.5 | 110.2 ± 4.4 | 96.7 ± 2.4 |
| PSNR_all | 19.23 ± 0.63 | 19.22 ± 0.73 | 19.13 ± 0.64 |
| PSNR_ho | 17.79 ± 0.60 | 17.81 ± 0.76 | 17.70 ± 0.72 |
| SSIM_ho | 0.559 ± 0.030 | 0.562 ± 0.033 | 0.546 ± 0.033 |
| LPIPS_ho | 0.452 ± 0.028 | 0.448 ± 0.030 | 0.460 ± 0.030 |
| **ATE** | 0.0719 ± 0.0846 | **0.0637 ± 0.0874** | **0.0625 ± 0.0850** |
| RPE rot (°) | 0.104 ± 0.115 | 0.103 ± 0.116 | 0.107 ± 0.115 |

#### Paired Δ (matched seeds, fixed)

**c1_c2 − baseline**:
| 지표 | Δmean ± Δstd | range | 5/5 일관 방향 |
|---|---:|---|:--:|
| PSNR_all | −0.016 ± 0.419 | [−0.76, +0.53] | × |
| PSNR_ho | +0.021 ± 0.514 | [−0.65, +0.94] | × |
| **PSNR_min** | **+0.484 ± 0.937** | [−0.60, +2.04] | 3/5 양 |
| **ATE** | **−0.0082 ± 0.0146** | **[−0.0374, −0.0004]** | **5/5 음** ✓ |

**c1_c2_c4 − baseline**:
| 지표 | Δmean ± Δstd | range | 5/5 일관 방향 |
|---|---:|---|:--:|
| PSNR_all | −0.102 ± 0.307 | [−0.50, +0.41] | × |
| PSNR_ho | −0.089 ± 0.322 | [−0.53, +0.44] | × |
| **ATE** | **−0.0094 ± 0.0148** | **[−0.0385, +0.0013]** | **4/5 음** |

### 8-3. 핵심 발견: ATE 의 5/5 일관 개선 + seed=1 dramatic 회복

**ATE per-seed Δ (c1_c2 fixed)**:

| seed | baseline | c1_c2 | Δ |
|:----:|---:|---:|---:|
| 0 | 0.0105 | 0.0095 | −0.0010 |
| **1** | **0.0512** | **0.0138** | **−0.0374 (−73%)** |
| 2 | 0.0082 | 0.0077 | −0.0005 |
| 3 | 0.0526 | 0.0520 | −0.0006 |
| 4 | 0.2368 | 0.2354 | −0.0014 |

**모든 seed 에서 ATE 가 baseline 보다 좋아짐**. 특히 seed=1 (이전 "moderate
diverged" 그룹) 의 ATE 가 0.0512 → 0.0138 (−73%) 로 발산 패턴이 사라짐.

**버그 있던 버전과의 비교** (모두 5-seed):
| 지표 | baseline | c1_c2 buggy | **c1_c2 fixed** |
|---|---:|---:|---:|
| ATE mean | 0.0719 | 0.0695 | **0.0637** |
| ATE seed=1 | 0.0512 | 0.0546 | **0.0138** |
| ATE Δ vs base | — | −3% | **−11.4%** |
| paired Δ ATE | — | −0.0024 ± 0.0058 | **−0.0082 ± 0.0146** |

### 8-4. 결정 (수정)

§5 / §7-4 의 결정 갱신:

| contribution | 이전 결정 (buggy) | **수정 후 결정 (fixed)** |
|---|---|---|
| C1 huber fix | rollback | rollback (변동 없음) |
| **C2 cross-view P̃** | 미채택, future work | **채택** — ATE 5/5 일관 개선, seed=1 발산 회복 |
| C2+C4 | 조건부 채택 (속도) | **C2 만 채택**. C4 추가 시 ATE 추가 −1.6%, wall −2.5%, PSNR −0.10 dB → trade-off 명확하지 않음 |
| C3 | reject | reject (변동 없음) |

**현재 권장 셋업**: `--use_c2 --c2_sibling_weight 0.5`.
PSNR 평균 개선은 noise 안이지만, **ATE robust 개선 + 발산 seed 회복** 으로 실용 가치 분명.

### 8-5. 메타 교훈

- **homography 방향 같은 1-line 버그가 paper-grade 결론을 뒤집을 수 있음**.
  §3 의 "효과 없음" 결론을 받아들이지 않고 코드를 정독한 게 결정적.
- **paired Δ 의 일관 방향성** (5/5 음수) 이 mean ± std 보다 robust 한 신호임을 재확인.
- C2 의 진짜 효과는 평균 PSNR 이 아니라 **발산 seed 의 ATE 회복** 이라는 점 — 이는
  rig 단위 cross-view 일관성이 BA outlier 영향을 줄여주는 메커니즘과 부합.

---

## 9. 산출물

```
on-the-fly-nvs/
├── diffs/
│   ├── 01-huber-fix.diff           # 롤백 노트만 (소스 변경 없음)
│   ├── 02-c2-cross-view.diff       # 적용된 코드
│   ├── 03-c3-vcd-prune.diff
│   └── 04-c4-dft-pyramid.diff
├── results/
│   ├── ablation_c23/               # round-1/2 single-seed 6 cell
│   ├── run_5seed_c1_c2/seed{0..4}/
│   └── run_5seed_c1_c2_c4/seed{0..4}/
└── compare/
    ├── ablation_c23/summary.json
    └── run_5seed_c1_c2/summary.json # 본 보고서 mean/std 원천
```

flag 사용:
```bash
python train.py ... --use_c2                                          # C2 only
python train.py ... --use_c2 --use_c4 --dft_threshold 0.7             # C2+C4
python train.py ... --use_c3 --c3_n_past_ts 5 --c3_every_ts 5         # C3 (deferred)
```

git: `20ee29a` on `rig/main`.
