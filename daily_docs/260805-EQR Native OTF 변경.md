# EQR Native OTF 변경점 및 OB3D 결과 보고

## 1. Upstream 대비 EQR Native에서 바뀐 것

> Bootstrap → Incremental → Mapper의 큰 처리 순서는 upstream과 동일함.  
> 아래에는 upstream과 동일한 단계는 생략하고, EQR 이식에서 데이터·기하 계약이 바뀐 부분만 정리함.

### 1.1 좌표계 및 관측 계약

| 항목           | upstream pinhole                             | EQR Native                                                                |
| ------------ | -------------------------------------------- | ------------------------------------------------------------------------- |
| Pose         | $\mathbf X_c=\mathbf R\mathbf X_w+\mathbf t$ | 동일함                                                                       |
| 영상 관측        | 픽셀과 focal로 pinhole ray 구성                    | EQR 픽셀을 unit bearing $\mathbf b$로 변환                                      |
| 깊이           | z-depth                                      | radial range $r=\lVert\mathbf X_c\rVert$                                  |
| 역깊이          | $1/z$                                        | inverse radial range $\rho=1/r$                                           |
| 재투영 오차       | pixel residual                               | bearing angular residual                                                  |
| 최적화 residual | 2D pixel residual                            | bearing의 tangent-plane 2D log-map residual                                |
| 영상 경계        | 좌우가 독립적인 평면                                  | 경도 $u$만 주기적으로 wrap하고 위도 $v$는 wrap하지 않음                                    |
| 픽셀 면적        | 균일한 픽셀 가중치                                   | 위도별 solid-angle weight $\cos\phi$ 사용                                      |
| Gauge        | $\mathbf t$ 차이의 평균을 0.1로 정규화                 | camera center $\mathbf C=-\mathbf R^\mathsf T\mathbf t$ 이동량의 평균을 0.1로 정규화 |

EQR bearing 계약은 다음과 같음.

$$
\lambda
=
2\pi
\left(
\frac{\operatorname{wrap}(u)+0.5}{W}
-\frac12
\right),
\qquad
\phi
=
\pi
\left(
\frac12-\frac{v+0.5}{H}
\right)
$$

$$
\mathbf b(u,v)=
\begin{bmatrix}
\cos\phi\sin\lambda\\
-\sin\phi\\
\cos\phi\cos\lambda
\end{bmatrix},
\qquad
\mathbf X_c=r\mathbf b
$$

영상 중앙은 $+Z$, 오른쪽은 $+X$, 아래쪽은 $+Y$임.
### 1.2 Bootstrap

```text
upstream
pixel match → fundamental RANSAC → pose·point·focal MiniBA

EQR Native
bearing match → spherical essential RANSAC → pose·point angular MiniBA
```

| 경계          | upstream                                    | EQR Native                                                                                               |
| ----------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 상대 pose 추정  | pixel correspondence로 fundamental matrix 추정 | bearing correspondence로 spherical essential matrix 추정<br>(EQR 픽셀을 3D 방향 벡터로 바꾼 뒤, 두 카메라 사이의 상대 pose를 추정) |
| 카메라 변수      | pose와 focal을 함께 초기화·최적화                     | EQR projection이 고정되어 focal 변수를 제거함                                                                       |
| BA residual | pixel residual                              | angular tangent-plane residual                                                                           |
| Gauge       | translation-vector 차이 사용                    | camera-center 이동량 사용                                                                                     |

- Angular tangent-plane residual : 관측 bearing과 예측 bearing 사이의 구면 오차를 관측 방향의 접평면 위 2차원 벡터로 표현한 것임. optimizer가 pose를 수정할 방향을 제공함.

### 1.3 Incremental

```text
새 EQR frame
 → 좌우 circular-padding XFeat
 → 회전 보정 angular-parallax KF gate
 → spherical PnP RANSAC
 → angular pose-only LM
 → KF 등록
 → spherical triangulation
 → Mapper
```

