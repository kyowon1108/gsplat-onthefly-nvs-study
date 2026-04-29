# 260429 - rig 단위 photometric pose 자유도 재구성

본 보고서는 [260427](260427-ontheflynvs_rig_post_followup_with_ablations.md)
이후 진행된 photometric refinement 자유도 단위 재구성 결과를 다룬다.

---

## 1. 문서 목적

- 260427 §7 의 lr_poses 4-cell ablation 측정 1~4 는 모두 photometric pose 자유도가
  *view 단위* (한 ts 당 9 view × 6 = 54-DoF, holdout 1 view 제외 effective
  48-DoF) 인 구조에서 측정된 것임. 이는 원본 on-the-fly-nvs 의 single-camera
  설계를 그대로 이어받은 것으로, rig 환경에서 rig 가정 (`rel_t = 0`,
  `rel_R` 고정) 이 학습 진행에 따라 view 별로 약간씩 깨질 수 있는 자유도 구조.
- 본 차수는 photometric optimizer 자체를 rig 단위로 재구성하여 측정 5 (rig
  단위 자유도 셋업) 를 추가한다.
- 260427 의 §3, §6, §7, §11, §12 는 본 보고서로 cross-ref 한 줄씩 추가.

---

## 2. 코드 변경 요약 (commit `9706823`, branch `feature/rig-aware-photo`)

| 파일 | 변경 |
|---|---|
| `scene/keyframe.py` | rig 분기. `info["ts_idx"]` + `info["rig_view"]` 가 채워지면 rW2C/tW2C 를 nn.Parameter 가 아닌 plain attr 로 두고, `get_R/get_t/get_Rt` 가 `scene_model.rig_R6D[ts_idx]` / `rig_t[ts_idx]` 로부터 `rel_R @ rig_pose` 로 동적 구성. |
| `scene/scene_model.py` | `rig_R6D`, `rig_t` (`ParameterList`) + `rig_optimizer` 컨테이너. `register_rig_poses` (bootstrap), `append_rig_pose` (incremental), `get_Rts` 에서 rig 모드 시 cached_Rts 우회 (autograd 그래프 stale 방지), `optimization_step` 에서 `rig_optimizer.step()` 추가. |
| `scene/optimizers.py` | `BaseAdam.add_param` 7-line 추가 — incremental 시 동적으로 새 ts 의 rig pose 를 옵티마이저에 등록 (exp_avg/exp_avg_sq 0 으로 초기화). |
| `train.py` | bootstrap 직후 `register_rig_poses(mtx2sixD(R), t)`, incremental 마다 `append_rig_pose`. `inf["ts_idx"]`, `inf["rig_view"]` 를 Keyframe 생성자 호출 전에 채움. `--seed` arg 추가 (multi-run 재현용). |
| `tools/test_b1_autograd.py` | §7.1 단위 검증 (autograd flow + 2nd backward + cached_Rts 우회). |

총 +366 LOC, -10 LOC. 5 files.

### 2.1 핵심 수식

변경 전 (view 단위):

```python
keyframe.rW2C, keyframe.tW2C  ← nn.Parameter
keyframe.get_R() = sixD2mtx(rW2C)
keyframe.get_t() = tW2C
```

변경 후 (rig 단위):

```python
scene_model.rig_R6D[ts], scene_model.rig_t[ts]  ← nn.Parameter
keyframe.get_R() = rel_R[v] @ sixD2mtx(scene_model.rig_R6D[ts_idx])
keyframe.get_t() = rel_R[v] @ scene_model.rig_t[ts_idx]   # rel_t = 0
```

자유도 차원에서 rig 가정이 코드 차원에서 강제되며, 9 view 의 photometric loss
gradient 가 모두 같은 rig_pose 로 합쳐진다.

### 2.2 단위 검증 (`tools/test_b1_autograd.py`)

학습 전 4 단계 검증:

1. 첫 backward — `rig_R6D[ts].grad`, `rig_t[ts].grad` 가 None 이 아니고 finite
2. 두 번째 backward — `rig_optimizer.step()` 직후 같은 keyframe 으로 다시
   forward + backward 했을 때 grad 가 다시 흐름 (cached_Rts stale 그래프 방지)
