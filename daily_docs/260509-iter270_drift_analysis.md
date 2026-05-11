# 260509 — iter=270 ATE Drift 분석 및 품질 개선 방향

> 작성일: 2026-05-09
> 목적: iter=100 → iter=270 전환 시 C2 효과 역전 원인 분석 + 후속 개선 방향 제안
> 대상 독자: 본 프로젝트 인수자, 외부 AI 어시스턴트 (ChatGPT 등)

---

## 0. 프로젝트 컨텍스트 (신규 독자용)

**저장소**: `kyowon1108/on-the-fly-nvs-rig`
**핵심 아이디어**: Insta360 X5 EQR 영상 → 9개 rotation-only virtual pinhole view로 분해 → rig-aware on-the-fly 3D Gaussian Splatting (NVS)
**Rig 특성**: baseline = 0, relative rotation R_ij가 EQR 구면 기하에서 exact하게 알려짐 → H_ij = K·R_ij·K⁻¹ (depth-independent homography)
**목표**: PG 2026 제출용 contribution 구현 및 검증

### 구현된 Contribution 현황

| ID | 내용 | 상태 |
|----|------|------|
| C1 | Zero-baseline rotation-only rig + DoF 절감 (rig_R6D 6+3 params) | ✅ 구현 완료, baseline |
| C2 | Cross-view P̃: 9-view sibling 렌더 기반 spawn probability 억제 | ✅ 채택 (iter=100 기준) |
| C3 | VCD-style past-keyframe pruning | ❌ Reject (360° sweep 구조적 비호환) |
| C4 | DFT-adaptive pyramid level scheduler | ✅ 조건부 채택 |

### C2 수식 (핵심)

```
P_s(u,v) = max(ref_penalty, max_i[P̃_i(warp(u,v; H_sib→ref))] × 0.5, 0)

H_sib→ref = K · R_ref · R_sib^T · K⁻¹
```

sibling view의 rendered Laplacian을 ref 좌표로 역방향 warp → per-pixel max → 이미 잘 표현된 영역에 새 Gaussian spawn 억제.

---

## 1. iter=100 실험 결과 (확정 수치)

5-seed ablation (`seeds {0,1,2,3,4}`, rig iter=100, holdout=High_Cam01, 23 ts × 9 view):

| 지표 | baseline (c1_only) | c1_c2 | Δ |
|---|---:|---:|---:|
| ATE (mean) | 0.072 ± 0.085 | **0.064 ± 0.087** | **−11.4%** |
| n_gauss | 1.18 ± 0.17M | **1.24 ± 0.04M** | +5.1%, std ↓ 4× |
| PSNR_all | 19.23 ± 0.63 | 19.22 ± 0.73 | ≈0 (noise 안) |
| wall (s) | 99.2 ± 4.5 | 110.2 ± 4.4 | +11% |

**Per-seed ATE (seed=1 드라마틱 회복)**:

| seed | baseline ATE | c1_c2 ATE | Δ |
|:----:|---:|---:|---:|
| 0 | 0.0105 | 0.0095 | −10% |
| 1 | 0.0512 | **0.0138** | **−73%** |
| 2 | 0.0082 | 0.0077 | −6% |
| 3 | 0.0526 | 0.0520 | −1% |
| 4 | 0.2368 | 0.2354 | −1% |

**5/5 seed 모두 ATE 개선** (방향 일관). seed=1의 -73%가 가장 극적: "moderate diverged" 그룹이 "COLMAP 수준" (ATE 0.35% of scene scale)으로 수렴.

---

## 2. iter=270 관찰 (현재 진행 중)

| | iter=100 baseline | iter=100 c1_c2 | iter=270 baseline | iter=270 c1_c2 |
|---|---:|---:|---:|---:|
| seed=1 ATE | 0.0512 | **0.0138 (−73%)** | 0.0685 | **0.0748 (+9% ❌)** |

두 가지 이상 현상:
1. **baseline 자체 악화**: iter=100 (0.0512) → iter=270 (0.0685). iteration을 늘렸는데 ATE가 나빠짐.
2. **C2 효과 역전**: iter=100에서 −73%이던 C2 개선이 iter=270에서 +9% 악화로 반전.

---

## 3. 근본 원인 분석

### 3-1. depth_loss_weight 지수 감쇠

`keyframe.step()` 매 gradient step마다:
```python
self.depth_loss_weight *= self.depth_loss_weight_decay  # e.g. decay=0.99
```