| 단계            | upstream pinhole               | EQR Native                                                                               | 상태        |
| ------------- | ------------------------------ | ---------------------------------------------------------------------------------------- | --------- |
| 특징 검출         | 이미지에서 XFeat 검출                 | XFeat을 먼저 EQR 이미지에서 검출 후 검출된 keypoint 위치를 unit bearing으로 변환                              | 불확실       |
| KF gate       | pixel motion과 match 수 사용       | 매칭된 두 bearing 집합에서 Kabsch로 카메라 회전에 의한 공통 움직임 제거. 이후에도 남는 각 변화량의 중앙값이 문턱보다 클 때에만 새 KF로 승인 | 문턱 미확정    |
| 2D–3D 대응      | pixel keypoint ↔ world point   | unit bearing ↔ world point                                                               | 확정        |
| Pose RANSAC   | P4P와 pixel inlier threshold    | spherical PnP와 angular inlier threshold                                                  | 확정        |
| Pose 정련       | pixel residual LM              | angular tangent-plane residual LM<br>(pose로 예측한 ray가 실제 feature ray와 일치하도록 미세 조정)        | 확정        |
| 삼각측량 geometry | positive z와 pixel reprojection | 두 관측 ray의 양수 range와 angular reprojection                                                 | 확정        |
| 삼각측량 채택 gate  | near/far pixel disambiguation  | angular disambiguation<br>(안정적인 교점인지 판단해야 하는데, 지금 해당 부분에 대한 채택 gate에 대한 방법을 구상중)         | 최종 정책 미확정 |
- 특징 검출 부분에서, 극점에 대한 보정 없이 XFeat를 수행하므로, 해당 부분은 작동은 하나 수정이 필요해보임.

### 1.4 Mapper

