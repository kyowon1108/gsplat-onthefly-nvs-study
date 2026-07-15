# 0. 용어 정리 & 원본 OTF ↔ 리팩토링 rig 비교 (260708 기준으로 리팩토링 진행중)

## 0.1 용어 정리

| 용어                                  | 뜻 (한 줄)                                                                                            |
| ----------------------------------- | -------------------------------------------------------------------------------------------------- |
| EQR (equirectangular)               | 360° 파노라마를 경도·위도로 직사각형에 편 표현                                                                       |
| virtual pinhole rig (zero-baseline) | EQR 한 장을 **N개 가상 핀홀 뷰**로 쪼갠 것. N뷰가 한 광학중심 공유 → 뷰 간 이동(baseline)=0                                  |
| rel_R·focal 기지주입                    | 뷰 간 상대회전·초점거리를 추정 안 하고 **기지값으로 주입** → 미지수 `6N+f → 6`                                               |
| pooled Wahba                        | 여러 뷰 대응을 모아 회전 `R`을 한 번에 푸는 closed-form(회전평균 계열)                                                   |
| t-only PnP                          | `R` 고정 후 위치 `t`만 선형으로 푸는 pose 추정                                                                   |
| cross-ts triangulation              | 같은 timestep 뷰끼리는 baseline=0이라 금지, **서로 다른 timestep** 뷰로만 삼각측량                                      |
| scale gauge                         | monocular라 절대 크기 미정 → 인접 이동 median을 0.1로 고정                                                        |
| native-spherical vs pinhole-rig     | EQR을 구면 그대로 처리(native) vs N개 핀홀로 잘라 처리(rig)                                                        |
| resampling loss                     | EQR→pinhole(grid_sample)→render **이중 보간**으로 고주파 텍스처 뭉개짐                                            |
| pole EWA 붕괴                         | 극(pole) 방향에서 Gaussian 투영 근사가 무너져 가로 번짐·seam 찢김                                                     |
| confidence                          | 예산 배분 신호. need=더 학습?, trust=supervision 믿을만?, utility=depth/pose에 도움?, ==현재 이 부분에 대해 좀 더 리서치가 필요== |
| transverse-parallax depth-utility   | 회전으로 설명 안 되는 cross-view 잔차 = 실제 parallax = **depth 관측 가능성**                                        |

## 0.2 원본 OTF → 리팩토링 OTF-rig (무엇을 왜 바꿨는가)

| 단계                | 원본 OTF                   | 리팩토링 OTF-rig                        | 판정                                                       |
| ----------------- | ------------------------ | ----------------------------------- | -------------------------------------------------------- |
| 입력 단위             | 프레임 1장                   | **12뷰 packet**                      | rig 필연                                                   |
| 회전 초기화            | F-matrix RANSAC          | **pooled Wahba**                    | zero-baseline서 F 퇴화 → 대체                                 |
| 포즈                | P4P (R,t 동시)             | **Wahba R + t-only PnP**            | 회전 강관측 → 위치만                                             |
| **포즈 정련(miniBA)** | n_ts=1 점고정 20iter (~4ms) | **6-ts 윈도우 joint BA, 점 최적화 60iter** | 현재 miniBA쪽에서 난황 겪는 중. 시간이 굉장히 오래 걸리고 품질에도 영향을 줌.         |
| scale             | median 0.1 정규화           | 동일 + freeze-ts0 + z-ref             | timestep0을 무조건 기준으로 다음 timestep을 배치, 이후 scale을 normalize |
| 깊이                | 이웃 프레임                   | **cross-ts만** (같은 ts baseline 0)    |                                                          |
| focal/rel_R       | 추정                       | 이미 알고 있음. 직접 주입함.                   | EQR to pinhole 과정에서 rotation과 camera parameter이 고정됨.     |
| 최적화               | 30iter joint             | 270iter, shared rig pose            | 현재 iteration을 조절해나가는 방식으로 최종 품질과 시간 trade off 측정중        |
| anchor/window     | 프레임 단위                   | **packet 단위**                       |                                                          |
- 현재 Incremental 파트에서 새 timestep이 등록되기 위한 miniBA 부분에서 연산이 너무 많이 들어, 해당 부분에 대한 방법 고찰중.

---

# 1. native vs pinhole 언제, 왜 우위가 갈리는가

![OB3D EQR 왜곡 특징](video_picture/260702/ob3d_explain.png)
- OB3D Dataset 예시 : ==극(바닥)=가로로 늘어남==, ==좌·우 끝=같은 곳(wrap)==, ==적도 부근=왜곡 최소==.


