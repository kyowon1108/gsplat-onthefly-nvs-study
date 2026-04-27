# 260427 - pose channel ablation, view 기여도, EQR seam 검증

---

## 1. 문서 목적

- 260413 보고서 (`260413-ontheflynvs_vs_colmap_rig_comparison.md`) 이후 진행된 검증 작업 정리
- pose channel ablation, per-view PnP 기여도, EQR seam-distance × residual 측정 결과 보고
- 260413 보고서의 일부 표현을 측정 기반으로 정밀화함.
  - "BA 동등성" → "trajectory 수준 일치성"
  - "9-view 활용도 100%" → "9 view 모두 참여, 단 effective_weight 분포는 비균등"
  - "직접 증거" → 4-cell ablation 측정값

---

## 2. 실행 환경

| 항목 | 값 |
|---|---|
| GPU | RTX 4060 Ti 16GB |
| Python 환경 | `conda activate onthefly_nvs` |
| 해상도 | 960 × 960 |
| 공통 intrinsics | `fx=fy=cx=cy=480` (고정) |
| Ref view | `High_Cam07` |
| Holdout view | `High_Cam01` (가장자리 view) |
| Keyframe 수 | 23 timestamps × 9 views = 207 images |
| 표준 iter | 100 (development), 500 (best quality) |

---

## Part 1. 코드 변경 요약

### 3. 본 차수 추가된 변경 (commit 단위)

| 구분 | 파일 / 위치 | commit | 변경 목적 |
|---|---|---|---|
| Pose ablation 인프라 | `poses/pose_initializer.py` (refinement env-gate) | `def3962` | `RIG_DISABLE_POSE_REFINE=1` 로 1-step LM refinement 비활성화 가능 |
| PnP stats 누적 | `poses/pose_initializer.py` (per-ts × per-view) | `def3962` | `n_correspondences`, `success`, `n_inliers`, `effective_weight`, mean/std reproj residual |
| Stats dump | `train.py` (env-gate) | `def3962` | `RIG_DUMP_PNP_STATS=path.json` 로 dump |
| 분석 도구 | `tools/analyze_feedback_round1.py` (452 LOC) | `a6561b4` | Stage 1~3 결과 집계, COLMAP Sim(3) 정렬 자동 호출 |
| Figure 도구 | `tools/visualize_feedback_round1.py` | `9f13aa5` | 본 보고서의 ablation figure 3장 (lr_poses, per-view PnP, seam) 생성 |

---

## Part 2. 측정 결과

### 5. 이슈 1: CUDA 라스터라이저 크래쉬 해결

#### 문제

iter ≥ 20 에서 `cudaErrorIllegalAddress` 발생으로 학습이 중단되었음. 초기 진단 시 로그 손실로 정확한 원인 파악이 어려웠음.

#### 근본 원인

`raw_scaling.clamp(max=3.0)` 안전장치가 원인이었던 것으로 진단되었음.

| 메커니즘 | 결과 |
|---|---|
| in-place `clamp(max=3.0)` 적용 | parameter 값 강제 수정 |
| PyTorch Adam optimizer 가 momentum/variance state 를 별도로 갱신 | parameter 수정을 인지하지 못함 |
| Adam state 와 실제 텐서 값의 불일치 | 다음 update 에서 NaN 또는 wild step 발생 |
| 라스터라이저가 invalid coordinate 수신 | `cudaErrorIllegalAddress` |

#### 해결

`raw_scaling.clamp` 제거 (commit `24ac933`).

```python
# 이전:
raw_scaling.clamp_(max=3.0)
# 이후: 제거. xyz clamp ±100만 유지 (Adam state 영향 없는 형태)
```

#### 결과

이전에는 iter 20 부터 학습이 중단되어 본 시스템 학습 자체가 차단되는 blocking 이슈였음. 이번 변경으로 iter=500 까지 안정 동작 확인. 본 보고서의 후속 측정 (§6 ~ §13) 모두 이 변경 이후 가능해진 것임. 안전장치 목적으로 추가되었던 코드가 실제로는 silent failure 의 원인이었음을 실험으로 확인.

---

### 6. 이슈 2: COLMAP과 scale 차이 + Sim(3) 정렬

#### 문제

본 시스템의 BA 결과를 COLMAP rig-constrained 결과와 비교할 때, 두 시스템이 서로 다른 좌표계·스케일을 사용하므로 단순 절대 거리 비교가 의미를 갖지 못함.

#### 원인 — BA의 7-DoF gauge freedom

