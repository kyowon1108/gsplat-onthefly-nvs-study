# Gaussian rendering quality 비교

## 1. 비교 대상

| # | 방법 | 약칭 | iter | pose 출처 | 비고 |
|---|------|------|----:|-----------|------|
| 1 | Ground truth | **GT** | — | — | 참조 |
| 2 | 3DGS (rig-constrained COLMAP poses) | **3DGS (rig)** | 30,000 | `colmap/rig` | 공유 PINHOLE, 41,678 sparse points |
| 3 | 3DGS (OTF rig poses + 신규 SIFT 삼각측량) | **3DGS (OTF→3DGS)** | 30,000 | `colmap/ontheflynvs` | per-image SIMPLE_PINHOLE f=480, cx=cy=479.5, 47,272 points |
| 4 | On-the-fly NVS rig (photometric only) | **OTF rig** | 100 | OTF 자체 | rig-unit lr_poses=1e-4, holdout=High_Cam01 |
| 5 | On-the-fly NVS (rig 제약 X, view-major 입력) | **OTF non-rig** | 30 | OTF 자체 | view 가 다른 카메라로 넘어가는 8 곳의 transition 중 4 곳에서 reboot 발생 (§3-4) |

---

## 2. 정량 비교

### 2.1 전체 평균

| 방법 | iter | n | PSNR (dB) | SSIM | LPIPS | wall (s) | n_anchors |
|------|----:|--:|---------:|----:|------:|--------:|---------:|
| **3DGS (rig)** | 30,000 | 207 | **26.52** | **0.884** | **0.181** | ~4564 | — |
| 3DGS (OTF→3DGS) | 30,000 | 207 | 24.63 | 0.840 | 0.228 | ~4549 | — |
| OTF rig | **100** | 207 | 18.91 | 0.599 | 0.431 | 97 | 1 |
| OTF non-rig | **30** | 190 (17↓) | 15.97 | 0.449 | 0.540 | 130 | 5 |

### 2.2 PSNR 분포 (OTF 방법)

| 방법 | min | max | range |
|------|---:|---:|---:|
| OTF rig (iter=100) | 11.75 | 25.32 | 13.6 dB |
| OTF non-rig (iter=30) | 8.29 | 22.11 | 13.8 dB |

### 2.3 OTF rig: train / holdout split (High_Cam01 holdout)

| split | n | PSNR | SSIM | LPIPS |
|------|--:|----:|----:|----:|
| train (8 view × 23 ts) | 184 | 19.03 | 0.602 | 0.430 |
| holdout (High_Cam01 × 23 ts) | 23 | 17.96 | 0.568 | 0.437 |
| gap (train − holdout) | — | +1.07 | +0.034 | −0.007 |

- train ↔ holdout 격차 1.07 dB → photometric overfit 없이 rig 구조가 holdout 에 일반화됨.

### 2.4 Trajectory 정성 비교 (OTF NVS → COLMAP gui export)

| OTF rig (ATE 0.011 m, scene_scale 의 0.31%) | OTF non-rig (ATE 2.115 m, scene_scale 의 61.4%) |
|:---:|:---:|
| ![otf_rig_trajectory](../video_picture/260507/otf_rig_colmap.png) | ![otf_norig_trajectory](../video_picture/260507/otf_norig_colmap.png) |

- **좌 (rig 제약 O)** — 점들이 단일 oval loop 으로 균등하게 정렬. rig 가 강체로 유지된 채 timestamp 따라 일정하게 이동. spatial extent 작음.
- **우 (rig 제약 X)** — 동일 viewport 안에서 여러 partial loop + 분리된 cluster 로 fragmented. §3-4 의 "4 회 reboot → scene 5 조각 분할" 이 그림 위에 직접 매칭됨. 우측 아래 별개 cluster 가 그 대표 예. spatial extent 가 좌측 대비 현저히 큼 → ATE 2.11 m / scene_scale 의 61.4% 가 시각적으로 확인됨.

### 2.5 COLMAP rig (3DGS rig 입력) trajectory

![colmap_rig_trajectory](../video_picture/260507/rig_constraint_colmap.png)

---

## 3. 핵심 관찰

### 3.1 3DGS (rig) 가 종합 1위

