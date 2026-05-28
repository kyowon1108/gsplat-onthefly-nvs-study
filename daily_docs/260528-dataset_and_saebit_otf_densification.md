## 1. 공개 dataset order / motion continuity

### 1.1 360Roam Dataset의 Scene별 motion 양상

| scene      | timestamp | 총 m<br>길이 | 평균 m<br>길이 | 최대 m<br>길이 | 2m 넘는 ts |
| ---------- | --------: | --------: | ---------: | ---------: | -------: |
| bar        |       152 |     83.16 |      0.299 |       6.96 |        9 |
| base       |       148 |     82.76 |      0.315 |       9.64 |        6 |
| cafe       |        75 |     40.05 |      0.335 |       7.64 |        2 |
| canteen    |        63 |     43.49 |      0.278 |       9.57 |        4 |
| center     |       135 |     93.26 |      0.394 |       5.94 |        8 |
| center1    |        95 |     60.66 |      0.561 |       1.50 |        0 |
| corridor   |        53 |     25.15 |      0.286 |       6.26 |        1 |
| innovation |       161 |     78.58 |      0.302 |       4.88 |        7 |
| lab        |        84 |     47.92 |      0.364 |       7.63 |        2 |
| library    |        66 |     53.63 |      0.578 |       5.13 |        3 |
| office     |       105 |     57.93 |      0.370 |       6.64 |        3 |

### 1.2 Per-scene trajectory figures

- 왼쪽 : official train trajectory top-down view
- 오른쪽 : 각 이전 frame의 길이
- 빨간 dashed trajectory와 빨간 점 : 2.0 m threshold를 넘는 discontinuity step임.

#### center1 - smooth reference sequence

![center1 official trajectory](../video_picture/260528/trajectory_360roam/trajectory_center1.png)

#### bar - main-subsequence only, disclose coverage

![bar official trajectory](../video_picture/260528/trajectory_360roam/trajectory_bar.png)

#### office - not suitable for full-sequence OTF evaluation

![office official trajectory](../video_picture/260528/trajectory_360roam/trajectory_office.png)

### 1.3 결론

- 해당 2m가 넘는 keyframe을 맨 후반 timestamp로 옮기는 처리를 진행했으나 정상적인 pose를 추정하지 못함.
- 원본 OTF에서 언급한 ordered / sufficient overlap / smooth incremental tracking 가정을 깨는 구간이 많음.

---

## 2. 22 timestamp active-window 한계

### 2.1 구조적 사실

| 항목                         |          원본 OTF |                     9-view rig OTF |
| -------------------------- | --------------: | ---------------------------------: |
| 1 timestamp당 keyframe 수    |               1 |                                  9 |
| `max_active_keyframes` 기본값 | 약 200 timestamp |         약 22 full timestamp packet |
| 22 ts 이후                   |   아직 넓은 history | eviction / packet fragmentation 시작 |

### 2.2 center1 측정 결과

- `Sim(3) scale`을 통해 OTF trajectory의 누적 scale drift를 보는 proxy로 사용함.
- 아래 표와 curve는 prefix마다 독립적으로 Sim(3) 정렬한 결과임.

| prefix | ATE RMSE vs official GT | Sim(3) alignment scale | 해석                                             |
| -----: | ----------------------: | ---------------------: | ---------------------------------------------- |
|   0-29 |                 0.334 m |                  5.295 | 22 ts cap 직후까지는 비교적 안정                         |
|   0-49 |                 1.326 m |                  5.604 | 큰 motion cluster 직전, drift 증가 시작               |
|   0-59 |                 2.879 m |                  7.827 | ts 50-60 large-motion cluster 후 scale drift 증가 |
|   0-94 |                 4.635 m |                 16.255 | full sequence 누적 drift / global inconsistency  |