Bundle Adjustment 는 absolute reference 없이 풀면 7-DoF (Degrees of Freedom, 자유도) 가 남음.

- Scale (1 자유도, 단위)
- Rotation (3 자유도, world frame 회전)
- Translation (3 자유도, world origin)

본 시스템과 COLMAP 이 각자 다른 gauge 에 수렴함.

- 본 시스템: bootstrap 후 "consecutive rig 거리 median = 0.1" 로 정규화
- COLMAP: 자체 gauge (보통 first-pair baseline)

따라서 두 좌표계 간 7-DoF 변환 정렬이 선행되어야 비교가 가능함.

#### 해결 — Umeyama (1991) Sim(3) 정렬

`tools/compare_with_colmap.py` (470 LOC, commit `c42baf1`).

양쪽 trajectory 의 카메라 중심 (`C = -R^T t`) 을 추출한 뒤 Umeyama (1991) 로 7-DoF Sim(3) (s, R, t) 를 추정 (SVD + 반사 보정), 본 시스템 trajectory 에 적용해 정렬한 후 ATE/RPE 를 계산함.

#### 결과 (5-run mean)

| 지표 | 값 | 해석 |
|---|---|---|
| Sim(3) scale | 9.818 ± 4.83e-3 | 본 시스템이 COLMAP 단위로 약 9.8× 작음 |
| ATE RMSE | 0.0121 ± 1.74e-3 | COLMAP scene scale 3.444 의 0.35% |
| RPE rot RMSE | 0.055° ± 4.0e-3° | 인접 timestep 회전 변화 일치 |
| 5-run scale 변동 | 0.05% (relative σ) | BA gauge 가 결정적 |

#### Figure

![sim3_alignment](../video_picture/260427/fig1_alignment.png)

- 좌상: 정렬 전. 변경한 on-the-fly-nvs 약 2 단위, COLMAP 약 22 단위 영역에서 서로 다른 scale·orientation
- 우상: 정렬 후. 두 궤적 거의 일치
- 좌하: per-timestep ATE (5-run mean ± σ band, RMSE 0.0121)
- 우하: per-timestep RPE rot (5-run mean ± σ band, RMSE 0.055°)

![scale_origin](../video_picture/260427/fig2_scale_origin.png)

- 좌: scale 9.81× 의 origin 막대. 변경한 on-the-fly-nvs path 2.228 대 COLMAP path 21.860 (비율 9.81)
- 우: 5-run 분포 boxplot. Sim(3) scale 변동 0.05%, ATE/RPE 변동 7~15%

#### 결과 해석 범위

본 측정은 ref-view trajectory 수준에서 COLMAP rig-constrained 결과와의 높은 일치성을 보임.

측정값에 부합하는 statement:

- 카메라 중심 trajectory shape 일치
- 인접 timestep 회전 변화 일치

측정값이 함의하지 않는 statement:

- BA objective 동일성
- 모든 view 의 reprojection 동일성

따라서 안전한 표현은 trajectory-level high agreement (단일 scene 측정).

---

### 7. 이슈 3: GS 최적화의 pose 보정 (lr_poses ablation)

#### 문제

본 시스템의 photometric optimization 단계가 pose 변수에 어느 정도 영향을 주는지가 명확히 측정되지 않았음. 두 pose 보정 채널의 단독 효과 및 결합 효과를 분리하여 정량화할 필요가 있었음.

분리 측정할 두 채널: refinement (`_refine_rig_pose_miniba` — PnP+Fréchet 결과를 1-step LM 으로 tightening) 와 `lr_poses` (학습 단계의 photometric gradient 가 pose 변수에 흐름).

#### 코드 변경 (commit `def3962`)

`poses/pose_initializer.py:843`:

```python
# RIG_DISABLE_POSE_REFINE=1 short-circuits this for ablation runs.
if (
    hasattr(self, "miniba_incr_rig")
    and os.environ.get("RIG_DISABLE_POSE_REFINE", "0") != "1"
):
    rig_pose = self._refine_rig_pose_miniba(...)
```

`--lr_poses` 는 기존 args, value 0 으로 disable.

#### 실험 절차 — 4-cell matrix

| run | env `RIG_DISABLE_POSE_REFINE` | `--lr_poses` |
|---|---|---|
| A | (unset) | 1e-4 |
| B | (unset) | 0 |
| C | 1 | 1e-4 |
| D | 1 | 0 |

다른 인자 동일: `--use_rig --fix_focal --rig_holdout_view High_Cam01 --num_iterations 100`. 단일 시드, single scene.