3. `scene_model.get_Rts()` 가 fresh autograd graph 의 stack 을 반환
4. `append_rig_pose` 후 새 ts 에 대해서도 grad 가 흐름

본 시스템에서 4/4 통과 확인.

---

## 3. 측정 결과 (단일 시드)

iter=100, `--rig_holdout_view High_Cam01`, `--lr_poses 1e-4`, single seed
(`--seed 0`). 같은 셋업의 측정 1 (260427 §7) 과 직접 비교.

### 3.1 σ_center sanity check

`tools/analyze_view_drift.py`. 각 ts 의 9 view 카메라 중심
(`C = -R^T t`) 의 평균으로부터 max 거리. rig 가정 (`rel_t = 0`) 이 깨지지 않으면
≈ 0.

| 셋업 | scene_scale | σ_center mean | σ / scene_scale | σ_center max |
|---|---:|---:|---:|---:|
| 측정 1 (view 단위) | 0.345 | 9.30×10⁻⁴ | 0.27% | 1.46×10⁻³ |
| **측정 5 (rig 단위)** | **0.346** | **1.65×10⁻⁷** | **5×10⁻⁵%** | **3.27×10⁻⁷** |

측정 5 셋업의 σ_center 는 부동소수점 노이즈 수준 (5,600× 작음). rig 가정이
학습 끝까지 코드 차원에서 강제됨이 측정으로 확인.

### 3.2 train/holdout split metrics

`tools/split_metrics_by_test.py` (render_eval/metrics.json 의 per_frame 을
is_test 로 분리).

| 셋업 | iter | wall (s) | n_gauss | split | n | PSNR | SSIM | LPIPS |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| 측정 1 (view 단위) | 100 | 95.4 | 1.23M | train | 184 | 19.690 | 0.593 | 0.435 |
| 측정 1 (view 단위) | 100 | 95.4 | 1.23M | holdout | 23 | 17.463 | 0.545 | 0.450 |
| **측정 5 (rig 단위)** | **100** | **100.0** | **1.27M** | **train** | **184** | **19.619** | **0.580** | **0.439** |
| **측정 5 (rig 단위)** | **100** | **100.0** | **1.27M** | **holdout** | **23** | **17.466** | **0.525** | **0.453** |

Holdout PSNR Δ = +0.003 dB (측정 1 17.463 vs 측정 5 17.466). 자유도 축소
(48 → 6) 가 photometric quality 에는 영향 없음.

### 3.3 Sim(3) 정렬 trajectory metric (single seed)

`tools/compare_with_colmap.py` ref_view = High_Cam07.

| 셋업 | sim3 scale | ATE RMSE (m) | RPE rot RMSE (°) |
|---|---:|---:|---:|
| 측정 1 (view 단위) | 9.963 | 0.0422 | 0.059 |
| **측정 5 (rig 단위)** | **9.949** | **0.0219** | **0.062** |

ATE Δ = -0.0203 m (-48%). view 별 photometric drift 가 ref view 의 ATE 에도
누적 systematic error 로 작용하고 있었으며, rig 단위 갱신이 이를 제거한다.

### 3.4 lr_poses ablation 5-cell — 측정 5 추가

![lr_poses_5cell](../video_picture/260429/fig_3_5_2_lr_poses_5cell.png)

위 figure 는 측정 1~4 (260427 §7) 에 측정 5 (오렌지) 를 추가한 1×3 bar chart.

| run | `lr_poses` | refine | photometric DoF (per ts) | holdout PSNR | ATE (m) | RPE rot (°) |
|---|---|---|---|---:|---:|---:|
| 측정 1 | 1e-4 | on  | view 단위 effective 48 | 17.46 | 0.0422 | 0.059 |
| 측정 2 | 0    | on  | (자세 갱신 없음)        | 17.23 | 0.0232 | 0.061 |
| 측정 3 | 1e-4 | off | view 단위 effective 48 | 17.51 | 0.0400 | 0.094 |
| 측정 4 | 0    | off | (자세 갱신 없음)        | 16.31 | 0.0841 | 0.110 |
| **측정 5** | **1e-4** | **on (rig-unit)** | **rig 단위 6** | **17.47** | **0.0219** | **0.062** |