### 메커니즘 가설
- 같은 360 입력을 EQR **native**(안 자르고 구면 그대로) vs **pinhole-rig**(N개 평평한 사진으로 잘라서) 넣어 novel view 화질 비교.

#### EQR native가 이기는 경우 : 무늬 많은 scene (고주파 scene)

|     | 무슨 일                | 직관                                                                                                        |
| --- | ------------------- | --------------------------------------------------------------------------------------------------------- |
| 원인  | ==resampling loss== | pinhole-rig는 EQR을 자를 때 픽셀 격자가 안 맞아 **평균내서(이중 보간) 채움** → 잘잘한 무늬(고주파)가 뭉개짐 (한 픽셀 정도로 고주파가 뭉개지는 것은 합당하지 않다.) |
| 결과  | **native 우위**       | native는 안 자르니 뭉갬 0 → 벽돌·잔디·카펫 등 **텍스처 풍부 씬**에서 선명함                                                        |

#### EQR native가 지는 경우 : 극(천장/바닥) scene

|     | 무슨 일               | 직관                                                                                              |
| --- | ------------------ | ----------------------------------------------------------------------------------------------- |
| 원인  | ==극 EWA 붕괴==       | 방울을 2D 타원으로 근사하는데 EQR **극(위·아래)** 은 가로로 늘어나 근사가 깨짐 → 번지거나 seam에서 찢김, 이를 극복하기 위한 추가 연산 프로세스가 필요함 |
| 결과  | **pinhole(우리) 우위** | 극을 **똑바른 up/down 크롭**으로 따로 떠서 안 찌그러짐 → **천장·바닥 콘텐츠 많은 씬**에서 앞섬                                  |

---
# 2. pinhole은 lock이 아니라 real-time 위한 choice?