#### 결과

![lr_poses_ablation](../video_picture/260427/fig_3_5_1_lr_poses_ablation.png)

위 figure 는 1×3 bar chart 구성 (holdout PSNR / ATE / RPE rot).

| run | `lr_poses` | refine | holdout PSNR | ATE (m) | RPE rot (°) |
|---|---|---|---:|---:|---:|
| A | 1e-4 | on | 17.46 | 0.0422 | 0.059 |
| B | 0 | on | 17.23 | 0.0232 | 0.061 |
| C | 1e-4 | off | 17.51 | 0.0400 | 0.094 |
| D | 0 | off | 16.31 | 0.0841 | 0.110 |

Pairwise 차이:

| 비교 | 변경 채널 | Δ holdout PSNR | Δ ATE | Δ RPE rot |
|---|---|---:|---:|---:|
| A − B | `lr_poses` 1e-4 vs 0 | +0.23 | +0.019 | -0.002 |
| A − C | refinement on vs off | -0.04 | +0.002 | -0.035 |
| A − D | 둘 다 vs 둘 다 끔 | +1.16 | -0.042 | -0.052 |

#### 결과 해석

- `lr_poses` 단독 효과 (A−B = +0.23 dB): GS 최적화가 pose 변수에 영향을 미친다는 점이 측정값으로 확인됨. 단 ATE 가 0.0232 → 0.0422 로 증가하여, photometric optimum 방향으로 trajectory 를 이동시키는 효과 — BA optimum (= COLMAP-aligned trajectory) 과 다른 위치임. rendering quality 와 COLMAP-aligned trajectory 라는 두 목적함수가 일치하지 않음을 의미함.
- Refinement 단독 효과 (A−C): holdout PSNR 변화 거의 없음 (-0.04 dB) 이지만 RPE rot 0.035° 감소 — refinement 는 rendering quality 에 직접 기여하기보다 trajectory tightness 에 작용함.
- 두 채널 결합 효과 (A−D = +1.16 dB): A−B 와 A−C 의 단순 합 (+0.19) 과 일치하지 않음. 두 채널이 독립적이지 않으며 결합 시 단독 효과 합 이상의 영향이 측정됨.

#### 한계

- 단일 시드, 단일 scene, iter=100.
- 분산 미측정. iter=500 에서의 동일 ablation 미수행.

---

### 8. 추가 개선: 9-view Gaussian spawn

#### 문제

Bootstrap 및 incremental 단계에서 9개 view 중 ref view 1개만 `add_new_gaussians()` 를 호출하는 구조였음. 나머지 8개 view 는 photometric loss 단계에만 참여하고 spawn 단계에서는 활용되지 않았음. 이로 인해 입력 데이터의 약 89% (8/9 view) 가 Gaussian 시드 단계에서 사용되지 않는 상태였음.

#### 해결 — Patch 1 (commit `8e3f667`)

`train.py` 의 bootstrap 및 incremental 양쪽에서 9개 view 모두에 대해 spawn 을 호출하도록 변경.

```python
# Bootstrap (이전: ref view만 → 변경: 9 view 모두)
first_bootstrap_scene_idx = (
    len(scene_model.keyframes)
    - len(bootstrap_rig_data) * len(view_order)
)
for scene_idx in range(first_bootstrap_scene_idx, len(scene_model.keyframes)):
    scene_model.add_new_gaussians(scene_idx)

# Incremental (이전: ref view만 → 변경: 9 view 모두)
for v_name in view_order:
    ...
    scene_model.add_new_gaussians()  # 9 view 모두 호출
```

#### 결과

| 측정 | 이전 (ref view만, iter=20) | Patch 1 적용 후 (iter=20) | iter=100 (현재 표준) |
|---|---:|---:|---:|
| n_active_gaussians | 545k | 1.42M | 1.23M |
| holdout PSNR | 14.90 | 17.62 | 18.18 |
| 데이터 활용 | 1/9 view | 9/9 view (holdout 시 8/9) | 동일 |

iter=20 baseline 대비 PSNR +2.7 dB. 본 작업의 단일 변경 중 가장 큰 quality 기여로 측정됨.

#### 부수 효과

Cam02 holdout setup 에서 n_gauss 변화가 관찰됨. 이전 구조의 동일 setup 에서는 약 1.6× 더 많은 Gaussian 이 spawn 되었으나 (2.04M vs 1.25M), holdout PSNR 은 오히려 낮았음 (15.33 dB). 9-view spawn 및 mono depth seed 적용 이후 더 적은 Gaussian 으로 동등 또는 향상된 quality 가 측정됨 — representation efficiency 측면에서도 개선이 있음.