- PSNR 26.52 / SSIM 0.884 / LPIPS 0.181.

### 3.2 3DGS (OTF→3DGS) 는 3DGS (rig) 대비 −1.89 dB

- 26.52 → 24.63.
- OTF rig pose 를 입력으로 30k 학습해 OTF rig 자체 (18.91 dB) 보다는 +5.72 dB 회복.
- 그러나 3DGS (rig) 수준에는 여전히 못 미침. 원인 추정: §3.5.

### 3.3 OTF rig 는 100 iter / 97 s 로 18.91 dB

- 3DGS (rig) 대비 iter 300× / wall time 47× 빠름 (4564 s → 97 s).
- holdout 일반화도 안정적 (§2.3, gap +1.07 dB).

### 3.4 OTF non-rig 는 모든 지표에서 최하위

- 17 프레임 누락 (8.2%).
- 9 view × 23 ts 입력에서 view 가 다른 카메라로 넘어가는 8 곳의 transition 중 4 곳에서 reboot 발생 → scene 5 조각으로 분할.
- ATE 2.11 m = scene_scale 의 61.4% → trajectory 복원 실패 수준.

### 3.5 잔여 −1.89 dB (3DGS rig 대비) 원인 추정

- OTF rig 는 ATE 0.0105 m 로 COLMAP 과 거의 같은 pose 임에도 3DGS (OTF→3DGS) 가 3DGS (rig) 에 못 미침.
- 추정 원인:
  - (a) per-image SIMPLE_PINHOLE 207 개 vs 공유 PINHOLE 9 개 [3DGS rig] — 같은 params 라도 3DGS 의 BA 가 image 별 독립 refine 가능.
  - (b) 47k SIFT 삼각측량 점 vs 41k rig-constrained BA 점.
  - (c) 잔여 ATE 0.0105 m 의 합산 효과.

---

## 4. 시각 비교 (3 view × 5 ts)

- 각 grid 이미지는 한 (camera, timestamp) 조합에 대해 5-column 가로 배치.
- 배치 순서: `GT | 3DGS (rig) | 3DGS (OTF→3DGS) | OTF rig | OTF non-rig`.
- 누락된 OTF non-rig 프레임은 우측 끝에 회색 *(missing)* placeholder 로 표시.

3 view 선정 이유:

| view | 역할 | 선정 이유 |
|------|------|-----------|
| **High_Cam01** | holdout | OTF rig 학습에서 빠진 view → §2.3 의 일반화를 시각적으로 확인 |
| **High_Cam07** | reference | OTF rig 의 ref_view (rig 좌표계 원점 기준 카메라) → 가장 안정 학습된 view |
| **Low_Cam02** | side / 다른 height | High row 가 아닌 Low row 의 측면 view → row × position 조합의 일반성 확인 |

### 4.1 High_Cam01 (holdout view)

![High_Cam01_ts00](../video_picture/260507/High_Cam01_ts00.png)
![High_Cam01_ts05](../video_picture/260507/High_Cam01_ts05.png)
![High_Cam01_ts11](../video_picture/260507/High_Cam01_ts11.png)
![High_Cam01_ts16](../video_picture/260507/High_Cam01_ts16.png)
![High_Cam01_ts22](../video_picture/260507/High_Cam01_ts22.png)

### 4.2 High_Cam07 (ref view)

![High_Cam07_ts00](../video_picture/260507/High_Cam07_ts00.png)
![High_Cam07_ts05](../video_picture/260507/High_Cam07_ts05.png)
![High_Cam07_ts11](../video_picture/260507/High_Cam07_ts11.png)
![High_Cam07_ts16](../video_picture/260507/High_Cam07_ts16.png)
![High_Cam07_ts22](../video_picture/260507/High_Cam07_ts22.png)

### 4.3 Low_Cam02 (한 측면 view)

![Low_Cam02_ts00](../video_picture/260507/Low_Cam02_ts00.png)
![Low_Cam02_ts05](../video_picture/260507/Low_Cam02_ts05.png)
![Low_Cam02_ts11](../video_picture/260507/Low_Cam02_ts11.png)
![Low_Cam02_ts16](../video_picture/260507/Low_Cam02_ts16.png)
![Low_Cam02_ts22](../video_picture/260507/Low_Cam02_ts22.png)