![center1 prefix ATE and scale curve](../video_picture/260528/center1_prefix_ate_scale_curve.png)

 
 - ts 22 active-window cap을 지난 직후에는 ATE와 scale이 비교적 완만하게 유지되지만,
 - ts 50-60 large-motion cluster 이후 Sim(3) scale과 ATE가 함께 증가함.
 - 따라서 center1의 drift는 22 ts boundary에서 즉시 발생했다기보다, 큰 motion 구간에서 incremental pose scale이 틀어진 뒤 누적된 것으로 해석함.

### 2.3 해석

| 질문                                    | 답                                                                                         |
| ------------------------------------- | ----------------------------------------------------------------------------------------- |
| 22 ts를 넘는 순간 바로 망가지는가?                | 아님. prefix 0-29 기준 ATE 0.334 m로 비교적 안정적임.                                                 |
| 그럼 22 ts는 의미 없나?                      | 의미 있음. 9-view rig에서 full-packet active horizon이 원본 대비 약 1/9로 줄어드는 구조적 한계임.                |
| catastrophic drift의 직접 trigger는 무엇인가? | center1에서는 ts 50-60의 큰 motion cluster에서 incremental pose scale이 크게 틀어진 것이 직접 trigger로 보임. |
| active window가 그 drift를 고쳤나?          | 아니오. 다음 §3의 pose movement log 기준, stochastic revisit이 old pose를 local BA처럼 의미 있게 움직이지 못함. |

![center1 full-sequence trajectory overlay](../video_picture/260528/center1_trajectory_full_sim3_overlay.png)

---

## 3. Active-window stochastic revisit / pose movement

- 원본 OTF 논문은 pose 쪽 핵심 구성으로 learned feature matching + GPU-friendly mini BA를 통한 fast pose initialization을 제시함.
- 이후 학습 loop에서는 active window 안의 keyframe을 stochastic하게 revisit하며 pose와 Gaussian을 photometric/depth loss로 update함.
- 다만 원본 OTF README도 no loop closure / no global drift correction을 명시함. 즉 active window revisit은 전역 pose graph나 loop closure가 아니라 streaming refinement 단계임.
- rig OTF, 원본 OTF 둘 다 **한 optimization step은 active window에서 선택된 1개 view만 render/loss/backward**하며, 그 view의 timestamp (rig) pose와 visible Gaussian만 gradient를 받음.
- 따라서 여기서 확인한 질문은 "active window stochastic revisit이 실제로 local/global BA처럼 old pose를 충분히 다시 맞춰 주는가"임.

### 3.1 측정 결과

center1에서 `--log_pose_movement`로 각 incremental timestamp의 270 iteration 전후 rig pose 변화를 기록함.

| 측정 항목                                | 관찰                                                |
| ------------------------------------ | ------------------------------------------------- |
| 새 timestamp pose 변화량                 | bootstrap 직후에는 약 0.1 deg 수준, ts 50 이후에는 거의 0에 가까움 |
| old timestamp pose 평균 회전 변화          | 대체로 0.003-0.02 deg 수준                             |
| old timestamp pose 평균 translation 변화 | 대체로 0.1 mm 이하                                     |
| 큰 drift 구간(ts 50-60)                 | pose movement가 증가하지 않음                            |

### 3.2 해석

| 질문                                            | 응답                                                                                                                                                                                     |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 한 step에서 몇 view를 보나?                          | 1개 view만 render/loss/backward함. 같은 timestamp의 9 view를 동시에 BA하지 않음.                                                                                                                     |
| 선택된 view 외 다른 timestamp pose도 gradient를 받나?   | 아님. picked view의 `ts_idx`에 해당하는 shared rig pose만 graph에 들어감.                                                                                                                           |
| Gaussian은 어떻게 update되나?                       | selected view에서 visible한 Gaussian만 sparse update됨.                                                                                                                                     |
| stochastic revisit이 local BA로 작동하는가?          | 원본 OTF의 mini BA는 pose initialization 단계의 feature-based BA에 가깝고, active-window revisit은 photometric sampling/optimization 단계임. 측정상 pose refinement magnitude도 local BA라고 부르기 어려울 만큼 작음. |
| window 간 global matching / loop closure가 있는가? | 없음. `get_prev_keyframes`는 새 timestamp pose/init을 위한 history 후보를 제공하지만, 과거 anchor/window pose를 다시 움직이는 pose graph나 loop closure는 없음.                                                    |
| rig의 9 view는 서로 pose를 잡아주는가?                  | 같은 timestamp의 9 view가 shared rig pose를 쓰므로 여러 step에 걸쳐 gradient가 누적될 수는 있음. 하지만 한 step에서 9 view가 동시에 pose를 잡아주는 구조는 아님.                                                                |