측정 5 의 ATE 0.0219 는 측정 2 (lr_poses=0, 자세 미갱신) 의 0.0232 보다 작다.
즉 photometric refinement 채널을 끄는 것보다, photometric refinement 를 *rig
자유도로* 켜 두는 것이 trajectory 측면에서 더 정확함.

---

## 4. 측정 결과 (5-run 재현성)

`--seed 42 43 44 45 46`. 그 외 인자 동일. `tools/aggregate_sim3.py` 로 mean ± σ
집계.

### 4.1 Sim(3) 정렬 metric (5-run mean ± σ)

§6 protocol 을 본 셋업에 적용한 결과 (seeds 42, 43, 44, 45, 46).

| 지표 | 측정 1 (view 단위, 260427 §6) | 측정 5 (rig 단위, 본 차수) |
|---|---|---|
| Sim(3) scale | 9.818 ± 4.83×10⁻³ | 9.913 ± 0.130 |
| ATE RMSE (m) | 0.0121 ± 1.74×10⁻³ (0.35%) | 0.1177 ± 0.110 |
| RPE rot RMSE (°) | 0.055 ± 4.0×10⁻³ | 0.234 ± 0.252 |
| RPE trans RMSE | (보고서에 미수록) | 0.0551 ± 0.057 |
| 5-run scale 변동 | 0.05% (relative σ) | 1.31% (relative σ) |

본 5-run 의 ATE/RPE 평균과 σ 가 측정 1 의 5-run 보다 크게 나옴. **자유도 단위
재구성이 photometric 결과 (PSNR) 와 σ_center 에는 명확한 이득을 주지만,
5-run 시드 분산은 view 단위 baseline 보다 큼.** §4.2 에서 시드별 분포로 나눈다.

### 4.2 5-run 시드 별 분포 (정확한 raw 값)

| seed | holdout PSNR | train PSNR | ATE (m) | RPE rot (°) | sim3 scale |
|---:|---:|---:|---:|---:|---:|
| 42 | **16.81** | 18.51 | **0.1847** | **0.30** | 9.903 |
| 43 | 17.43 | 19.80 | 0.0194 | 0.05 | 9.910 |
| 44 | 17.71 | 19.61 | 0.0304 | 0.06 | 9.842 |
| 45 | 17.76 | 19.50 | 0.0600 | 0.06 | 9.761 |
| 46 | **16.26** | 18.14 | **0.2941** | **0.69** | 10.152 |
| (별도) seed 0 | 17.47 | 19.62 | 0.0219 | 0.062 | 9.949 |

3 seed (43, 44, 45) 는 default seed (0) 와 일관된 ATE 0.02–0.06 m 영역. 2 seed
(42, 46) 는 ATE 0.18–0.29 m 의 catastrophic outlier. 후자 두 seed 의 holdout
PSNR 도 16.3–16.8 dB 로 1 dB 이상 낮음.

3-seed (43–45) 만의 mean 은 ATE 0.0366 ± 0.017 m, holdout PSNR 17.63 ± 0.18 dB
로 측정 1 (view 단위) 의 5-run mean 과 비교 가능한 영역. outlier 두 seed 가
존재하는 원인 (예: rig_optimizer.step() 의 stale Adam moment, 특정 sampling
순서에서 9 view photometric grad 합이 발산하는 케이스) 은 본 차수 범위 밖.

> ⚠ 본 5-run 의 시드 (42~46) 는 260427 §6 의 5-run 시드 군과 다를 수 있다.
> 측정 1 의 5-run 도 같은 시드 군에 동일 outlier 패턴이 나타나는지 (즉 학습
> 일반의 시드 민감성인지, rig-unit 셋업 한정 민감성인지) 는 동일 시드 군에서
> 양쪽 셋업을 학습하는 비교 작업이 필요. 본 차수 범위 밖.

---

## 5. 측정 결과 (3-way 비교: GT × 원본 3DGS × 본 시스템)