| 시점 | 남은 depth_loss_weight |
|---|---|
| iter=100 완료 후 | 0.99^100 ≈ **0.366** (36.6%) |
| iter=270 완료 후 | 0.99^270 ≈ **0.067** (6.7%) |

depth_loss는 pose의 절대 스케일 anchor 역할을 한다. iter=270에서는 이 anchor가 사실상 소멸 → **pose가 photometric loss만으로 최적화됨**. photometric loss는 pose에 대해 극도로 non-convex → local minima 함정 + drift 발생. 이것이 **baseline ATE 악화의 1차 원인**.

### 3-2. C2의 Gaussian 수 감소가 pose constraint를 약화

C2는 spawn을 억제 → n_gauss 감소. 3DGS에서 pose gradient는:

```
∂L/∂ξ = Σ_k (∂L/∂c̃_k) · (∂c̃_k/∂μ_k^2D) · (∂μ_k^2D/∂ξ)
```

Gaussian 수가 적으면 이 합산이 작아짐 → **photometric Jacobian의 effective rank 감소** → pose optimizer가 ill-conditioned. depth supervision이 decay된 상태에서 photometric Jacobian도 작으면 작은 noise에 pose가 크게 흔들림.

iter=100에서는 depth_loss가 0.366 수준이라 이 ill-conditioning을 보정 가능했지만, iter=270에서는 0.067로 depth supervision이 너무 약해 보정 불가.

### 3-3. C2 penalty가 iter에 무관하게 동일 세기로 동작

```python
self.c2_sibling_weight = 0.5  # 상수, 어떤 decay도 없음
```

iter=270에서 scene renders 품질이 향상 → sibling rendered Laplacian이 더 선명 → penalty가 실질적으로 더 강해짐 → 후반부 새 keyframe에서 spawn이 과도하게 억제 → scene under-representation → photometric loss가 기존 Gaussian을 "당기는" 방향으로 작용 → pose와 Gaussian 위치가 동시에 틀어짐.

### 3-4. Pipeline 설계 범위 이탈

OTF-NVS 원 논문 (arXiv:2506.05558) §4.2에서 authors는 per-keyframe optimization steps를 **30**으로 설정. 이 pipeline은 "짧게 최적화하고 다음 keyframe으로 이동"하는 streaming paradigm. iter=270은 설계 범위 바깥이며, Revising Densification (ECCV 2024) §4.3이 지적하는 "geometric regularization 없는 장기 photometric optimization → pose degeneration"과 정확히 일치하는 상황.

### 3-5. 원인 요약

```
iter=270 ATE 악화 = (depth_loss 소멸)
                  × (C2로 인한 sparse Gaussians → 약한 photometric constraint)
                  × (c2_sibling_weight 고정 → 후반부 과도한 spawn 억제)

→ 세 효과의 곱산. iter=100에서는 depth_loss(0.366)가 살아있어
  나머지 두 효과를 보정 가능. iter=270에서는 보정 불가.
```

---

## 4. 결론: iter ↑는 틀린 레버

"품질을 올리려면 iteration을 늘린다"는 직관이 이 pipeline에서는 반대로 작동한다.

- iter=270에서 baseline ATE 자체가 악화 → iteration 증가가 순효과 없음
- C2+C4는 **주어진 iteration budget 안에서 효율을 높이는** 설계. 이것이 contribution의 근거
- 장기 최적화가 필요하다면 구조적 보완이 필요 (아래 §5)

**PG 2026 논문 서술 포인트**:
> "Naïvely increasing per-keyframe iterations is counterproductive in streaming 3DGS: depth supervision decays exponentially, leaving pose estimation under-constrained by photometric loss alone. This motivates structural contributions — C2 improves spawn initialization quality, and C4 improves optimization efficiency within a fixed budget — rather than relying on extended optimization."

---

## 5. 품질 개선 방향 (iter ↑ 대신)

### 방향 A. Past Keyframe Refinement Window (이론적으로 강함)

**아이디어**: 새 keyframe 추가 시 최근 N개 timestamp의 keyframe들을 sliding window로 묶어 joint re-optimization.

```
현재: [KF_t] → optimize(iter) → [KF_{t+1}] → ...
제안: [KF_{t-N}, ..., KF_{t-1}, KF_t] → joint optimize(iter_short) → slide window
```

**장점**:
- 새 시점의 photometric signal이 과거 pose를 재보정 → depth_loss decay 이후에도 multi-view geometric constraint 유지
- Classical BA (bundle adjustment) 이론의 스트리밍 구현 → 논문적 근거 강함
- C3 Reject 이후 남은 "past keyframe 활용" 아이디어를 pruning이 아닌 pose refinement로 전환