- active window 안의 view를 stochastic하게 revisit하는 것은 맞지만, center1 pose movement log 기준으로 old rig pose의 평균 변화량은 회전 0.003-0.02 deg, translation 0.1 mm 이하 수준이었음.
- 따라서 현재 baseline에서 active window revisit은 "online stochastic single-view photometric refinement"로 부르는 것이 정확함.
- 원본 OTF의 feature-based mini BA와 같은 의미의 BA, multi-view simultaneous local BA, global BA, loop closure로 설명하면 부정확함.
- pose는 대부분 incremental PnP / MiniBARig 단계에서 결정되고, 이후 photometric optimization에서는 거의 유지되는 것으로 보임.

---

## 4. OTF -> 3DGS train / holdout comparison

- train : High_Cam01을 제외한 8 view × 23 timestamp = 184 view.
- test_hold : High_Cam01 23 timestamp이며, OTF holdout과 동일한 view / timestamp.

- densification OFF : 공식 3DGS의 adaptive density control을 끈 조건임. 즉 split / clone / prune / opacity reset이 실행되지 않음.
- densification ON : 일반 3DGS lifecycle을 켠 조건임.

### 4.1 학교 scene 3-seed 결과

| split | metric | OTF baseline | 3DGS densification OFF | 3DGS densification ON |
|---|---|---:|---:|---:|
| train (184 view) | PSNR | 21.47 ± 0.07 | 21.99 ± 0.12 | **25.42 ± 0.08** |
|  | SSIM | 0.676 ± 0.004 | 0.730 ± 0.005 | **0.854 ± 0.002** |
|  | LPIPS | 0.375 ± 0.003 | 0.344 ± 0.005 | **0.215 ± 0.002** |
| test (23 holdout) | PSNR | 19.60 ± 0.24 | 19.18 ± 0.07 | **21.17 ± 0.08** |
|  | SSIM | 0.652 ± 0.009 | 0.700 ± 0.004 | **0.812 ± 0.002** |
|  | LPIPS | 0.373 ± 0.006 | 0.332 ± 0.005 | **0.230 ± 0.003** |

#### Train-test gap (PSNR)

| pipeline | train | test | gap |
|---|---:|---:|---:|
| OTF baseline | 21.47 | 19.60 | 1.87 |
| 3DGS densification OFF | 21.99 | 19.18 | 2.81 |
| 3DGS densification ON | 25.42 | 21.17 | 4.25 |

#### Mean 차이 (test holdout)

| 비교 | ΔPSNR | ΔSSIM | ΔLPIPS |
|---|---:|---:|---:|
| 3DGS OFF - OTF-rig | -0.42 dB | +0.048 | -0.041 |
| 3DGS ON - OTF-rig | **+1.57 dB** | **+0.160** | **-0.143** |
| 3DGS ON - 3DGS OFF | **+1.99 dB** | **+0.112** | **-0.102** |

#### Gaussian count 확인

| 항목                            | n_Gaussian | 의미                                                  |
| ----------------------------- | ---------: | --------------------------------------------------- |
| OTF base anchor used for 3DGS |    974,108 | 3DGS OFF / ON 초기값으로 사용한 anchor임                     |
| 3DGS densification OFF 30k    |    974,108 | Gaussian 수가 유지됨. adaptive density control이 꺼졌음을 확인함 |
| 3DGS densification ON 30k     |  3,123,265 | split / clone / prune lifecycle이 동작한 결과임            |


#### Figure 1. GT / OTF / 3DGS densification OFF / ON 비교