- depth 계약에 [UniK3D](https://github.com/lpiccinelli-eth/UniK3D)를 사용함. (기존 Depth-Anything-V2 대체)
![](../video_picture/260805/classroom_00000_unik3d.png)
#### Mapper 내부 치환

| 단계              | upstream pinhole             | EQR Native                                                              |
| --------------- | ---------------------------- | ----------------------------------------------------------------------- |
| Depth prior     | relative inverse z-depth     | aligned inverse radial range                                            |
| Guided MVS      | pinhole ray의 z-depth 후보 검증   | 동일 bearing 위의 radial 후보를 이웃 KF에 투영하여 dense XFeat descriptor로 검증         |
| Detail sampling | 평면 Laplacian과 균일 픽셀 sampling | 수평 circular Laplacian과 solid-angle weighted sampling                    |
| Rasterization   | pinhole Gaussian projection  | ODGS의 EQR projection·구면 Jacobian을 사용하고 pixel-center 및 좌우 주기 seam 규약을 적용 |
| Mapping loss    | pixel-mean L1·DSSIM·depth    | 수평 circular DSSIM과 solid-angle weighted L1·DSSIM·depth                  |

- **Guided MVS** : UniK3D가 예측한 거리를 그대로 믿지 않고, 그 주변 거리들을 시험함. 각 후보를 이웃 KF에서 확인하여 같은 물체의 feature와 가장 잘 맞는 거리를 선택함.

- **Rasterizer** : 3D Gaussian의 중심을 경도와 위도로 투영하고, 구면 projection의 Jacobian을 사용하여 화면상의 크기와 모양을 계산함. 투영된 Gaussian들을 합성하여 EQR RGB, alpha 및 radial depth 이미지 생성.

---

## 2. OB3D dataset ego nonego 결과

### 2.1 실험 조건

- 데이터 : OB3D 12개 장면의 ego 및 nonego trajectory
- 입력 : 각 실행 100 frame, 1600×800 EQR
- 반복 : seed 0, 1, 2의 3회 평균과 표본 표준편차를 사용함
- pose 범위 : ATE는 등록된 keyframe pose만 평가함
- test 정책 : `test_hold=8`, 실제 mapping에는 사용하지 않음.
- 시간 : reconstruction time

### 2.2 Ego 결과

| 장면             |          시간 (s) |       ATE (mm) |   WS-PSNR (dB) |          등록 KF |     그중 test KF |
| -------------- | --------------: | -------------: | -------------: | -------------: | -------------: |
| archiviz-flat  |  92.226 ± 1.102 |  0.903 ± 0.109 | 33.471 ± 0.142 | 48.000 ± 0.000 | 13.000 ± 0.000 |
| barbershop     |  99.638 ± 1.626 |  0.620 ± 0.483 | 32.361 ± 0.034 | 52.000 ± 0.000 | 13.000 ± 0.000 |
| bistro         |  36.838 ± 3.034 |  2.110 ± 1.162 | 27.733 ± 0.160 | 19.333 ± 0.577 | 12.333 ± 0.577 |
| classroom      |  89.144 ± 2.225 |  2.166 ± 2.809 | 30.537 ± 1.027 | 47.000 ± 0.000 | 13.000 ± 0.000 |
| emerald-square |  25.059 ± 5.046 | 20.400 ± 8.958 | 20.567 ± 0.576 | 11.667 ± 1.155 | 10.667 ± 1.155 |
| fisher-hut     | 104.494 ± 2.490 |  2.621 ± 0.727 | 26.765 ± 0.047 | 58.000 ± 0.000 | 13.000 ± 0.000 |
| lone-monk      |  62.845 ± 1.088 |  0.700 ± 0.287 | 32.275 ± 0.102 | 36.000 ± 0.000 | 13.000 ± 0.000 |
| pavillion      |  62.033 ± 1.197 |  1.624 ± 0.178 | 35.471 ± 0.129 | 35.000 ± 0.000 | 13.000 ± 0.000 |
| restroom       |  74.531 ± 0.864 |  2.686 ± 3.782 | 30.845 ± 0.229 | 41.000 ± 0.000 | 13.000 ± 0.000 |
| san-miguel     |  69.604 ± 1.259 |  0.966 ± 0.415 | 26.926 ± 0.041 | 40.000 ± 0.000 | 13.000 ± 0.000 |
| sponza         |  65.844 ± 1.250 |  0.391 ± 0.045 | 35.759 ± 0.034 | 35.000 ± 0.000 | 13.000 ± 0.000 |
| sun-temple     |  43.512 ± 1.834 |  1.133 ± 0.108 | 31.458 ± 0.221 | 24.667 ± 0.577 | 12.667 ± 0.577 |

### 2.3 Nonego 결과

| 장면             |          시간 (s) |         ATE (mm) |   WS-PSNR (dB) |           등록 KF |     그중 test KF |
| -------------- | --------------: | ---------------: | -------------: | --------------: | -------------: |
| archiviz-flat  | 107.025 ± 2.146 |    6.918 ± 1.372 | 32.344 ± 0.232 |  60.000 ± 0.000 | 13.000 ± 0.000 |
| barbershop     | 162.630 ± 3.018 |   15.252 ± 2.944 | 27.732 ± 0.199 |  92.000 ± 0.000 | 13.000 ± 0.000 |
| bistro         |  68.681 ± 0.321 |    2.285 ± 0.318 | 28.409 ± 0.051 |  40.000 ± 0.000 | 13.000 ± 0.000 |
| classroom      | 176.087 ± 8.984 |    8.044 ± 2.754 | 30.422 ± 0.186 |  96.000 ± 0.000 | 13.000 ± 0.000 |
| emerald-square |  48.528 ± 1.707 |   24.191 ± 1.193 | 27.376 ± 0.136 |  30.000 ± 0.000 | 13.000 ± 0.000 |
| fisher-hut     | 186.656 ± 1.637 | 106.801 ± 21.787 | 25.418 ± 0.023 | 100.000 ± 0.000 | 13.000 ± 0.000 |
| lone-monk      | 150.845 ± 2.597 |   74.032 ± 9.311 | 28.191 ± 0.298 |  83.000 ± 0.000 | 13.000 ± 0.000 |
| pavillion      | 126.194 ± 1.452 |   98.503 ± 3.830 | 33.696 ± 0.161 |  70.000 ± 0.000 | 13.000 ± 0.000 |
| restroom       | 162.430 ± 1.161 |    7.903 ± 1.591 | 30.802 ± 0.062 |  87.000 ± 0.000 | 13.000 ± 0.000 |
| san-miguel     | 178.198 ± 2.387 |  133.045 ± 5.330 | 25.361 ± 0.116 | 100.000 ± 0.000 | 13.000 ± 0.000 |
| sponza         | 174.261 ± 0.853 |   18.216 ± 0.965 | 31.185 ± 0.114 |  99.000 ± 0.000 | 13.000 ± 0.000 |
| sun-temple     |  97.983 ± 0.773 |    3.937 ± 0.514 | 31.971 ± 0.036 |  56.000 ± 0.000 | 13.000 ± 0.000 |

---

## 3. 장면별 등록 궤적

동일 장면의 Ego/Nonego 궤적을 seed 0, 1, 2로 비교함.
회색은 GT, 파란색은 mapping KF, 주황색은 test KF를 뜻함.  

### 3.1 Archiviz Flat

Ego는 적은 KF로 GT 궤적을 안정적으로 따라가며 낮은 ATE를 보임.  
Nonego는 더 많은 KF가 등록되지만, 등록 수 증가에 비해 포즈 오차가 더 크게 남는 장면임.

![Archiviz Flat Ego/Nonego seed별 등록 궤적](../video_picture/260805/archiviz-flat-trajectory-summary.png)

![Archiviz Flat Ego 입력 이미지 0](../video_picture/260805/archiviz-flat-ego-image00000.png)

### 3.2 Barbershop

Ego는 약 절반의 프레임을 KF로 선택하면서 낮은 ATE를 유지함.  
Nonego는 대부분의 프레임이 등록되지만 ATE가 더 커, 등록률과 포즈 정확도가 동일한 지표가 아님을 보여줌.

![Barbershop Ego/Nonego seed별 등록 궤적](../video_picture/260805/barbershop-trajectory-summary.png)

![Barbershop Ego 입력 이미지 0](../video_picture/260805/barbershop-ego-image00000.png)

### 3.3 Bistro

Ego와 Nonego 모두 비교적 낮은 ATE로 전체 이동 형태를 따라감.  
Nonego가 더 많은 KF를 사용하지만 두 motion 유형 모두 안정적으로 등록된 사례임.

![Bistro Ego/Nonego seed별 등록 궤적](../video_picture/260805/bistro-trajectory-summary.png)

![Bistro Ego 입력 이미지 0](../video_picture/260805/bistro-ego-image00000.png)

### 3.4 Classroom

Ego는 선택적인 KF 등록으로 낮은 ATE를 유지함.  
Nonego는 거의 모든 프레임이 등록되지만 중간 수준의 drift가 남아, 높은 등록률만으로 정확도를 판단할 수 없음을 보여줌.

![Classroom Ego/Nonego seed별 등록 궤적](../video_picture/260805/classroom-trajectory-summary.png)

![Classroom Ego 입력 이미지 0](../video_picture/260805/classroom-ego-image00000.png)

### 3.5 Emerald Square

Ego는 mapping KF가 거의 생성되지 않고 test KF 위주로 궤적이 표시되어, KF gate 미발화가 두드러지는 장면임.  
Nonego도 등록 수에 비해 ATE가 크므로, 두 경로 모두 gate·PnP·mapping 상태를 별도로 확인해야 함.

![Emerald Square Ego/Nonego seed별 등록 궤적](../video_picture/260805/emerald-square-trajectory-summary.png)

![Emerald Square Ego 입력 이미지 0](../video_picture/260805/emerald-square-ego-image00000.png)

### 3.6 Fisher Hut

Ego는 안정적으로 GT 궤적을 추종하며 낮은 ATE를 보임.  
Nonego는 전 프레임이 등록되었음에도 큰 drift가 발생하여, 등록 성공과 올바른 포즈 추정이 분리되어야 함을 가장 분명히 보여줌.

![Fisher Hut Ego/Nonego seed별 등록 궤적](../video_picture/260805/fisher-hut-trajectory-summary.png)

![Fisher Hut Ego 입력 이미지 0](../video_picture/260805/fisher-hut-ego-image00000.png)

### 3.7 Lone Monk

Ego는 비교적 적은 KF로 낮은 ATE를 유지함.  
Nonego는 등록 프레임이 크게 늘지만 궤적 오차도 함께 커져, 포즈 품질을 별도로 검증해야 하는 장면임.

![Lone Monk Ego/Nonego seed별 등록 궤적](../video_picture/260805/lone-monk-trajectory-summary.png)

![Lone Monk Ego 입력 이미지 0](../video_picture/260805/lone-monk-ego-image00000.png)

### 3.8 Pavillion

Ego는 선택된 KF가 GT 이동 형태를 비교적 안정적으로 추정함.  
Nonego는 더 많은 프레임이 등록되지만 큰 drift가 남아, 높은 coverage가 정확한 trajectory를 보장하지 않음을 보여줌.

![Pavillion Ego/Nonego seed별 등록 궤적](../video_picture/260805/pavillion-trajectory-summary.png)

![Pavillion Ego 입력 이미지 0](../video_picture/260805/pavillion-ego-image00000.png)

### 3.9 Restroom

Ego와 Nonego 모두 전반적인 궤적 형태를 따라가지만 seed별 오차 차이가 관찰됨.  
특히 Ego ATE의 분산이 커, 평균값과 함께 반복 실행 안정성을 확인해야 하는 장면임.

![Restroom Ego/Nonego seed별 등록 궤적](../video_picture/260805/restroom-trajectory-summary.png)

![Restroom Ego 입력 이미지 0](../video_picture/260805/restroom-ego-image00000.png)

### 3.10 San Miguel

Ego는 제한된 KF로 낮은 ATE를 유지함.  
Nonego는 전 프레임이 등록되지만 매우 큰 drift가 발생하여, 등록률과 정확도를 함께 보고해야 하는 대표 사례임.

![San Miguel Ego/Nonego seed별 등록 궤적](../video_picture/260805/san-miguel-trajectory-summary.png)

![San Miguel Ego 입력 이미지 0](../video_picture/260805/san-miguel-ego-image00000.png)

### 3.11 Sponza

Ego는 낮은 ATE로 GT 궤적을 안정적으로 추종함.  
Nonego도 거의 모든 프레임이 등록되지만 Ego보다 큰 오차가 남아 motion 유형에 따른 차이를 보여줌.

![Sponza Ego/Nonego seed별 등록 궤적](../video_picture/260805/sponza-trajectory-summary.png)

![Sponza Ego 입력 이미지 0](../video_picture/260805/sponza-ego-image00000.png)

### 3.12 Sun Temple

Ego와 Nonego 모두 비교적 낮은 ATE로 궤적의 주요 형태를 따라감.  
등록 수는 motion 유형에 따라 다르지만 두 경로가 모두 안정적으로 동작한 사례임.

![Sun Temple Ego/Nonego seed별 등록 궤적](../video_picture/260805/sun-temple-trajectory-summary.png)

![Sun Temple Ego 입력 이미지 0](../video_picture/260805/sun-temple-ego-image00000.png)