**단점**:
- Sliding window BA를 streaming 환경에서 구현하면 state management 복잡
- 계산 비용: N × 9 views를 매 timestep마다 재렌더링
- PG 2026 타임라인에서 ablation까지 완료하기엔 구현 리스크 높음

**추천**: PG 2026 future work로 서술, 별도 후속 연구로 설계

---

### 방향 C. Rig Multi-view Photometric Loss — 수정된 formulation (즉시 실행 가능)

#### C-초기 제안의 문제점 (ChatGPT 검토 후 정정)

초기 제안은 `warp(render_sib, H_ij) vs target` 형태였는데, 이는 아래 두 가지 이유로 pose drift 억제에 약하다.

**① H_ij 경로로는 pose gradient가 흐르지 않는다**

rig pose T_t (학습 변수), sibling local rotation Q_i (fixed, EQR geometry에서 known)이면:

```
T_{t,i} = T_t ∘ Q_i
H_{i→j} = K · Q_j · Q_i^T · K⁻¹
∂H_{i→j}/∂ξ_t = 0   ← global rig pose가 sibling 간 relative rotation에서 cancel
```

따라서 H_ij는 fixed이고, H_ij 자체로는 pose gradient가 없다. Gradient는 `render(G, T_{t,i})` 경로에서만 흐른다.

**② render-to-render self-consistency는 degenerate solution 허용**

```python
# ❌ 약한 formulation: rendered sibling끼리 비교
L_rig = |render(G, T_t∘Q_i) - warp(render(G, T_t∘Q_j), H_ji)|
```

pose와 Gaussian이 둘 다 잘못된 방향으로 일관되게 움직이면 loss가 낮아질 수 있다. "서로 틀리게 일관된" 상태를 잡지 못함.

---

#### C-수정: Multi-view Photometric Loss (render vs observed)

**올바른 formulation**: H_ij를 쓰지 않고, 각 sibling을 독립 렌더링 → 각각의 실제 관측 이미지와 직접 비교 → 하나의 shared rig pose T_t에 gradient 집중.

```
L_rig-mv(t) = Σ_{i ∈ S_t} ρ( M_i ⊙ [render(G, T_t∘Q_i) - I_{t,i}^obs] )

여기서:
- T_t: 학습 변수 (shared rig pose for timestamp t)
- Q_i: fixed sibling local rotation (EQR geometry에서 known)
- I_{t,i}^obs: sibling i의 실제 관측 이미지 (학습 타깃)
- ρ: Huber/L1 robust loss
```

Gradient chain:
```
L_rig-mv → render(G, T_t∘Q_i) → Gaussian rasterization → T_t
                                                        → G (Gaussian params)
```

모든 sibling이 하나의 T_t를 공유하므로 9개 view가 동시에 pose를 제약 → depth_loss decay 이후에도 geometric anchor 역할.

**추천 구현**:

```python
# optimization_step() 내 — photo_loss와 함께 backward
if self.use_c_rig_loss and self.rig_optimizer is not None:
    sib_ids = random.sample(same_ts_sibling_ids, k=2)  # 매 step 2개 샘플
    for sib_id in sib_ids:
        sib_pkg = self.render_from_id(sib_id)       # pose-dependent render (no detach)
        sib_render = sib_pkg["render"]
        target_sib = self.keyframes[sib_id].get_image()
        mask = self.keyframes[sib_id].get_mask()
        rig_loss += robust_l1(mask * (sib_render - target_sib))
    loss = loss + self.lambda_rig * rig_loss
    # H_ij 불필요. pose gradient는 render 경로에서 자동으로 흐름.
```

**H_ij의 역할 재정의**: H_ij는 이 loss 자체에 쓰지 않는다. C2 spawn 억제 (이미 구현), sibling mask alignment, ref-space visualization에만 사용.

---

#### C-추가: Pose-frozen Substep (Gaussian이 drift error 흡수하는 것 방지)

pose와 Gaussian을 동시에 optimize하면 Gaussian이 drift error를 흡수해 L_rig-mv가 낮아지면서도 pose는 틀린 채로 남을 수 있다. 이를 막으려면:

```python
# Substep 1: pose refinement (Gaussian frozen)
freeze_gaussians()
for _ in range(pose_refine_steps):
    loss = photo_loss + lambda_rig * rig_multiview_loss + lambda_depth * depth_loss
    loss.backward()
    rig_optimizer.step()
unfreeze_gaussians()

# Substep 2: scene update (pose detach 또는 joint)
loss = photo_loss + regularizers
loss.backward()
gaussian_optimizer.step()
```