![saebit holdout comparison](../video_picture/260528/saebit_holdout_gt_otf_3dgs.png)

![](../video_picture/260528/confidence_artifact_crops.png)
- OTF baseline, 3DGS densification OFF, 3DGS densification ON 모두 같은 holdout view에서 렌더함.

| 열                      | 무엇을 보여주나                                                         | 해석                                                                               |
| ---------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| OTF baseline           | 구조는 맞지만 나뭇잎, 가지, 바닥 detail이 흐림                                   | pose와 coarse geometry는 크게 틀리지 않았지만 online OTF의 Gaussian refinement/lifecycle이 부족 |
| 3DGS densification OFF | OTF anchor를 오래 학습하니 일부 detail은 나아지지만 smear/floating artifact가 남음 | 기존 Gaussian만 조정해서는 잘못 크거나 부족한 primitive를 고치기 어려움                                 |
| 3DGS densification ON  | thin branch, foliage, edge detail이 가장 많이 회복                      | split/clone/prune/densification 같은 lifecycle이 품질 회복에 핵심                          |

- OTF가 만든 pose/Gaussian anchor는 발산 없이 3DGS 초기값으로 사용할 수 있음.
- densification OFF는 train SSIM/LPIPS와 test SSIM/LPIPS를 일부 개선하지만, test PSNR은 OTF-rig보다 낮음.
- densification ON은 train과 test 모두에서 가장 좋음. 특히 test 기준 OTF-rig 대비 PSNR +1.57 dB, SSIM +0.160, LPIPS -0.143임.
- densification ON은 train-test gap도 가장 큼. 즉 offline 3DGS가 train detail을 더 강하게 fit하지만, holdout 품질도 함께 개선함.
- 따라서 문제는 "pose/point가 완전히 틀렸나"보다 "어떤 Gaussian을 유지, 제거, 분할, 추가할 것인가"에 더 가까움.

---

## 5. Gaussian confidence

- OTF가 만든 Gaussian point 중 어떤 것은 믿을 만하고, 어떤 것은 blur/artifact를 만들 가능성이 큰가?
- 이 질문은 §4의 3DGS 실험과 연결됨. OTF anchor가 3DGS 초기값으로는 쓸 수 있지만, densification/prune/lifecycle을 켜야 detail이 살아남. 따라서 "어떤 Gaussian을 유지/제거/분할/추가해야 하는가"를 판단할 confidence 신호가 필요함.

### 5.1 Confidence 후보 용어

| 용어                          | 의미                                                                                                      | 쉽게 말하면                                              |
| --------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Gradient EMA                | Gaussian center에 들어온 gradient magnitude의 moving average. 아직 refinement signal을 받는지 보는 parameter-side 신호 | 아직 학습이 이 Gaussian을 계속 고치고 있는지 보는 값임                 |
| Visibility count            | rendering 과정에서 visible로 잡힌 횟수. 실제 output에 자주 관여하는지 보는 visibility-side 신호                                | 이 Gaussian이 실제 렌더에 자주 쓰였는지 보는 값임                    |
| Cross-view visibility       | 같은 timestamp의 다른 rig view에서도 보이는 정도. rig multi-view coverage를 반영하는 geometry-side 신호                     | 한 rig timestamp 안에서 여러 view가 같이 보는 Gaussian인지 보는 값임 |
| Final opacity               | 학습 후 Gaussian의 alpha/opacity                                                                            | 최종적으로 얼마나 강하게 살아남았는지 보는 결과값임                        |
| Physical scale / anisotropy | 너무 크거나 길쭉한 artifact 후보를 찾기 위한 geometry-side 지표                                                          | smear / needle artifact 후보를 찾는 보조 지표임               |
| rank correlation            | 값의 절대 크기보다 순서가 같이 움직이는지를 보는 상관 지표. 여기서는 Spearman correlation을 의미함                                       | 어떤 신호가 커질수록 final opacity도 같이 커지는지 보는 값임            |

### 5.2 Gaussian 생성 출처

OTF의 새 Gaussian은 크게 두 경로에서 생김.

