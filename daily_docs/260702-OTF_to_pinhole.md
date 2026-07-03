
① 왜 OTF는 pinhole 이미지로만 되는가?
② EQR(360°)을 그대로 못 쓰는 이유?
③ 가능은 한가?

----

# 1. 왜 OTF는 pinhole 전용인가?

## 1.1 OTF 전체 흐름 요약
| 단계          | 흐름                                                                                                                                 |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Feature     | 각 이미지에서 XFeat로 keypoint+descriptor(≈6144개) 추출.                                                                                     |
| Match       | 프레임 쌍에서 mutual-NN + cosine 임계로 매칭 → **fundamental-matrix RANSAC**으로 outlier 제거(inlier만 남김)                                         |
| Bootstrap   | Bootstrap 이미지를 한번에 exhaustive pairwise match 진행(8장을 한 번에 joint mini-BA). 이후 8개 등록된 keyframe의 pose 및 공유 focal 및 sparse 3D map을 출력함. |
| Incremental | 등록되면 최근 keyframe들과 매칭해 map의 기존 3D점과 **2D-3D 대응 → PnP(resection)+pose-only BA로 새 pose부터 확정** → 그 뒤 아직 3D 없는 매칭을 **삼각측량**해 map 확장    |
| Spawn       | LoG를 통해 방금 등록된 keyframe에서 이미 잘 렌더된 영역보다, detail이 있으면서 렌더가 나쁜 픽셀에 우선 spawn 진행함.                                                     |
| Render      | keyframe당 30 iter로 photometric 최적화를 진행함. (Pose와 Gaussian 둘 다)                                                                      |

## 1.2 pinhole이 어디에 기여하고 있는가?
| 단계          | 이 단계가 pinhole에 기대는 지점                                                                      |
| ----------- | ------------------------------------------------------------------------------------------ |
| Feature     | XFeat이 **perspective 이미지로 학습**함.                                                           |
| Match       | outlier 제거의 **fundamental matrix = perspective epipolar(두 카메라의 위치와 이미지 평면 간의 기하학적 관계) 가정** |
| Bootstrap   | mini-BA residual = **`pts2px(R·X+t) − uv`(pixel)** + ==공유 focal==                          |
| Incremental | PnP도 같은 pixel reprojection 최소화 + triangulation은 **pinhole ray + z>0 cheirality**           |
| Spawn       | depth→3D 배치가 **`depth2points`(z-depth 역투영)**                                               |
| Render      | 미분가능 rasterizer가 **pinhole 투영 + EWA Jacobian + z>0 frustum culling**                       |

---

# 2. 왜 EQR을 그대로 못 쓰는가?

![](../video_picture/260702/ob3d_explain.png)
- OB3D의 dataset 중 하나를 예시로 특징을 시각화함.

### 2.1 용어 정리
- **cheirality(키랄리티)** : 3D 공간상의 점이 카메라의 앞(정상적인 시야)에 위치해야 한다는 물리적 제약 조건
- **bearing(방향벡터)** : 카메라에서 점으로 향하는 "단위 방향 화살표". 픽셀 좌표 대신 이걸로 기하를 풀면 앞·옆·뒤 360° 다 담김.
- **intrinsic 0개** : pinhole은 내부 파라미터 4개(fx,fy,cx,cy)가 필요한데, 순수 구면 카메라는 "방향=픽셀위치"가 공식으로 딱 정해져 있어 **추정할 게 없음**. → OTF가 골머리 앓던 focal 추정이 통째로 사라짐.

| 단계          | EQR에서 깨지는 지점                                                                                                                                                 |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Feature     | feature 점이 이미지 자체에서 pinhole과 달리 왜곡되기 때문에 추가적인 연산이 필요함.<br>(현재 EQR to Pinhole의 프로세스)                                                                          |
| Match       | 직선만 그릴 줄 아는 도구(F-matrix)로 곡선 제약을 측정하지 못함.                                                                                                                    |
| Bootstrap   | pixel↔각도가 위도마다 달라(세계지도 왜곡) pixel 오차가 왜곡됨.<br>→ angular(bearing) residual(pixel 잔차가 아니라 EQR의 특징에 맞는 계산) 필요.<br>추가로 intrinsic 0개(fx, fy, cx, cy)라 focal 추정 불가. |
| Incremental | Bootstrap과 같은 이유로 pixel PnP 불가함. → angular PnP로 변화해야 함.<br>추가로 전방위라 z>0 cheirality도 무의미함.                                                                    |
| Spawn       | z-depth 개념이 아니라, 구면 역투영으로 spawn을 진행해야 함.                                                                                                                     |
| Render      | **tan(FoV/2) 발산** + **EWA affine 붕괴(극·seam)** + z>0 culling이 **뒤 절반 삭제**                                                                                     |

1. Perspective 투영행렬의 부재
	하나의 4×4 matrix로 표현 불가, `tan(FoV/2)`가 ==FoV≥180°에서 발산==함.

2.  ==EWA local affine 근사가 붕괴==함.
	2D covariance는 투영의 1차 Taylor임.
	ERP Jacobian은 위도별로 격변 → **극 근처 Gaussian이 가로 전체로 번지고, ±180° seam에서 두 조각**으로 나뉨.

---

# 3. 가능은 한가?

- 2번에서 언급했듯이, 전반적인 train process는 진행할 수 있으나, Spherical한 방향으로 전 연산 과정을 재유도하면서, depth와 feature 계산에 대한 다른 방식으로 교체해야 함.

## 3.1 용어 정리
- **ERP-native rasterization** : Gaussian을 평면이 아니라 **구면(ERP)에 직접** 그리는 렌더러.
- **spherical pose (bearing 도메인)**: pose를 픽셀이 아니라 방향(각도)으로 푸는 것(= angular PnP/BA).
- **online + joint pose** : 사진 들어오는 즉시(online), pose를 미리 안 주고 같이 푸는 것.
- **native vs rig** : EQR을 그대로(native) 처리 vs 우리처럼 12조각 pinhole로 잘라서(rig) 처리.

| 부품                          | 선행연구                                                                               |
| --------------------------- | ---------------------------------------------------------------------------------- |
| ERP-native rasterization    | ODGS(NeurIPS 2024), OmniGS(WACV 2025), OP43DGS(ECCV 2024), SPaGS(EGSR 2025)        |
| Spherical pose(bearing 도메인) | OpenSfM·OpenMVG(intrinsic 0개), **COLMAP 4.1.0**(2026-06-26 native spherical)       |
| 360 depth                   | Depth Anywhere(NeurIPS 2024), UniK3D(CVPR 2025)                                    |
| **Online + joint pose**     | **ODGS-SLAM(CVPR 2026)** — ERP closed-form gradient로 tracking+mapping, 사전 pose 불필요 |

### 3.2 그러나 native가 항상 나은지는 인사이트가 더 필요함.
- ==COLMAP 4.1.0== release note : native spherical은 "faster but **less accurate** than rendering perspective views"라고 언급되어 있어, pinhole과의 trade-off가 있어 추가 인지가 필요함.
- ==FullCircle==(2026): stitched ERP 직접 학습은 화질 저하 → raw dual-fisheye를 택함.