---

### 9. 9 view 의 pose 기여도 정량 측정

#### 측정 절차

Run A (full system, lr_poses=1e-4 + refinement on) 1회 학습 + `RIG_DUMP_PNP_STATS=...json`. 15 incremental timestep × 9 view = 135 cell 기록. 평균은 view 별로 (mean over timesteps).

#### 결과

![per_view_pnp](../video_picture/260427/fig_3_6_1_per_view_pnp.png)

위 figure 는 1×2 horizontal bar 구성 (좌: mean effective_weight, 우: mean n_inliers).

| view | rel_R angle | success rate | mean n_inliers | mean effective_weight |
|---|---:|---:|---:|---:|
| High_Cam01 (holdout) | 90° | 1.000 | 492 | 0.201 |
| Low_Cam02 | -144° | 1.000 | 429 | 0.173 |
| High_Cam02 | 135° | 0.933 | 413 | 0.163 |
| Low_Cam01 | 171° | 1.000 | 346 | 0.144 |
| High_Cam08 | 45° | 1.000 | 341 | 0.135 |
| Low_Cam08 | 126° | 1.000 | 218 | 0.068 |
| High_Cam07 (ref) | 0° | 0.933 | 160 | 0.050 |
| High_Cam06 | -45° | 0.867 | 120 | 0.035 |
| Low_Cam07 | 81° | 0.933 | 87 | 0.031 |

#### 측정값의 의미

- 9 view 모두 PnP 에 참여하나 (success rate ≥ 0.867) effective_weight 분포가 비균등 (0.031 ~ 0.201, 범위 6.5×). 이전 보고의 "활용도 100%" 표현은 "All 9 views participate, with non-uniform effective weight" 로 정밀화됨.
- 단일 view 의 최대 weight 가 0.201 에 그쳐 단일 view 의존도가 낮음. 한두 view 의 PnP 실패 시 SE(3) Fréchet mean 의 나머지 후보로 fallback 가능한 구조적 robustness 가 측정값으로 확인됨.

---

### 10. EQR central-camera 가정의 약점 검증

#### 측정 배경

dual-fisheye stitching 으로 생성된 EQR 이 central panorama 가정으로부터 벗어날 가능성 (Seam360GS 등 선행 연구가 지적한 우려) 을 측정으로 확인.

#### 측정 절차

Run A 1회의 per-ts × per-view residual 데이터를 `analyze_feedback_round1.py` 에 입력. View 별 mean residual + seam azimuthal distance 산출 후 scatter plot + Pearson r.

#### 결과

![seam_residual](../video_picture/260427/fig_3_7_1_seam_residual.png)

위 figure 는 log-y scatter plot. x 축은 seam azimuthal distance, y 축은 mean reprojection residual.

| view | view azimuth (°) | seam distance (°) | mean residual (px) | std (px) |
|---|---:|---:|---:|---:|
| Low_Cam01 | 171.1 | 8.9 | 35.99 | 21.26 |
| Low_Cam02 | -143.9 | 36.1 | 33.03 | 18.57 |
| High_Cam02 | 135.0 | 45.0 | 161.09 | 244.55 |
| Low_Cam08 | 126.1 | 53.9 | 30.38 | 30.15 |
| High_Cam01 | 90.0 | 90.0 | 38.46 | 21.23 |
| Low_Cam07 | 81.1 | 98.9 | 23.48 | 22.52 |
| High_Cam06 | -45.0 | 135.0 | 283.66 | 715.89 |
| High_Cam08 | 45.0 | 135.0 | 40.34 | 26.92 |
| High_Cam07 | 0.0 | 180.0 | 43.86 | 58.95 |

| 분석 | 값 |
|---|---:|
| Pearson r (seam_dist, mean_residual) | 0.197 |
| Seam-near (<45°) mean residual | 34.51 px |
| Seam-far (≥45°) mean residual | 88.75 px |

#### 측정값의 의미