| 생성 경로                          | 쉽게 말하면                                                                      |  이번 비율 | 해석                                        |
| ------------------------------ | --------------------------------------------------------------------------- | -----: | ----------------------------------------- |
| matched keypoint triangulation | 서로 다른 timestamp 이미지에서 같은 feature keypoint를 찾고 3D 위치를 삼각측량해 Gaussian을 만드는 경로 |  2.78% | 전통 SfM sparse point와 비슷하지만, 현재는 보조 경로임    |
| MVS LoG sampling               | 이미지 edge/detail/residual이 큰 위치에 Gaussian을 뿌리는 경로                            | 97.22% | OTF anchor의 대부분은 dense residual 기반 spawn임 |

- `matched keypoint triangulation`: COLMAP sparse point와 비슷한 방식임. 서로 다른 이미지에서 같은 keypoint를 찾고, 두 카메라 pose를 이용해 그 keypoint의 3D 위치를 계산한 뒤 Gaussian을 생성함.
- `MVS LoG sampling` : 명시적인 keypoint match로 3D point를 만든다기보다, 현재 render가 부족하거나 이미지 detail이 강한 위치를 보고 Gaussian 후보를 dense하게 생성하는 OTF식 spawn임.

### 5.3 생성된 Gaussian의 confidence를 어떻게 봤는가

| 신호 그룹             | 측정값                                                    | 쉽게 말하면                              | 이번 결과                                                    |
| ----------------- | ------------------------------------------------------ | ----------------------------------- | -------------------------------------------------------- |
| 살아남은 정도           | final opacity, opacity < 0.05                          | 학습 끝에 이 Gaussian이 강하게 남았는가          | opacity < 0.05가 11.7%로, 약한 prune 후보는 존재함                 |
| 실제 사용 정도          | Visibility count, Cross-view visibility, never visible | 렌더에 실제로 쓰였는가 / 여러 rig view에서 보였는가   | never visible은 0%, visibility count는 final opacity와 잘 맞음 |
| shape artifact 후보 | physical scale, anisotropy                             | 너무 크거나 길쭉해서 blur/needle이 될 가능성이 있는가 | tail은 존재하지만 정상 thin structure와 겹쳐 단독 prune 기준은 위험함       |
| refinement 필요성    | Gradient EMA                                           | 아직 학습이 이 Gaussian을 고치고 있는가          | final opacity와 가장 높은 rank correlation을 보임                |

1. `never visible = 0%`이므로, OTF가 완전히 렌더에 안 닿는 Gaussian을 대량으로 쌓은 상황은 아님.
2. `Gradient EMA`와 `Visibility count`가 final opacity와 가장 잘 맞았음. 즉 “아직 학습 신호를 받는가”와 “실제 렌더에 자주 쓰이는가”가 confidence로 가장 유효한 축임.
3. `physical scale`과 `anisotropy`는 artifact 후보를 찾는 데 유용함. 하지만 나뭇가지, 잎, 난간처럼 정상적으로 길쭉한 구조도 anisotropy가 높게 나올 수 있음. 따라서 현 단계에서 scale/aniso만으로 prune을 결정하면 detail을 같이 지울 위험이 있음.

### 5.4 관련 연구와 confidence 신호의 위치