- **COLMAP 4.1.0**(2026-06) : spherical(EQR) 카메라 모델을 추가하며 릴리스노트에 *"generally **faster but less accurate** than rendering perspective views, as performed in the panorama_sfm example"*  (이전에 보고한 12 view로 쪼개는 `panorama_sfm`임.)
	==문서에 기재된 트레이드오프 판단이 우리 설계와 일치함== ([release](https://github.com/colmap/colmap/releases/tag/4.1.0))

→ "native가 항상 낫다"가 거짓이므로, pinhole 선택은 **명분 있는 real-time 최적화**이지 회피가 아님.

---
# 3. ODGS-SLAM study
 - **CVPR 2026**(pp.26114–26123). ([project](https://odgs-slam.github.io/) · [CVF](https://openaccess.thecvf.com/content/CVPR2026/html/Spiss_ODGS-SLAM_Omnidirectional_Gaussian_Splatting_SLAM_CVPR_2026_paper.html))
- **360 비디오 스트림으로 실시간 카메라 궤적 + 3D Gaussian 지도를 만드는 direct 3DGS-SLAM** (= perspective용 MonoGS를 EQR로 옮긴 것).

![EQR projection model — 3D 방향 → 구면 → ERP 픽셀](video_picture/260708/eqr_projection_model.png)
- ODGS-SLAM은 Gaussian을 pinhole 평면이 아니라 **이 EQR(구면) 위에 직접** splat하고, 그 투영의 미분(gradient)을 유도해 rasterizer에 심어 pose를 렌더로 갱신함.

### 흐름 용어

| 용어                            | 뜻                                                                                |
| ----------------------------- | -------------------------------------------------------------------------------- |
| SLAM                          | 카메라가 움직이며 **동시에** 위치(tracking)+지도(mapping)를 만드는 것. 실시간·순차                        |
| direct(=photometric) tracking | feature 매칭 없이 **렌더를 실제 이미지에 맞춰** pose를 gradient로 갱신함.                            |
| closed-form gradient          | EQR 투영의 미분을 손으로 유도해 rasterizer backward에 심음<br>= ==rasterizer 수술==               |
| latitude weighting            | EQR loss를 cos(위도)로 가중해 극 과대가중 보정 (EQR을 직접 넣어서 필요)                                |
| keyframe removal              | 쌓인 keyframe을 covisibility 그래프로 쳐내 메모리 절감 (back-end pruning)                      |
| ATE / scale-drift             | ATE : 궤적 위치 오차(tracking 정확도).<br>scale-drift : 절대 크기 미관측으로 오차 누적(RGB·outdoor 취약) |

### 흐름이 OTF와 어떻게 다른가

| 단계       | ODGS-SLAM                                          | 우리 OTF-Rig                                                        |
| -------- | -------------------------------------------------- | ----------------------------------------------------------------- |
| 입력       | EQR 프레임 (RGB/RGBD)                                 | EQR → **N개 pinhole packet**                                       |
| 매칭       | ==없음 (featureless)==                               | XFeat 매칭                                                          |
| pose 추정  | ==photometric: 렌더 vs 이미지 → EQR gradient로 pose 직접== | ==feature: PnP+mini-BA로 pose 먼저==, render는 정련/fallback            |
| 왜곡 처리    | EQR gradient + 위도 가중 (수술)                          | pinhole crop이라 **불필요 (무수술)**                                      |
| 지도 splat | Gaussian → EQR 직접                                  | Gaussian → pinhole                                                |
| 효율/메모리   | keyframe removal                                   | - anchor offload (active window)<br>- confidence-budget (구현해야 함.) |
| 성격       | tracking+mapping 통합 direct SLAM                    | 등록(가벼움) + render 정련 **분리**                                        |

| 렌즈                | ODGS-SLAM                                          | 우리(OTF-Rig)                                               |
| ----------------- | -------------------------------------------------- | --------------------------------------------------------- |
| projection        | EQR 직접 미분(closed-form gradient, ==rasterizer 수술==) | EQR→12 virtual pinhole (**rasterizer 무수술**)               |
| 효율 레버             | **keyframe removal(메모리)**, confidence-budget 아님    | **confidence**로 iter/spawn/MVS/cap 배분                     |
| real-time latency | 논문에 latency에 대한 future work가 필요하다고 기재되어 있음.        | virtual pinhole 유지 + confidence budget으로 real-time성 개선 목표 |
| rig-pinhole       | EQR 직접                                             | method core가 pinhole packet                               |

![ODGS-SLAM per-frame latency (paper Table 6)](video_picture/260708/odgs_slam_latency.png)
- ==track 1.4–1.7s · map 2.3–2.8s (프레임당)==로 ~1s streaming budget 초과 → 논문도 latency를 future work로 명시함.

- 화질 : ODGS-SLAM ~28–29 PSNR로 **comparable** → **tracking ATE는 우위, mapping은 comparable**. outdoor RGB는 scale-drift로 실패.
- 논문 주장 : *"the **first** omnidirectional SLAM using 3DGS for tracking and mapping"*
- **결론** : confidence에 대한 novelty는 현재 존재하지 않기 때문에, =="ODGS-SLAM이 EQR을 미분 가능 rasterizer로 흡수한다면, 우리는 EQR을 미분 불필요한 pinhole rig로 분해한다."== 라는 방향으로 나아 가야 함. (좀 더 토의 필요)

---

# 4. 우리 스탠스 · novelty

![360° GS landscape: rasterizer × pose regime](video_picture/260708/positioning_landscape.png)
- ==online + pinhole + zero-baseline confidence== 

**[PFGS360](https://arxiv.org/abs/2603.23324)**: **offline pose-free EQR-native**(unposed 360 video, Gaussian 내부 depth로 pose). causal-online은  아님.

**생각하는 novelty 문장**
> ODGS-SLAM이 EQR을 미분가능 rasterizer로 흡수하고, 2512.08498이 **real-baseline** rig에서 다른 카메라의 삼각측량으로 예산을 깎는다면?
> 우리는 EQR을 **zero-baseline** virtual pinhole rig로 분해하고, 회전으로 설명 안 되는 cross-view 잔차(**transverse-parallax depth-utility**)를 ==confidence로 정의해(방법 모색 필요)==, **깊이가 원리적으로 결핍되는 영역에만 iteration·Gaussian 예산을 몰아주는** online 자원최적화 프레임워크

---
## 참고문헌

| 항목                                    | 링크                                                                                                                                                                                            |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 원본 On-the-Fly NVS (SIGGRAPH/TOG 2025) | arXiv:2506.05558                                                                                                                                                                              |
| OB3D 벤치마크                             | arXiv:2505.20126                                                                                                                                                                              |
| ODGS-SLAM (CVPR 2026)                 | [odgs-slam.github.io](https://odgs-slam.github.io/) · [CVF](https://openaccess.thecvf.com/content/CVPR2026/html/Spiss_ODGS-SLAM_Omnidirectional_Gaussian_Splatting_SLAM_CVPR_2026_paper.html) |
| multi-cam rig OTF (최대 위협)             | [arXiv:2512.08498](https://arxiv.org/abs/2512.08498)                                                                                                                                          |
| PFGS360 (offline pose-free)           | [arXiv:2603.23324](https://arxiv.org/abs/2603.23324)                                                                                                                                          |
| COLMAP 4.1.0 (native spherical)       | [release](https://github.com/colmap/colmap/releases/tag/4.1.0)                                                                                                                                |
