## 1. COLMAP 4.1.0 Panorama SfM 비교

COLMAP 4.1.0은 360° 파노라마를 직접 처리하는 구면 카메라 모델을 추가함. 공식 릴리즈 문서는 이 native 방식이 `panorama_sfm`의 perspective rendering 방식보다 **일반적으로 빠르지만 정확도는 낮다**고 설명함. ([COLMAP 4.1.0 Changelog](https://github.com/colmap/colmap/blob/main/CHANGELOG.rst#colmap-410-06262026))

| 표기 | 공식 `panorama_sfm` mode | 이번 실험에서 수행한 처리 |
|---|---|---|
| **S** | `spherical` | 원본 EQR을 COLMAP의 native `EQUIRECTANGULAR` 카메라로 직접 재구성 |
| **P** | `perspective_overlapping` | EQR 1장을 겹치는 12개 `SIMPLE_PINHOLE` 영상으로 렌더링한 뒤 rig로 재구성 |

### 평가 scene (OB3D)
![OB3D scene first frames](../video_picture/260715/scene_first_frames_3x4.png)

### 실험 및 핵심 결과

12 scenes × Ego/Nonego × S/P × 3회, 총 144회를 동일한 CUDA SIFT·matching 및 loop retrieval 조건으로 수행함.

| Trajectory | scene 평균 ATE S / P | scene 중앙값 ATE S / P | 더 정확한 scene S / P | P 시간 배수 |
| ---------- | -----------------: | ------------------: | ----------------: | ------: |
| Ego        |   8.688 / 0.844 mm |    0.801 / 0.585 mm |             5 / 6 |   1.46× |
| Nonego     | 82.743 / 17.934 mm |    2.224 / 2.941 mm |             9 / 3 |   2.42× |

| 결과가 불안정한 scene     | 문제                                                 |
| ------------------ | -------------------------------------------------- |
| Ego Bistro–P       | run2/3이 각각 24/100, 17/100 frame만 등록되어 ATE 직접 비교 불가 |
| Ego Lone-monk–S    | 3/3회 frame 40 pose spike, 최대 0.82–0.86 m           |
| Nonego Pavillion–S | 3/3회 pose spike, 최대 4.44–7.14 m                    |
| Nonego Restroom–S  | 2/3회 초반 pose spike, 최대 약 2.68 m                    |

### Trajectory 비교

![Corrected trajectory comparison](../video_picture/260715/F2_trajectory_examples.png)

### 시간 차이 정량 분석

| 항목           | Native EQR | 12-view perspective |
| ------------ | ---------: | ------------------: |
| COLMAP 영상 수  |       100장 |              1,200장 |
| 영상 해상도       |   1600×800 |             400×400 |
| 원본 프레임당 총 픽셀 |      1.28M |               1.92M |
| 픽셀 증가        |         1× |            **1.5×** |
- 100장 기준으로 계산한 결과, 12 view로 나눈 것이 native보다 픽셀 수를 1.5배 더 사용하고 있었음.
- 그리고 등록하는 이미지의 수가 12배가 되므로 feature matching 부터 더 많은 연산량을 요구함.

### 실제 측정된 단계별 시간

| 단계              | Native EQR |                 12-view |           실제 증가 |
| --------------- | ---------: | ----------------------: | --------------: |
| Perspective 렌더링 |         없음 |                   약 36초 |       추가 CPU 비용 |
| GPU feature 추출  |     약 4.6초 |                   약 21초 |      **약 4.6배** |
| GPU matching    |   약 12–16초 |                  약 103초 |  **약 6.4–8.8배** |
| Mapper          | 약 135–189초 |              약 135–154초 | 장면에 따라 비슷하거나 역전 |
| 전체 scene 시간     |         기준 | Ego 1.46배, Nonego 2.42배 |  **실질적으로 큰 차이** |
### 결론

- **속도:** spherical가 perspective_overlapping 명확히 빨라 공식 설명과 일치함.
- **정확도:** perspective_overlapping 큰 pose spike를 줄였지만, 일관된 우위는 보이지 않음. (데이터셋의 한계?)
- **해석:** spherical은 빠르고 등록이 잘 되지만 특정 scene에서는 일부 frame이 튀는 현상 발생. (공식 릴리즈 문서에서 표기한 정확도 낮음을 의미하는가?)

> Perspective가 항상 정확한 것도 아니고, spherical이 항상 robust한 것도 아님.
> Spherical은 빠르고 전체 연결성을 유지하는 데 유리하지만 일부 잘못된 match에 크게 흔들릴 수 있고, perspective는 match를 안정화하지만 분할된 view 사이의 연결이 끊길 수 있음.

---

## 2. Native EQR과 pinhole 분할의 robustness 조건

핵심은 **특징점의 국소 왜곡**과 **한 view가 유지하는 시야·연결성** 사이의 trade-off임.

| 처리 방식                  | 이득이 생기는 과정                                                               | 반대로 취약해지는 조건                                                      |
| ---------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| **Pinhole/tangent 분할** | EQR의 적도·고위도·seam 사이를 이동해도, 저왜곡 perspective view에서는 국소 모양이 비교적 일정함.       | 너무 잘게 분할하면 view별 FOV가 작아져 큰 구조가 잘려 전체 연결을 놓칠 수 있음.                |
| **Native EQR**         | 한 장에서 360° 특징을 함께 사용하므로 여러 방향에 흩어진 특징과 큰 구조를 유지하고 view graph가 끊길 위험이 작음. | EQR 위치에 따라 같은 물체의 국소 모양이 비선형적으로 달라져 부분 모양이 일그러질 수 있음. (추가 연산이 필요) |

```text
적당한 분할:  EQR 왜곡 감소 → 반복 가능한 특징점 증가 → pose가 안정될 가능성 증가
과도한 분할:  view FOV 감소 → 큰 특징·공통 관측 감소 → 등록 단절 가능성 증가
```

> pinhole 분할은 구면 왜곡에 의한 feature 불안정을 줄이지만, 분할이 많아질수록 시야와 연결성을 잃을 수 있음.
> Native EQR은 반대 특성을 가지므로 두 방식은 우열 관계보다 서로의 trade off를 가진 것으로 봐야 함.

---

## 3. ODGS-SLAM dataset 분석

ODGS-SLAM은 실제 실내 + Blender 합성 실내/실외 데이터셋에서 native EQR RGB/RGBD SLAM을 평가함. ([paper](https://openaccess.thecvf.com/content/CVPR2026/papers/Spiss_ODGS-SLAM_Omnidirectional_Gaussian_Splatting_SLAM_CVPR_2026_paper.pdf), [supplement](https://openaccess.thecvf.com/content/CVPR2026/supplemental/Spiss_ODGS-SLAM_Omnidirectional_Gaussian_CVPR_2026_supplemental.pdf))

| 구분                | 데이터·규모                                          | EQR / Depth                          |
| ----------------- | ----------------------------------------------- | ------------------------------------ |
| Real–Insta360 Pro | 실내 5 sequences, 354~954 frames                  | 1920×960 / 6-fisheye stereo 추정 depth |
| Real–Insta360 X4  | direct·extension 각 4 sequences, 485~2792 frames | 3840×1920 / **depth 없음**             |
| Synthetic–Indoor  | `Italian Flat`, 5 trajectories, 250~1500 frames | 3840×1920 / Blender GT depth         |
| Synthetic–Outdoor | UZH virtual urban, 3000 frames                  | 3840×1920 / Blender GT depth         |

![ODGS-SLAM synthetic indoor/outdoor RGB and depth examples](../video_picture/260715/odgs_synthetic_dataset_examples.png)

- ODGS-SLAM supplement paper - synthetic indoor/outdoor의 EQR·fisheye·pinhole RGB/depth 예시.
- Cycles : Blender의 물리 기반 렌더링 엔진

### Depth 유무에 따른 핵심 결과

| 평가 조건               |                            RGB ATE |    RGBD ATE | 해석                           |
| ------------------- | ---------------------------------: | ----------: | ---------------------------- |
| Synthetic indoor 평균 |                            0.068 m | **0.029 m** | GT depth로 57% 감소             |
| Synthetic outdoor   |                           36.070 m | **0.571 m** | 장거리 monocular scale drift 복구 |
| Real Insta360 Pro   |                        **0.031 m** |     0.055 m | noisy stereo depth로 오히려 악화   |
| Real Insta360 X4    | direct 0.032 m / extension 0.062 m |         미제공 |                              |
- 렌더링에서는 depth가 항상 유리하지 않음. synthetic PSNR은 28.45→29.37 dB였지만, real Pro는 24.35→23.19 dB로 하락함.
- Synthetic 기준 depth 사용 시 tracking은 1.27→1.71 s, GPU 메모리는 약 6.7→10.3 GB로 증가함.

> Blender 모델을 사용한 train은 Depth를 제공해줌에 따라 indoor는 더 trajecoty를 따라갔고, outdoor에 대해서는 drift를 복구한 수준으로 trajectory를 따라감.
> 반면 실제 Insta360 Pro에서는 6-fisheye stereo 추정 depth의 noise 때문에 RGBD 결과가 오히려 악화됐으며, depth가 없는 X4에서는 RGB-only 경로가 사용됨.
> 따라서 depth의 존재보다 신뢰도가 중요함.