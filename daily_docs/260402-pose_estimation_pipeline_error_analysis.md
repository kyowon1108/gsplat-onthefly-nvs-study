# 260402 - Pose Estimation Pipeline 오차 누적 구조 분석

## 1. 문서 목적

현재 On-the-fly NVS의 pose estimation 파이프라인에서 오차가 누적되는 구조적 문제 정리

## 2. 환경 및 기준 데이터

| 항목 | 값 |
|------|-----|
| 데이터셋 | `/opt/ftp/files/260325` |
| 이미지 해상도 | 960 x 960 |
| 카메라 파라미터 | fx = fy = cx = cy = 480 |
| Rig 구성 | EQR에서 추출한 9개 pinhole view |
| Rig 유형 | **Rotation-only** (translation = 0, 동일 광학 중심) |
| Keyframe 수 | 23 (GT trajectory 기준) |

## 3. 파이프라인 구조 요약

- pose 추정 방식
```
┌─────────────────────────────────────────────────────────────────┐
│  Bootstrap Phase (첫 8 keyframes)                               │
│  - Joint optimization: 모든 keyframe pose + focal 동시 추정     │
│  - MiniBA 200 iterations                                        │
│  - 결과: 초기 trajectory의 scale과 방향 결정                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Incremental Phase (9번째 keyframe 이후)                        │
│  - 새 frame만 추정, 이전 pose는 고정                             │
│  - PnP + RANSAC → MiniBA 20 iterations                         │
│  - 결과: 이전 pose 오차가 그대로 전파                            │
└─────────────────────────────────────────────────────────────────┘
```

## 4. 초기 가설: Bootstrap Phase 문제

### 4.1 가설

Bootstrap phase에서 오차가 발생하면 전체 reconstruction의 기준이 되어 이후 모든 keyframe에 영향을 미칠 것으로 예상했음. **(10절 반복 실험에서 반증됨)**

### 4.2 예상 원인

| 원인 | 설명 |
|------|------|
| 초기 correspondence 품질 | 첫 몇 frame 간의 feature matching 및 triangulation 품질이 낮으면 초기 pose 추정이 불안정 |
| Scale 모호성 | Rotation-only rig에서는 timestamp 내 translation baseline이 없어 depth scale 추정이 어려움 |
| Joint optimization 한계 | 8개 keyframe을 동시에 최적화하지만, local minimum에 빠질 수 있음 |

### 4.3 예상 영향

1. **3D point 위치 왜곡**: triangulated points가 실제 위치에서 벗어남
2. **Scale ambiguity**: rotation-only rig에서는 초기 scale과 depth가 약하게 제약됨
3. **후속 pose 기준 오염**: incremental phase에서 잘못된 3D points를 기준으로 새 pose를 추정

## 5. Incremental Phase 문제

### 5.1 문제 요약

Incremental phase는 **feed-forward** 구조로, 새 pose만 추정하고 이전 pose는 절대 수정하지 않음.

### 5.2 세부 원인

| 원인 | 설명 |
|------|------|
| 단방향 오차 전파 | 이전 pose 오차 → 잘못된 3D points → 새 pose 오차 (누적) |
| Multi-keyframe BA 부재 | 새 keyframe 추가 후 최근 N개를 함께 재정렬하는 메커니즘 없음 |
| Constant velocity fallback | Pose 추정 실패 시 등속 운동 가정으로 대체 → 추가 오차 유입 |

### 5.3 오차 누적 다이어그램 (초기 가설)

```
KF1 (bootstrap) ──┐
KF2 (bootstrap) ──┼── Joint BA (200 iters) ──▶ 초기 오차 ε₀ (실제로는 재현성 높음)
...               │
KF8 (bootstrap) ──┘

KF9  ← 고정된 KF1-8 기준으로 추정 ──▶ ε₀ + δ₉
...
KF14 ← 문제 구간 시작 (frame_00561~) ──▶ pose 추정 실패 → fallback → 발산
...
KF23 ← 발산된 trajectory
```

**→ 10절 실험 결과: 실제 variance는 bootstrap이 아닌 fallback 구간(00561~00761)에서 발생**

## 6. Rotation-Only Rig의 구조적 한계

### 6.1 Rig 특성

| 특성 | 값 |
|------|-----|
| View 수 | 9개 (High_Cam01-08, Low_Cam01-08 중 일부) |
| 기준 view | High_Cam07 |
| Translation | 모든 view에서 t = [0, 0, 0] |
| Rotation | 각 view마다 고유한 방향 |