- Seam-far bin 평균을 끌어올리는 두 view (High_Cam02 161 px, High_Cam06 284 px ± 716) 는 이전에 known-issue 로 문서화된 high rel_R angle 시드 reflection 영향 view 와 일치함 (commit `095d232`). 즉 outlier 원인은 EQR seam 이 아니라 별도 structural 한계.
- High_Cam06 의 std (715.89 px) 가 mean (283.66 px) 보다 큰 것은 일부 timestep 의 residual 이 매우 크고 나머지는 작은 분산 패턴임. 평균이 outlier timestep 에 가중되어 있음을 의미함.
- 본 single-scene 측정 한정으로, EQR central-camera 가정이 systematic residual 로 드러나는 약점은 관찰되지 않음. Seam360GS 등 선행 연구가 우려한 dual-fisheye stitching artifact 의 영향이 본 데이터에서는 측정되지 않음.

---

## Part 3. 정량/정성 결과

### 11. Quality metrics — train/holdout/all 분리

`render_eval/metrics.json` 의 per-frame 결과를 `is_test` 필드로 split.

| iter | wall (s) | n_gauss | n_anchors | split | n | PSNR | SSIM | LPIPS |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| 100 | 95.4 | 1.23M | 1 | train | 184 | 19.89 | 0.607 | 0.429 |
| 100 | 95.4 | 1.23M | 1 | holdout (`High_Cam01`) | 23 | 18.18 | 0.568 | 0.439 |
| 500 | 238.8 | 2.21M | 3 | train | 184 | 21.36 | 0.695 | 0.358 |
| 500 | 238.8 | 2.21M | 3 | holdout | 23 | 19.83 | 0.678 | 0.355 |

#### 측정값의 의미

- Train 과 holdout 사이 1.5–1.7 dB gap 은 정직한 generalization 신호이며, iter 증가 (100 → 500) 시 holdout PSNR 도 +1.65 dB 함께 향상됨 — 학습 시간 증가가 over-fitting 으로 가지 않음을 시사.
- 단 holdout view 는 같은 EQR 에서 잘라낸 virtual view 이며 pose 는 known `rel_R` 로 derived. 즉 view 1개를 Gaussian scene optimization 에서 제외한 view-held-out 평가이며, 완전 unseen-trajectory 평가가 아님 — 본 결과의 적용 범위가 제한됨.

### 12. Render samples (정성 평가)

![render_grid](../video_picture/260427/render_grid.png)

위 figure 는 4×4 panel 구성:

- 상단 2행: train view (4개, ts=0~3) — rendered (위) 대 GT (아래)
- 하단 2행: holdout view `High_Cam01` (4개, ts=18~22) — rendered (위) 대 GT (아래)
- 각 panel 에 PSNR 표기

train 과 holdout 의 시각 quality gap 이 합리적 범위. 정적 영역 (건물, 도로) 은 잘 복원, 동적 영역 (사람, 차량) 에 일부 blur 발생.

![render_structural](../video_picture/260427/render_structural.png)

위 figure 는 1×4 panel 구성:

- ts=10 에서 Cam02 (rel_R 135°, force-z=1 한계 view) 대 Cam06 (rel_R -45°, 정상 영역) 비교
- 단일 frame PSNR: Cam02 21.84, Cam06 22.51 (gap 0.7 dB)
- holdout 평가 시 gap 이 더 커짐 — Cam02 holdout 시 holdout PSNR 15.33 dB (Cam01 holdout 18.18 대비 약 -2.5 dB). structural limit 의 정량화.

### 13. Runtime — Per-stage breakdown (iter=100)

![per_kf_curve](../video_picture/260427/per_kf_curve.png)

위 figure 는 per-incremental-timestep wall time. iter=100 대 iter=500 비교.

| Stage | 누적 시간 (s) | n_calls | 비율 |
|---|---:|---:|---:|
| Load | 1.02 | 23 | 1.1% |
| BAB (Bootstrap BA) | 11.32 | 1 | 11.9% |
| BAI (Incremental BA) | 6.82 | 15 | 7.2% |
| Add (keyframe + matching) | 19.22 | 16 | 20.1% |
| Opt (optimization loop) | 47.76 | 16 | 50.1% |
| 기타 | ~9.3 | — | ~9.6% |

#### 측정값의 의미

- Bootstrap 1회 비용 25.2s (Load + BAB + Init 합산), 이후 incremental 단계는 timestep 당 평균 4.7s (iter=100), 12s (iter=500) 로 측정됨.
- 본 시스템은 촬영 종료 후 keyframe 단위 처리에 적합한 near-real-time 영역. Hard real-time (33 ms/frame) 영역에는 도달하지 못함.
- Stage 비율상 후속 속도 최적화의 1차 표적은 Opt (50%) + Add (20%) 합산 70%.
- Peak GPU memory 9.0 GB (iter=100). 16 GB GPU 권장, 8 GB 환경에서는 OOM 위험 가능.