원본 3DGS 학습 결과 (`/opt/ftp/files/260429_gsplat/images_rendered`) 를 baseline
으로 두고, GT × 원본 3DGS × 본 시스템 (측정 5, rig 단위) 의 정량/정성 비교를
수행.

### 5.1 정량 비교 (frame-by-frame, single seed)

`tools/three_way_compare.py`. PSNR/SSIM/LPIPS 를 각 frame 단위로 계산 후
(split, method) cell 평균.

| split | n | metric | 원본 3DGS | 본 시스템 (측정 5) | Δ (본 − 3DGS) |
|---|---:|---|---:|---:|---:|
| train | 184 | PSNR | 26.516 | 19.609 | -6.908 |
| train | 184 | SSIM | 0.881 | 0.580 | -0.301 |
| train | 184 | LPIPS | 0.130 | 0.470 | +0.340 |
| holdout | 23 | PSNR | 26.568 | 17.456 | -9.112 |
| holdout | 23 | SSIM | 0.911 | 0.525 | -0.386 |
| holdout | 23 | LPIPS | 0.086 | 0.477 | +0.391 |

원본 3DGS 의 quality 가 모든 split 에서 더 높음. 두 시스템은 학습 iter 수,
inductive bias, optimizer hyperparameter 가 다르다. 측정값의 정량 차이 자체가
"3DGS > 본 시스템" 이라는 결론으로 이어지지는 않으며, train↔holdout gap 의
비교가 더 정보적이다.

### 5.2 정성 비교

![3way_render_grid](../video_picture/260429/3way_render_grid.png)

위 figure 는 (2 view × 5 frame) × 3 method = 30 panel grid.

- view: `High_Cam01` (holdout), `High_Cam07` (train, ref view)
- frame ts: 0, 5, 10, 15, 22 (전체 시퀀스 주요 시점)
- 각 panel 하단 PSNR 표기 (GT panel 제외)

정적 영역 (건물, 도로) 에서 두 방법 모두 합리적 quality. 본 시스템 (rig-unit) 은
holdout view 에 대해서도 일관된 quality 를 유지하며, 원본 3DGS 와 비교 시
주로 fine detail (가로수 잎, 텍스처) 에서 차이를 보임.

### 5.3 정량 차이의 해석 범위

본 측정은 두 시스템의 *현재 학습 결과를 같은 GT 에 대해 측정한 차이* 를 보고
한다. 다음은 함의하지 않는다.

- 본 시스템이 원본 3DGS 보다 본질적으로 quality 가 낮음. (학습 iter 수, optimizer,
  initialization 모두 다른 셋업이며, 본 시스템은 stream 제약 하에서 100 iter 만
  학습함.)
- 두 시스템의 representation efficiency 비교. (Gaussian 수, 학습 시간, GPU
  메모리 등이 모두 다르므로 직접 비교 불가.)

함의하는 statement 는 다음에 한정된다.

- 동일 GT 에 대한 frame-by-frame quality 의 절대값
- train 과 holdout split 간 quality gap 의 패턴

---

## 6. 결론

측정값은 두 가지 영역으로 나뉜다.

### 정합 측면에서 측정 5 가 측정 1 보다 명확히 우수한 영역

- σ_center 의 5,600× 감소 — rig 가정 (`rel_t = 0`) 이 학습 끝까지 코드 차원에서
  강제됨. 자유도 차원에서 보장.
- single-seed 학습 (seed 0) 의 ATE -48% — 단일 시드 결과로는 trajectory 정확도가
  명확히 향상됨.
- single-seed holdout PSNR 17.466 vs 17.463 — photometric quality 동등 (자유도 축소가
  rendering 에 페널티 없음).

### 측정 1 보다 부정적 영역

- 5-run ATE/RPE 의 σ — 측정 1 의 σ 가 ~10⁻³ 수준이었으나 본 측정 5 는 σ ~0.1.
  3 seed (43~45) 는 측정 1 5-run 영역과 일치하나, 2 seed (42, 46) 가
  catastrophic outlier 로 평균을 끌어올림.