### 6.2 한계점

1. **Timestamp 내 triangulation 불가**
   - 같은 timestamp의 9개 view는 동일 광학 중심을 공유
   - Stereo baseline이 없어 depth 추정 불가
   - 반드시 다른 timestamp의 view와 매칭해야 함

2. **Cross-view matching의 어려움**
   - 현재 timestamp의 aux view와 이전 timestamp의 ref view는 시선 방향 차이가 큼
   - Overlap 영역이 제한적 → 매칭 품질 저하

3. **기존 MiniBA에 rig constraint 미통합**
   - 기존 MiniBA는 독립 카메라 가정 (각 카메라가 자유롭게 움직임)
   - Rig constraint (aux_Rt = rig_relative_Rt @ ref_Rt)를 직접 적용 불가

## 7. 시도한 해결책: Rig-Aware Local BA

### 7.1 구현 내용

Incremental phase에서 새 keyframe 추가 후, 최근 N개 keyframe의 ref pose를 재정렬하는 Local BA 구현

**수정 파일:**

| 파일 | 변경 내용 |
|------|----------|
| `scene/keyframe.py` | `aux_desc_kpts` 저장 구조 추가 |
| `poses/pose_initializer.py` | `refine_local_ba_rig()` 메서드 추가 (~170 lines) |
| `scene/scene_model.py` | `select_local_ba_window()`, `refresh_pose_caches()` 추가 |
| `train.py` | Local BA 호출 로직 추가 |
| `args.py` | Local BA 관련 arguments 추가 |

### 7.2 Local BA 설계

**Rig Constraint:**
```
aux_Rt = rig_relative_Rt @ ref_Rt
         ↑                   ↑
         고정값 (json)        최적화 대상
```
- Ref pose(High_Cam07)만 최적화하면 나머지 8개 aux pose는 자동 계산됨

**Optimization 구조:**
| 구분 | 내용 |
|------|------|
| 최적화 대상 | 최근 n_opt개 ref poses (각 6 DOF) |
| 고정 | n_fixed개 anchor poses, Gaussians, rig relative |
| 손실 | 2D-3D reprojection error |

**왜 MiniBA 대신 Adam(autograd)을 사용했는가?**

| MiniBA | Adam + autograd |
|--------|-----------------|
| 각 카메라를 독립적으로 최적화 | 제약 조건 적용 가능 |
| 9개 pose 각각 자유롭게 움직임 | ref만 움직이고 aux는 수식으로 파생 |
| → rig constraint 위반 가능 | → rig constraint 항상 유지 |

MiniBA는 내부 구현이 고정되어 `aux = rig @ ref` 제약을 넣을 수 없음. Adam + autograd 조합은 forward pass에서 제약을 명시적으로 적용하면서 gradient 기반 최적화 가능.

## 8. 정량 평가 결과

### 8.1 실험 설정

```bash
# 공통 설정
ref view High_Cam07 고정
focal 480 고정
test_hold 4
```

### 8.2 정량 비교

| 설정 | Keyframes | Time (s) | PSNR | SSIM | LPIPS | Gaussians |
|------|----------:|----------:|-----:|-----:|------:|----------:|
| Baseline (no Local BA) | 23 | 17.8 | **14.01** | 0.376 | **0.571** | 184,548 |
| Local BA (n_opt=4, n_fixed=2) | 23 | 26.5 | 13.63 | **0.377** | 0.581 | 188,181 |

- Local BA 적용 후 오히려 PSNR/LPIPS가 소폭 하락 (-0.38 / +0.01)
- SSIM은 거의 동일 (+0.001)
- 처리 시간 ~50% 증가 (17.8s → 26.5s)
- Keyframe 등록 수는 동일 (23개)

### 8.3 Fallback 사용 비교

| 설정 | Fallback 발생 프레임 |
|------|---------------------|
| Baseline | frame_00601, frame_00641, frame_00681 |
| Local BA | frame_00561, frame_00641, frame_00681 |

두 설정 모두 유사한 구간에서 pose 추정 실패 → fallback 사용

---

## 9. 정성 평가 (Test Images)

### 9.1 Test Frame 비교