| 문헌 흐름                           | 대표 논문                                                                                                    | 논문에서 보는 것                                                        | 우리 신호와의 연결                                          |
| ------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------- |
| Gaussian 중요도 / pruning          | [PUP 3D-GS](https://arxiv.org/abs/2406.10219)                                                            | Gaussian을 제거해도 되는지 sensitivity score로 판단함                        | `Gradient EMA`, `final opacity`와 연결됨                |
| gradient 기반 density control     | [AbsGS](https://arxiv.org/abs/2404.10484), [Efficient Density Control](https://arxiv.org/abs/2411.10133) | gradient, scale, split/prune 기준을 개선함                             | `Gradient EMA`, `physical scale`, `anisotropy`와 연결됨 |
| error / coverage redistribution | [Revising Densification](https://arxiv.org/abs/2404.06109), [PRIMU](https://arxiv.org/abs/2508.02443)    | pixel error나 visibility를 Gaussian primitive 단위로 되돌려 배분함          | `Visibility count`, `Cross-view visibility`와 연결됨    |
| uncertainty / view selection    | [FisherRF](https://arxiv.org/abs/2311.17874), [Online GS-NVS](https://arxiv.org/abs/2508.14014)          | 어떤 Gaussian/view가 정보량이 큰지 추정함                                    | rig view coverage와 active view 해석에 연결됨              |
| warm-start point confidence     | [InstantSplat](https://arxiv.org/abs/2403.20309)                                                         | 초기 point의 confidence를 이용해 point filtering / update strength를 조절함 | OTF anchor의 spawn source와 초기 point 신뢰도 질문에 느슨하게 연결됨 |

- Gaussian confidence는 크게 두 축으로 나뉨.
	1. gradient/sensitivity 계열 - 해당 Gaussian이 렌더 품질에 얼마나 민감한지, 또는 아직 refinement가 필요한지를 보는 방식
	2. visibility/coverage 계열 - 해당 Gaussian이 실제 view에서 얼마나 관측되고 렌더에 기여하는지를 보는 방식

- 측정한 `Gradient EMA`와 `Visibility count`는 각각 이 두 축에 대응함.
	1. `Gradient EMA` - refinement 필요성에 가까운 신호
	2. `Visibility count` - 실제 렌더 기여도에 가까운 신호

- 두 신호가 final opacity와 가장 높은 양의 rank correlation을 보였기 때문에, 현재 confidence 진단은 기존 3DGS confidence / density-control 문헌과 해석상 정렬됨.

### 5.5 현재 해석

- OTF anchor의 Gaussian 대부분은 keypoint triangulation이 아니라 **LoG/residual 기반 spawn에서 옴**.
- 따라서 현재 문제는 "sparse keypoint point가 부족함"보다 "LoG/residual 기반으로 많이 생성된 Gaussian 중 무엇을 믿고 무엇을 정리할 것인가"에 가까움.

---

## 6. 360 / EQR pose estimation reference

### 6.1 COLMAP 공식 360 panorama SfM 방식

![](../video_picture/260528/colmap_docs_eqr.png)
- https://colmap.github.io/rigs.html#reconstruction-from-360-spherical-images

| 항목           | 공식 문서 기준 내용                                                     | 우리 상황과의 연결                                  |
| ------------ | --------------------------------------------------------------- | ------------------------------------------- |
| 공식 문서        | COLMAP Rig Support의 `Reconstruction from 360° spherical images` | 360/EQR pose estimation을 위한 공식 route가 존재함   |
| 실행 예제        | `python/examples/panorama_sfm.py`                               | panorama를 virtual pinhole rig로 변환 후 SfM 수행  |
| camera model | virtual image는 `SIMPLE_PINHOLE` 계열로 처리                          | EQR 직접 camera model이 아니라 pinhole crop 방식임   |
| rig 처리       | virtual cameras의 intrinsic/extrinsic을 알고 있다고 두고 fixed rig로 처리   | 우리 rotation-only rig와 개념적으로 유사함             |
| BA 설정        | sensor-from-rig / focal / principal point 등을 고정하는 방향            | known virtual rig calibration을 강하게 신뢰하는 방식임 |

- COLMAP은 360 panorama를 virtual pinhole rig로 변환해 SfM하는 공식 예제를 제공함.

### 6.2 우리 EQR -> 9-view pinhole rig COLMAP과의 관계

| 항목              | COLMAP 공식 panorama SfM                   | 우리 EQR -> N-view rig COLMAP                                  |
| --------------- | ---------------------------------------- | ------------------------------------------------------------ |
| 입력              | 360 panorama                             | EQR에서 추출한 N-view pinhole                                     |
| projection 처리   | panorama를 여러 perspective view로 렌더링       | 우리가 미리 9개 perspective view로 추출                               |
| rig 구조          | fixed virtual camera rig                 | zero-baseline rotation-only virtual rig                      |
| same-frame pair | 같은 panorama에서 나온 virtual views는 별도 처리 필요 | same-ts pair exclusion을 구현함                                  |
| pose 의미         | panorama / rig frame의 pose               | timestamp별 shared rig pose                                   |
| 현재 상태           | 공식 route 확인 완료                           | center1에서 fresh COLMAP trajectory가 official trajectory와 불일치함 |

- 두 방식은 “EQR을 직접 SfM하는 것이 아니라 virtual pinhole rig로 바꾼다”는 점에서 같은 계열임.
- 다만 우리 방식이 COLMAP 공식 `panorama_sfm.py`와 완전히 동일한 것은 아님.

### 6.3 기존 360 NVS / GS 논문에서 pose를 어떻게 쓰는가

| 방법 / 논문 계열 | pose 사용 방식 | 해석 |
|---|---|---|
| 360Roam 원논문 | dataset이 제공하는 calibrated / SfM pose 사용 | fresh COLMAP을 매번 새로 돌린 것이 아니라 제공 pose를 기준으로 NVS 수행 |
| OmniGS / SC-OmniGS 계열 | dataset-provided calibrated camera pose와 sparse point cloud 사용 | 360Roam 계열 GS baseline은 보통 제공 pose를 신뢰함 |
| 우리 OTF-rig | EQR -> virtual pinhole rig 입력에서 pose를 online으로 추정함 | offline calibrated pose를 입력으로 쓰는 360GS와 직접 같은 조건은 아님 |

### 6.4 결론

| 질문                                          | 답                                                                                |
| ------------------------------------------- | -------------------------------------------------------------------------------- |
| COLMAP에 360/EQR pose estimation 공식 경로가 있는가? | 있음. `panorama_sfm.py` 기반 virtual pinhole rig SfM임.                               |
| EQR을 직접 spherical camera model로 푸는가?        | 아님. 공식 camera model 목록에 `EQUIRECTANGULAR` / `SPHERICAL` 직접 모델은 없음.               |
| 우리 N-view rig COLMAP은 그 방향과 관련 있는가?         | 관련 있음. virtual pinhole rig로 바꾸는 같은 계열임.                                          |
| OTF-rig pose 평가는 무엇을 기준으로 해야 하는가?           | fresh COLMAP보다 dataset-provided official trajectory / calibrated pose 기준이 더 타당함. |

---

## Appendix A. Additional 360Roam trajectory figures

360Roam의 모든 scene은 같은 방식으로 official `pose_c2w.json` train trajectory를 시각화함.

![base official trajectory](../video_picture/260528/trajectory_360roam/trajectory_base.png)

![cafe official trajectory](../video_picture/260528/trajectory_360roam/trajectory_cafe.png)

![canteen official trajectory](../video_picture/260528/trajectory_360roam/trajectory_canteen.png)

![center official trajectory](../video_picture/260528/trajectory_360roam/trajectory_center.png)

![corridor official trajectory](../video_picture/260528/trajectory_360roam/trajectory_corridor.png)

![innovation official trajectory](../video_picture/260528/trajectory_360roam/trajectory_innovation.png)

![lab official trajectory](../video_picture/260528/trajectory_360roam/trajectory_lab.png)

![library official trajectory](../video_picture/260528/trajectory_360roam/trajectory_library.png)

## Appendix B. Center1 prefix trajectory diagnostic

- center1 trajectory를 prefix별로 잘라 각각 독립적으로 Sim(3) 정렬한 결과임.

![center1 prefix Sim3 overlays](../video_picture/260528/center1_trajectory_prefix_sim3_overlays.png)

0-29와 0-49에서는 OTF trajectory가 official trajectory와 비교적 잘 맞지만,
0-59부터 끝부분 drift가 커지고, 0-94에서는 전체 trajectory inconsistency가 커짐.
따라서 center1에서는 22 ts active-window boundary 자체보다 ts 50-60 large-motion cluster 이후의 scale inflation이 더 직접적인 drift 신호로 보임.
