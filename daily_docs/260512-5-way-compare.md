# 260512 - OTF rig vs COLMAP rig 3DGS 5-way 비교

- 데이터셋: Insta360 X5 EQR -> 9 virtual pinhole view x 23 timestamp = 207 frame.
- 기준 실험: `260511_5way_compare`.
- OTF rig 비교군: `rasp_sph_strat_24k_s0`.
- 30k 3DGS 변종은 모두 `gaussian-splatting/train.py --iterations 30000 --resolution 1` 로 학습함.

## 진행 방식 요약

이번 비교의 목적은 OTF rig native 결과의 품질 저하가 **pose / 초기 point cloud 문제인지**, 아니면 **streaming OTF 의 제한된 optimization 및 Gaussian lifecycle 문제인지**를 분리해서 확인하는 것임.

이를 위해 같은 image set, 같은 COLMAP database / matches 를 기준으로 네 가지 30k batch 3DGS 결과를 만들었음. 첫 번째는 기존 COLMAP rig sparse 를 그대로 사용한 baseline 이고, 나머지 세 가지는 OTF rig pose 와 OTF 기반 triangulated points 를 COLMAP rig 결과와 교차시킨 변종임. 마지막 비교군인 OTF rig native 는 batch 3DGS 를 거치지 않은 실제 streaming 결과임.

핵심 결론은 OTF pose 와 OTF-triangulated points 를 30k batch 3DGS 에 넣으면 COLMAP rig baseline 과 거의 같은 PSNR / SSIM / LPIPS 로 수렴한다는 점임. 따라서 이 sequence 에서 OTF native 의 낮은 fine detail 은 pose 나 초기 point cloud 의 치명적 오류라기보다, streaming setting 에서의 제한된 최적화 시간, Gaussian budget, primitive lifecycle 정책의 영향으로 보는 것이 타당함.

## OTF rig native (E) 설정 요약

| 항목 | 설정 | 의미 |
|---|---|---|
| Pose 구조 | shared rig pose + 9 virtual pinhole views | 같은 timestamp 의 9 view 가 하나의 rig pose 를 공유함 |
| Depth source | same-ts MVS / triangulation 제외 | 9 view 는 same-center zero-baseline 이므로 같은 timestamp 에서는 depth cue 가 없음 |
| Spawn proposal | rig-spherical stratified proposal | 이미지 평면 점수보다 rig sphere 의 angular support 를 균등하게 덮도록 후보를 뽑음 |
| Bin 설정 | 4 x 8 yaw / pitch bins | rig sphere 를 32개 angular region 으로 나눠 sampling |
| Spawn budget | 24,000 / timestamp | 한 timestamp 의 9 view 묶음에서 새 Gaussian 수를 제한 |
| Optimization | 270 steps / keyframe | batch 30k 3DGS 와 달리 streaming 조건에서 제한된 local update 로 학습 |
| 안정화 | oversample, atomic spawn, artifact prune 사용 | 후보 탈락, spawn order 의존, 과대 Gaussian 발산을 방지하기 위한 safety stack |
| Seed | 0 | 본 비교는 단일 seed diagnostic 결과임 |

## 비교군 정의

| # | label | pose | points3D init | 의미 |
|---:|---|---|---|---|
| 1 | GT | - | - | 원본 이미지 |
| 2 | COLMAP rig 3DGS 30k | COLMAP rig | COLMAP triangulated | 기존 30k batch 3DGS baseline |
| 3 | OTF->3DGS (B) | Sim(3)-aligned OTF | OTF triangulated | OTF rig 결과를 COLMAP 좌표계로 정렬한 뒤 30k batch 3DGS 학습 |
| 4 | Cross COLMAP pose + OTF points (C) | COLMAP rig | OTF triangulated | pose 는 COLMAP 으로 고정하고 point init 만 OTF 로 교체 |
| 5 | Cross OTF pose + COLMAP points (D) | Sim(3)-aligned OTF | COLMAP triangulated | point init 은 COLMAP 으로 두고 pose 만 OTF 로 교체 |
| 6 | OTF rig native (E) | OTF rig | streaming GS | batch 3DGS 를 거치지 않은 실제 OTF streaming 결과 |

## 정량 요약

아래 값은 9 view x 23 timestamp = 207 장 전체에 대한 reconstruction metric 임. 즉, OTF native 와 30k batch 3DGS 의 품질 차이를 보는 diagnostic 이며, 별도 unseen trajectory 에 대한 generalization 평가로 해석하지 않음.

| method | PSNR | SSIM | LPIPS |
|---|---:|---:|---:|
| COLMAP rig 3DGS 30k | 26.522 | 0.8839 | 0.1805 |
| OTF->3DGS (B) | 26.505 | 0.8842 | 0.1802 |
| Cross COLMAP pose + OTF points (C) | 26.516 | 0.8843 | 0.1799 |
| Cross OTF pose + COLMAP points (D) | 26.527 | 0.8840 | 0.1806 |
| OTF rig native (E) | 20.530 | 0.6092 | 0.4331 |

초기 `points3D` 개수는 COLMAP rig 가 **41,678**, OTF-triangulated 가 **43,579** 임. Sim(3) align residual 은 paired 207 cameras 기준 RMSE **0.008** 임.

30k batch 3DGS 네 변종은 PSNR 26.50-26.53 범위로 거의 동일함. 이는 OTF aligned pose 와 OTF-triangulated points 가 batch refinement 기준에서는 COLMAP rig sparse 와 유사한 수렴점에 도달할 수 있음을 의미함. 반면 OTF rig native 는 PSNR 20.53 으로 약 6 dB 낮음. 따라서 현재 관찰되는 blur / high-frequency detail 손실은 pose 자체의 큰 실패라기보다 streaming OTF 의 제한된 optimization 및 density control 문제로 해석하는 것이 더 자연스러움.

## View 별 정성 비교

아래 이미지는 기존 Markdown 표 안에 개별 이미지를 넣는 방식 대신, view 별로 하나의 composite grid PNG 를 만든 것임. 각 이미지가 동일한 셀 크기에 고정되어 있어 GitHub / VSCode / 브라우저에서 들쭉날쭉하게 보이지 않음.

### High_Cam01 - holdout-like 외곽 view

![High_Cam01 5-way grid](../video_picture/260512/high_cam01_5way_grid.png)

### High_Cam07 - rig reference view

![High_Cam07 5-way grid](../video_picture/260512/high_cam07_5way_grid.png)

### Low_Cam02 - Low row 측면 view

![Low_Cam02 5-way grid](../video_picture/260512/low_cam02_5way_grid.png)

## 해석

- OTF->3DGS (B), Cross C, Cross D 가 모두 COLMAP rig 3DGS 30k 와 거의 동일한 품질로 수렴함.
- 이 결과는 OTF rig pose 또는 OTF-triangulated points 가 30k batch 3DGS 기준에서 큰 품질 병목은 아니라는 근거임.
- OTF rig native 만 detail 이 크게 흐려지는 것은 streaming OTF 가 제한된 local update, 제한된 Gaussian budget, on-the-fly density lifecycle 안에서 복원해야 하기 때문으로 보임.
- 따라서 다음 단계는 pose / triangulation 을 다시 의심하기보다, support-first proposal 을 유지하면서 high-frequency detail 영역에 추가 budget 을 배정하는 방향이 더 적절함.