| Frame | Baseline | Local BA |
|-------|----------|----------|
| 00001 | ![](../video_picture/260402/baseline/frame_00001.webp) | ![](../video_picture/260402/local_ba/frame_00001.webp) |
| 00161 | ![](../video_picture/260402/baseline/frame_00161.webp) | ![](../video_picture/260402/local_ba/frame_00161.webp) |
| 00321 | ![](../video_picture/260402/baseline/frame_00321.webp) | ![](../video_picture/260402/local_ba/frame_00321.webp) |
| 00481 | ![](../video_picture/260402/baseline/frame_00481.webp) | ![](../video_picture/260402/local_ba/frame_00481.webp) |
| 00641 | ![](../video_picture/260402/baseline/frame_00641.webp) | ![](../video_picture/260402/local_ba/frame_00641.webp) |
| 00801 | ![](../video_picture/260402/baseline/frame_00801.webp) | ![](../video_picture/260402/local_ba/frame_00801.webp) |

### 9.2 COLMAP GUI 비교

| Baseline | Local BA |
|----------|----------|
| ![](../video_picture/260402/baseline/colmap_gui_baseline.webp) | ![](../video_picture/260402/local_ba/colmap_gui_local_ba.webp) |

두 설정 모두 trajectory 후반부에서 카메라 위치가 실제와 불일치하는 양상 확인

---

## 10. 반복 실험 (10회)

4절의 "Bootstrap이 문제"라는 초기 가설을 검증하기 위해 동일 조건(Baseline, no Local BA)에서 10회 반복 실행

### 10.1 Fallback 발생 현황

| Run | Fallback 횟수 | 발생 프레임 | Gaussians |
|-----|--------------|------------|-----------|
| 1 | 2 | 00601, 00641 | 223,890 |
| 2 | 4 | 00641, 00681, 00721, 00761 | 262,570 |
| 3 | 0 | - | 289,020 |
| 4 | 3 | 00641, 00681, 00721 | 221,509 |
| 5 | 0 | - | 276,315 |
| 6 | 3 | 00561, 00601, 00641 | 213,263 |
| 7 | 2 | 00601, 00641 | 219,154 |
| 8 | 3 | 00601, 00641, 00681 | 204,372 |
| 9 | 0 | - | 270,679 |
| 10 | 0 | - | 260,398 |

- Fallback 0회: 4/10 (40%)
- Fallback 2~4회: 6/10 (60%)
- 주로 **frame_00561~00761 구간**에서 발생

### 10.2 Pose Variance 분석

- **Q std**: Quaternion(회전) 표준편차. 값이 작을수록 10회 실행에서 카메라 방향이 동일
- **T std**: Translation(위치) 표준편차. 값이 작을수록 10회 실행에서 카메라 위치가 동일

| 구간 | Frame 범위 | Q std | T std |
|------|-----------|-------|-------|
| **Bootstrap** | 00001~00281 | 0.00006 | 0.00015 |
| Early Incr | 00321~00521 | 0.00041 | 0.00250 |
| **Fallback 구간** | 00561~00761 | **0.09867** | **0.13483** |
| After Fallback | 00801~00881 | 0.09177 | 0.26534 |

### 10.3 발견 내용

**Bootstrap은 run-to-run variance의 주요 원인이 아님**
- 10회 실행해도 첫 8개 keyframe pose는 사실상 동일 (Q std < 0.0001)
- Bootstrap phase의 재현성은 매우 높음

**Variance는 Incremental의 fallback 구간에서 발생**
- Fallback 구간(00561~00761)은 trajectory의 **U-turn 후반부**에 해당
- 카메라가 방향을 크게 전환한 직후 구간으로, feature matching이 어려워지는 영역
- frame_00641: Q std = 0.35 (quaternion이 완전히 다름)
- Pose 추정 실패 → constant velocity fallback → 각 run마다 다른 방향으로 발산
- 관측 범위에서는 발산 후 회복되지 않음

---

## 11. 이슈 요약

```
┌────────────────────────────────────────────────────────────┐
│                    근본 원인 (Root Causes)                  │
├────────────────────────────────────────────────────────────┤
│ A. Bootstrap은 variance의 주요 원인 아님 (10회 반복해도 pose 동일) │
│ B. U-turn 후반 구간(00561~00761)에서 pose 추정 실패        │
│ C. Fallback(constant velocity) 사용 시 trajectory 발산     │
│ D. 발산 후 회복 메커니즘 없음 (feed-forward only)          │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│                       결과 (Symptoms)                       │
├────────────────────────────────────────────────────────────┤
│ - Trajectory 후반부 drift 심화                              │
│ - COLMAP GUI에서 카메라 위치가 실제와 불일치                 │
│ - Pose 추정 실패 시 fallback 사용 → 추가 오차               │
└────────────────────────────────────────────────────────────┘
```
