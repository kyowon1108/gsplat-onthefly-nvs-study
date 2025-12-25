## 1. Skyfall-GS  
  
- arXiv: 2510.15869  
- Paper: Skyfall-GS: Synthesizing Immersive 3D Urban Scenes from Satellite Images  
- Code: [https://github.com/jayin92/Skyfall-GS](https://github.com/jayin92/Skyfall-GS)  
  
### 1.1 문제 정의  
  
**위성 이미지의 문제**  
- 약한 parallax (400km 거리) → 깊이 정보 거의 없음  
- multi-date 조명 변화 (아침/정오/저녁, 계절)  
- 부동(floater) 생성  
- 건물 정면/옆면 못 봄 (occlusion)  
  
### 1.2 Skyfall-GS의 해결책  
  
**Two-Stage Pipeline**
- 논문에서는 NVIDIA RTX A6000 D6 48GB 사용.  

| Stage | 입력 | 출력 | 시간 |  
|-------|------|------|------|  
| **Stage 1** | 위성 다중 이미지 | 3DGS | ~1시간 |  
| **Stage 2** | Stage 1 GS + Diffusion | 최종 3DGS (48 FPS) | ~6시간 |  

  
---  
## 2. Stage 1 - 위성 이미지에서 초기 3DGS 재구성  
  
### 2.1 카메라 모델: RPC -> Perspective  
  
**위성의 특수성**  
- 일반 카메라: 내부/외부 파라미터를 직접 정의함.  
- 위성: **RPC(Rational Polynomial Camera)** 모델  
- 이미지 좌표 <-> 지리적 좌표를 직접 매핑함.  
- Perspective 파라미터로 근사화 필요.  
  
**Skyfall-GS 방법**  
- SatelliteSfM (Zhang et al., 2019) 사용  
- RPC -> Perspective 근사화  
- Sparse SfM points로 GS 초기화  
  
### 2.2 Appearance Modeling (Multi-date 조명)  
  
**문제**:  
- 표준 3DGS에서는 View-dependent color만 표현함.  
- 계절, 시간이 달라지는 multi-date 이미지 동시 학습 불가.  
  
**해결책**  
```  
색 변환 (Affine):  
c̃_i(r) = γ ⊙ ĉ_i(r) + β  
  
  
파라미터:  
(β, γ) = f(e_j, g_i, c̄_i)  
  
  
구성:  
- e_j: Per-image embedding (32차원, 이미지 조명)  
- g_i: Per-Gaussian embedding (24차원, 위치 기반 그림자)  
- c̄_i: 0차 SH  
- f: Lightweight MLP (2층 128 neurons)  
```  
  
**학습률**  
- e_j: 0.001 (모든 픽셀에 영향)  
- g_i: 0.005  
- f: 0.0005 (가장 느림)  
  
**SH 제한**  
- 0차, 1차만 사용  
- 고주파 view-dependent 효과(2차 이상)는 의도적으로 봉인  
- 색 변화가 기하학과 섞이지 않도록 분리   
  
### 2.3 Opacity Entropy Regularization (Floaters 제거)
  
**문제**:  
- Color loss만으로는 부동 제거 불가  
- 옥상의 Gaussian과 공중의 Gaussian 모두 색 같음  
  
**해결책**    
```  
L_op = -Σ_i [α_i log(α_i) + (1-α_i) log(1-α_i)]  
  
  
Binary Entropy 함수:  
H(α) = 0 (α=0 또는 1, 최소)  
H(α) = 1 (α=0.5, 최대)  
```  

**왜 Entropy? (다른 방법과의 비교)**:

| 방법             | 효과            | 문제               |
| -------------- | ------------- | ---------------- |
| L1 Sparsity    | 작은 α 선호 (0.1) | 중간값 (0.5) 제거 못 함 |
| L2 Sparsity    | 약한 페널티        | 중간값 제거 못 함       |
| Entropy (본 논문) | 중간값 자체를 싫어함   | α=0 또는 1 강제      |

- entropy가 floater 제거에 가장 잘 맞는 선택임. (중간값인 α를 제거)

**Loss 구성**  
```  
L_sat = L_color + λ_op * L_op + λ_depth * L_depth  
= 1.0 + 10 * L_op + 0.5 * L_depth  
```  
- λ_op = 10 (매우 큼): 가우시안 많으므로 상대적 영향 조절  
- Densification (1000~21000 iter): α < 0.01인 가우시안 자동 제거  

- “color 1 : opacity 10 : depth 0.5” 정도 비율로 세 개의 loss를 섞어서 최적화한다는 뜻.
  
### 2.4 Pseudo-camera Depth Supervision (깊이 강화)  

#### 2.4.1 Pseudo-camera 위치 설정  
  
```  
Look-at point (Random):  
- (x, y, 0): x, y ~ N(0, 128)  
- 도시 중심 근처 정규분포  
  
  
카메라 배치 (Orbital):  
- Azimuth: 균등분포 [0, 2π)  
- Elevation: 80° -> 45° (선형 감소)  
- Radius: 300 -> 250 units (선형 감소)  
  
  
샘플링:  
- 매 10 iteration마다  
- 24개 카메라  
- Iteration 1000~21000  
- 총 ~3,000회  
```  
  
**Elevation 점진적 감소의 의미**:  
```  
초기(80°): 거의 위성에 가까운 높은 각도 -> GS가 이미 잘 맞추는 구간에서 시작 -> 안정적인 depth 감독
중간(65°): 점점 옆에서 보는 뷰 추가 -> 평면/건물 높이 패턴을 더 잘 배우게 됨.
후반(45°): 약간 낮은 각도 -> Stage 2에서 더 낮은 각도로 내려가기 전 준비 단계

```  

#### 2.4.2 Depth Rendering + MoGe  
  
**GS 렌더**:  
```  
RGB: 1024×1024 이미지  
Depth: α-blended depth map  
D̂_GS = Σ α_i * depth_i (앞에서 뒤로)  
```  
 
**MoGe (Monocular Geometry Estimator)**:  
- Pre-trained 단안 기하 모델 (CVPR 2025, Wang et al.)  
- GS로 렌더한 RGB 이미지 입력 -> scale-invariant depth D̂_est 출력
- "절대 깊이는 모르지만 상대 패턴은 추정"  
  
#### 2.4.3 Depth Loss (Pearson Correlation)

```  
L_depth = ||PCorr(D̂_GS, D̂_est)||_1  
  
  
PCorr(A, B) = Cov(A, B) / √[Var(A) × Var(B)]  
∈ [-1, +1]  
```  

**왜 절대값이 아닌 상관관계?**

| 요소     | 문제                             |
| ------ | ------------------------------ |
| MoGe   | 단안 깊이 (한 이미지), Scale-invariant |
| GS 렌더  | 실제 지상과 거리 다를 수 있음              |
| **해결** | **패턴만 비교** (스케일 무관)            |
  
### 2.5 Stage 1 파라미터 및 최적화  
  
**3DGS 수정**  

| 파라미터                   | 표준     | Skyfall-GS | 이유                 |
| ---------------------- | ------ | ---------- | ------------------ |
| Scaling LR             | 0.005  | 0.001      | 오버헤드 뷰 과도 신장 방지    |
| Densify grad threshold | 0.0002 | 0.0001     | 근거리 정보 부족          |
| Max covariance         | -      | 20         | 큰 가우시안(부동처럼 보임) 제거 |
| Densify range          | -      | 1000~21000 | 초반 안정, 후반 미세 정제    |

- Scaling LR : 줄여서 geometry가 과도하게 부풀어 오르지 않게 막는다.
- Densify grad threshold :  낮춰서 조금만 gradient가 있어도 새 가우시안을 추가해주겠다.
- Max covariance : 일정 크기 이상으로 커진 Gaussian은 제대로 된 surface라기보다는 노이즈일 확률이 높다 라고 보고 잘라버린다.
- Densify range : 1000~21000 iteration 구간에서만 적극적으로 가우시안을 추가/삭제한다. 이후에는 주로 파라미터 미세 조정만 (scale/opacity/color 조정) 한다.

---  
## 3. Stage 2 - Curriculum 기반 Iterative Refinement (합성)

### 3.1 Curriculum Learning Strategy  
  
```  
구성:  
N_e = 5 Episodes  
각 Episode: 10,000 iterations  
총: 50,000 iterations  
  
  
Look-at Points:  
- DFC2019: 3×3 grid (N_p=9)  
- GoogleEarth: N_p=16  
  
  
카메라 (per Look-at point):  
- N_v = 6 cameras  
- N_s = 2 samples (Multi-sample)  
  
  
Elevation 변화 (선형):  
- Episode 1: 85°  
- Episode 2: ~75°  
- Episode 3: ~65°  
- Episode 4: ~55°  
- Episode 5: 45°  
  
  
Radius 변화 (DFC2019):  
- 초기: 300 units  
- 최종: 250 units  
  
  
렌더 해상도: 2048×2048  
```  

**Curriculum의 의미**:  
```  
높은 고도부터 시작:  
└─ GS가 이미 잘 배운 구간 (위성) -> 높은 품질  
  
  
점진적으로 낮춤:  
└─ 어려운 각도 점진적 도입  
└─ 기하학 구조 보호  
```  

### 3.2 Render Refinement: FlowEdit + FLUX.1  
  
**Diffusion 모델**:  
- FLUX.1 [dev]: 12B params, Flow Matching 기반 Pre-trained 모델
- FlowEdit: Inversion-free image editing  
- FLUX.1 [dev] 모델을 가져다 쓰고 거기에 FlowEdit 방법을 적용해서 GS 렌더 이미지를 정제함.

**Prompt Pairs**  
  
```  
Source:  
"Satellite image of an urban area with modern and older  
buildings, roads, green spaces. Some areas appear distorted,  
with blurring and warping artifacts."  
  
  
Target:  
"Clear satellite image of an urban area with sharp buildings,  
smooth edges, natural lighting, and well-defined textures."  
```  

**FlowEdit 파라미터**  
```  
n_min = 4 : 얼마나 “적게” 노이즈를 섞고 시작할지
n_max = 10 : 얼마나 “많이” 섞을 수 있는지
cfg_source = 1.5 : source prompt 영향 (현재 상태 유지)
cfg_target = 5.5 : target prompt 영향 (깨끗한 쪽으로 밀기)
steps = 28 : FLUX.1 denoising step 수
```  

### 3.3 Multi-sample Diffusion  
  
**목적**: 각 뷰 간 3D 일관성 강화  

```  
같은 GS 렌더에 대해 N_s=2회 Diffusion:  
├─ FlowEdit+FLUX.1 (seed=0) -> I_diff_1  
└─ FlowEdit+FLUX.1 (seed=1) -> I_diff_2  
  
  
Loss:  
L_color = (1/2) × (||I_r - I_d1||² + ||I_r - I_d2||²)  
  
  
효과:  
└─ 두 이미지의 평균 패턴으로 수렴  
└─ Hallucination 회피  
└─ 3D 일관성 강화
```  
  
### 3.4 Iterative Dataset Update(IDU) 루프  

**한 번의 Iteration**:  
  
```  
Step 1: 렌더  
├─ Curriculum elevation에서 카메라 샘플  
├─ Stage 1 GS -> RGB 렌더 + Depth  
  
  
Step 2: Diffusion 정제 (Multi-sample)  
├─ FlowEdit+FLUX.1 (N_s=2)  
└─ 약 6초/iteration  
  
  
Step 3: Loss 계산  
├─ L_color: 렌더 vs 정제 이미지  
├─ L_depth: Depth correlation  
└─ L_IDU = L_color + 0.5 * L_depth  
  
  
Step 4: GS 업데이트  
├─ Backpropagation  
├─ Opacity regularization
└─ 다음 iteration  
```  
  
**Opacity Regularization 비활성화**  
```  
Stage 1에서는 opacity entropy + pruning으로 floater를 강하게 정리함.

하지만 Stage 2에서는
이미 Multi-view 관찰 + Diffusion 기반 consistency가 있어서 굳이 entropy 강제까지 할 필요가 줄어듦

대신, 유리/반투명 같은 구조를 표현하려면 α가 중간인 것도 어느 정도 허용해야 함
-> L_op를 완전히 비활성화
```  
  
**데이터 샘플링 전략**  
```  
각 Episode 학습 이미지:  
├─ 75%: Diffusion으로 정제한 이미지 (신규 감독)  
└─ 25%: 위성 원본 이미지 (의미론적 일관성)  
    
효과:  
└─ Diffusion 이미지가 위성과 의미 일치  
└─ 과도한 hallucination 방지  
```  

### 3.5 Stage 2 Loss 및 최적화  

**Loss 함수**:  
```  
L_IDU = L_color + λ_depth * L_depth  
= 1.0 + 0.5 * L_depth  
```  
  
  
**Stage 1과의 비교**:  
```  
Stage 1:  
L_sat = L_color + λ_op * L_op + λ_depth * L_depth  
= 1.0 + 10 * L_op + 0.5 * L_depth  
  
Stage 2:  
L_IDU = L_color + λ_depth * L_depth  
= 1.0 + 0.5 * L_depth  
(L_op 제거)  
```  
  
### 3.6 Stage 2 최종 결과  
  
**학습**: 5 episodes × 10K iter = 50K iter ≈ 6시간  

**최종 GS 특성**: 

| 항목       | 위성 시점 (85°) | 지면 시점 (45°) |
| -------- | ----------- | ----------- |
| 기하학      | 정확 (유지)     | 완성          |
| 텍스처      | 완벽          | 포토리얼        |
| Floaters | 제거          | 제거          |

**성능**:  
- T4 GPU: 11 FPS  
- RTX A6000: 48 FPS  
- MacBook Air M2: 40 FPS  
  
  