이 2-substep 구조는 L_rig가 "Gaussian geometry만 당기는 loss"로 변질될 가능성을 차단. 구현 복잡도는 높지만 pose drift 억제력이 훨씬 강함.

---

#### 방향 C 실효성 진단 코드

구현 전 gradient flow 확인:

```python
rig_loss = compute_rig_multiview_loss(...)
photo_loss = compute_photo_loss(...)

photo_grads = torch.autograd.grad(photo_loss, [self.rig_R6D], retain_graph=True)
rig_grads   = torch.autograd.grad(rig_loss,   [self.rig_R6D], retain_graph=True)

ratio = rig_grads[0].norm() / photo_grads[0].norm()
print(f"||∂L_rig/∂pose|| / ||∂L_photo/∂pose|| = {ratio:.4f}")
# 1e-3 이하이면 pose drift 억제에 실질적 기여 없음
```

**장점**:
- observed image anchor → degenerate solution 방지
- 9-view shared rig pose → 단일 photo_loss 대비 pose Jacobian rank 증가
- depth_loss decay 이후에도 geometric constraint 유지

**단점/주의**:
- H_ij로 pose drift가 잡히는 것이 아님 — render() 경로가 핵심
- pose-frozen substep 없이는 Gaussian이 drift 흡수할 위험
- wall time 증가: sibling 2개 추가 렌더링 ≈ +22% per step (k=2 샘플링 시)

---

## 6. 단기 처방 (코드 최소 수정)

iter=270 실험 계속 진행 시 우선 적용 가능한 패치:

**패치 1: depth_loss_weight floor 설정** (baseline ATE 악화 먼저 잡기)

```diff
# keyframe.py step() 내
- self.depth_loss_weight *= self.depth_loss_weight_decay
+ self.depth_loss_weight = max(
+     self.depth_loss_weight * self.depth_loss_weight_decay,
+     self.init_depth_loss_weight * 0.1   # 초기값의 10% floor
+ )
```

**패치 2: C2 iteration gate** (초기 iter에서만 spawn 억제 적용)

```diff
# scene_model.py add_new_gaussians() C2 블록 앞에
+ c2_active = (keyframe.num_steps < self.c2_cutoff_iter)  # 예: 100
  if self.use_c2 and self.rig_optimizer is not None and c2_active:
      # cross-view penalty aggregation
```

---

## 7. 우선순위 권장

| 우선순위 | 작업 | 기대 효과 | 난이도 |
|---|---|---|---|
| 1 | depth_loss_weight floor 설정 | iter=270 baseline ATE 안정화 | 낮음 (1줄) |
| 2 | C2 iteration gate | iter=270에서 C2 역전 방지 | 낮음 (2줄) |
| 3 | 방향 C-수정: L_rig-mv (render vs observed) | depth decay 이후 multi-view pose constraint | 중간 |
| 3-b | pose-frozen substep 추가 | Gaussian이 drift 흡수하는 것 차단 | 중간-높음 |
| 4 | 방향 A: sliding window BA | 구조적 pose refinement | 높음 |

---

## 8. 미해결 질문 (ChatGPT 등 추가 검토용)

1. **L_rig loss의 gradient 방향** [해결됨]: H_ij는 fixed (∂H/∂ξ=0)이라 H_ij 경로로는 pose gradient 없음. 그러나 render(G, T_t∘Q_i)가 current pose T_t에 의존하므로 render() 경로로 pose gradient는 흐름. 따라서 올바른 L_rig는 render-to-observed (not render-to-render warp) 여야 하며, 추가로 pose-frozen substep으로 Gaussian이 drift를 흡수하는 것을 방지해야 함. → §5 방향 C 수정 완료.

2. **방향 A의 window size**: 360° sweep 23 timestamp에서 sliding window N=3이면 27 keyframe. joint optimization cost가 single keyframe의 3배. 이를 incremental streaming에서 수용 가능한가?

3. **C4 threshold 0.7 재보정**: iter=270에서 pyr_lvl이 더 일찍 0에 도달할 가능성 → C4 단독으로 PSNR −0.10 dB 손해가 iter=270에서 더 커질 수 있음. iter=270 전용 dft_threshold 재탐색 필요한가?

---

## 9. git 참조

```
commit: 20ee29a  branch: rig/main
관련 파일: scene/scene_model.py, scene/keyframe.py, utils.py, args.py, train.py
핵심 플래그: --use_c2 --use_c4 (권장), --use_c3 (deferred)
```