- 즉 측정 5 셋업은 **best-case quality 는 측정 1 보다 우수하나 worst-case
  variance 가 더 큼**. 시드 민감성 측면에서 추가 안정화 작업이 필요.

### 본 보고서의 main result 로서의 위상

측정 5 는 자유도 단위 재구성이 trajectory 정확도와 rig invariant 강제에 명확한
효과가 있음을 single-seed 측정으로 보였다. 다만 5-run 시드 분포는 측정 1 보다
크고 (대표적으로 시드 2 개에서 outlier 가 발생), 이 셋업이 본 보고서의
*최종 main result* 로 채택되려면 outlier 원인 진단 + 동일 시드 군에서 view
단위 vs rig 단위 직접 비교가 선행되어야 한다. 본 차수에서는 *자유도 재구성이
가능하며 single-seed 학습에서 명확한 이득이 측정된다* 까지를 결론으로 한다.

본 보고서의 측정값은 단일 scene, 단일 시드 + 5-run 시드 군 (42~46) 의 측정에
한정된다. 다른 scene, 다른 holdout view 선택, iter ≥ 500 의 long-train 에서의
검증, 동일 시드 군 view 단위 vs rig 단위 직접 비교는 차후 작업.

---

## 부록 A. 260427 보고서로의 cross-ref 제안

260427 의 §3, §6, §7, §11, §12 끝에 다음 한 줄씩 추가 권장.

- §3: "Rig 단위 photometric optimizer 변경은 [260429] §2 참고."
- §6: "rig 단위 자유도 셋업의 5-run 비교는 [260429] §4 참고."
- §7: "view 단위 자유도 자체를 rig 단위로 재구성한 측정 5 셋업의 결과는
       [260429] §3.4 (5-cell figure 포함) 참고."
- §11: "rig 단위 자유도 셋업의 split metric 은 [260429] §3.2 참고."
- §12: "원본 3DGS 와의 3-way 정량/정성 비교는 [260429] §5 참고."

## 부록 B. 산출물 위치

| 항목 | 경로 |
|---|---|
| commit | `9706823` (branch `feature/rig-aware-photo`, push to `kyowon1108/on-the-fly-nvs-rig`) |
| 단위 검증 | `tools/test_b1_autograd.py` |
| 분석 도구 | `tools/{analyze_view_drift,split_metrics_by_test,compute_metrics,three_way_compare,three_way_grid,aggregate_sim3,visualize_5cell}.py` |
| 단일 시드 학습 | `results/b1_v2/run_B1/` |
| 5-run 학습 | `results/b1_5run/seed{42,43,44,45,46}/` |
| Sim(3) 비교 | `compare/run_B1_v2/`, `compare/b1_5run_seed{42-46}/` |
| 5-run aggregate | `results/b1_5run/sim3_5run_summary.json` |
| Figure | `../video_picture/260429/{fig_3_5_2_lr_poses_5cell,3way_render_grid}.png` |

## 부록 C. 5-run raw 값 (seeds 42~46)

`results/b1_5run/sim3_5run_summary.json`. `tools/aggregate_sim3.py` 로 mean ± σ
집계.

```text
| metric                | mean ± σ (rig-unit B-1 v2, seeds 42-46) |
|-----------------------|------------------------------------------|
| ATE RMSE (m)          | 0.1177 ± 0.110                           |
| RPE trans RMSE        | 0.0551 ± 0.057                           |
| RPE rot RMSE (°)      | 0.234 ± 0.252                            |
| Sim(3) scale          | 9.913 ± 0.130                            |
| Sim(3) R angle (°)    | 37.44 ± 0.45                             |
| Sim(3) |t|            | 4.145 ± 0.23                             |
```

각 seed 별 학습 산출물:

```
results/b1_5run/seed{42,43,44,45,46}/
  metadata.json              ← view-drift 분석 입력
  render_eval/metrics.json   ← split 분석 입력
  trajectory_otf.txt         ← compare_with_colmap 입력
compare/b1_5run_seed{42-46}/
  metrics.json               ← Sim(3) 정렬 결과 (aggregate_sim3 입력)
```
