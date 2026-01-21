# ontheflynvs에 rig sfm 적용

## 0. 참고 문헌
[https://arxiv.org/pdf/2512.08498](https://arxiv.org/pdf/2512.08498)

## 1. ontheflynvs 파이프라인 개요

```
360 영상 촬영 (Insta360 X5)
       ↓
다시점 이미지 추출 (Blender 360 Extractor)
       ↓
COLMAP SfM (Feature Extraction → Matching → Mapper)
       ↓
3DGS 학습 (PostShot)
       ↓
Novel View 렌더링
```

## 2. Rig SfM 적용 시 코드 문제점

| 문제 | 설명 |
|------|------|
| 자동화 부재 | 좌표계 변환(Blender→COLMAP), Rig 설정 생성, 프레임 동기화 모두 수동 |
| 좌표계 변환 | Blender(+Y forward, +Z up) → COLMAP(+Y down, +Z forward) 변환 스크립트 없음 |
| 파라미터 고정 | `ba_refine_sensor_from_rig=0` 사용 시 초기 파라미터 오류 수정 불가 |

- ~~**on-the-fly-nvs는 기본적으로 multi-camera rig(동시 다중 카메라 입력)을 지원하지 않기 때문에, 코드를 전부 수정해야 함.**~~
- ✅ **해결 완료**: 5개 파일 수정으로 9카메라 rig 지원 구현 (상세: Section 8)

## 3. 논문의 핵심 기법

### 3.1 Calibration-Free 초기화 (Hierarchical Initialization)

- 중앙 카메라 자동 식별: 카메라 그래프에서 다른 카메라들과의 경로 합이 최소인 중심 카메라 선택
- 계층적 트리 구조로 카메라 정렬, 각 카메라의 상대 포즈(Relative Pose) 획득

### 3.2 경량화된 Multi-Camera Bundle Adjustment

- Rigid Rig 제약 활용: 중앙 카메라 포즈만 최적화, 나머지는 상대 변환으로 도출
- 계산 효율성 유지 + Wide-baseline 환경에서 궤적 안정성 확보

### 3.3 중복 없는 Gaussian Sampling (논문 Section 3.2: Redundancy-free Gaussian Sampling)

- 인접 카메라 간 시야 중복 시 동일 영역에 중복 Gaussian 생성 방지
- 기존 Gaussian 투영(Reprojection) 후 깊이 차이 적으면 병합

### 3.4 주파수 기반 최적화 스케줄러 (논문 Section 3.3: Frequency-based Scheduling)

- 고주파 영역(디테일 多)에 더 많은 반복, 저주파 영역에 적은 반복
- 제한된 시간 내 전체 씬 선명도(Fidelity) 극대화

### 3.5 실시간 + OOM 해결의 5가지 핵심 레버

| 레버 | 설명 | OOM 관련성 |
|------|------|-----------|
| **A. 드리프트 없는 궤적** | 중앙 카메라만 최적화, 나머지는 상대변환 | 최적화 변수 폭발 방지 |
| **B. 중복 없는 샘플링** | Inter-frame + Inter-camera redundancy 제거 | **#Gaussians 성장률 제어** |
| **C. 10-30 iter 제약** | 키프레임당 반복 횟수 엄격 제한 | 연산 시간 고정 |
| **D. 주파수 스케줄러** | 저주파 영역에 iter 집중, LOD 학습 | 제한 iter 내 품질 유지 |
| **E. Anchor 전략** | 멀리 있는 Gaussian 집약/오프로딩 | VRAM 안정화 |

**실험 세팅 참고**: 기존 베이스라인들이 **3카메라 초과에서 OOM/드리프트**로 무너짐
→ 9카메라 rig 적용 시 B(중복 제거)가 1순위 레버

## 4. 논문 vs ontheflynvs 파이프라인 비교

| 항목 | 논문 (On-the-fly 3D Recon) | ontheflynvs (현재) |
|------|---------------------------|-------------------|
| 카메라 | Multi-camera rig | 360 카메라 (Insta360 X5) |
| 캘리브레이션 | Calibration-free (계층적 초기화) | Rig 설정 수동 생성 필요 |
| SfM | 실시간 다중 카메라 번들 조정 | COLMAP 오프라인 처리 |
| 3DGS 최적화 | 주파수 기반 스케줄러 (반복 감소) | PostShot 기본 학습 |
| 가우시안 샘플링 | 중복 제거 샘플링 (프리미티브 감소) | 기본 densification |
| 처리 방식 | On-the-fly (실시간) | 오프라인 |

## 5. Rigged SfM 적용 결과

### 5.1. 논문에서 사용한 camera rig 데이터셋
![](../video_picture/260119/260119-research_rig_camera.png)

### 5.2. Blender 360 extractor tool
![](../video_picture/260119/260119-blender_rig_image.png)

### 5.3. 260111/260113 실험 결과 연계

| 항목 | 260111 (SfM) | 260113 (3DGS) |
|------|-------------|---------------|
| Rig 구성 | 9대 카메라 (High 5 + Low 4) | 동일 |
| 기준 카메라 | High_Cam01 수동 지정 | - |
| SfM 개선 | 3D 포인트 +35%, Obs +119% | - |
| 3DGS 개선 | - | PSNR +1.24dB, SSIM +0.067 |

**논문 기법 적용 현황**
- 3.1 (Calibration-Free 초기화): Rig 구성이 이미 알려져 있으므로 불필요
- 3.2 (경량화된 BA): COLMAP Rig 제약과 유사하게 적용됨
- 3.3 (중복 제거 Gaussian): ✅ **구현 완료** (Section 8.2 참조)
- 3.4 (주파수 스케줄러): ✅ **구현 완료** (Section 9 참조)

### 5.4. Multi-Camera Rig 구현 실험 결과

| 항목 | 값 |
|------|-----|
| 처리된 프레임 | 414개 (100%) |
| 등록된 Keyframe | 330개 |
| 최종 Gaussian 수 | ~565,000개 |
| 생성된 Anchor 수 | 4개 |
| NVS 학습 시간 | **213.3초 (3.6분)** |
| 전체 파이프라인 시간 | 825.4초 (13.8분) |
| 회전 오차 (R°) | 0.048° |
| 이동 오차 (t) | 0.0015 |

**Baseline vs Frequency Scheduler 비교:**

| 항목 | Baseline | Frequency Scheduler |
|------|----------|---------------------|
| NVS 학습 시간 | 213.3초 | **207.1초 (-3%)** |
| Keyframes | 330 | 333 |
| 회전 오차 (R°) | 0.048° | **0.044° (-7%)** |
| Peak GPU Memory | 11,009 MB | **10,561 MB (-4%)** |

## 6. OOM 이해를 위한 Batch 시나리오 분석

### 6.1 3DGS에서 OOM을 유발하는 4가지 요인

| 요인 | 설명 | 메모리 기여도 |
|------|------|-------------|
| **Active #Gaussians** | GPU에 활성화된 Gaussian 파라미터 수 | ~60-70% |
| **Optimizer State** | Adam의 exp_avg, exp_avg_sq (파라미터 2배) | ~20-25% |
| **Views/Step** | 한 iteration에서 참조하는 뷰 수 | ~5-10% |
| **Keyframe Window** | 학습에 사용되는 키프레임 이미지 | ~5% |

**핵심**: OOM은 "이미지 몇 장"이 아니라 **Gaussian 수 + optimizer state**가 지배

### 6.2 Vanilla 3DGS vs On-the-Fly NVS (코드 검증 기준)

| 항목 | Vanilla 3DGS | On-the-Fly NVS (코드 확인) |
|------|-------------|---------------------------|
| **Views/Iteration** | 1 view (랜덤 샘플링) | 1 view (확률적: 20% 최신, 80% 랜덤) |
| **Iter/Keyframe** | 전체 이미지에 대해 수천~수만 | **30** (args.py:59) |
| **Active Keyframes** | 전체 (고정) | **200** (args.py:113, 초과 시 CPU offload) |
| **Gaussian 관리** | 정적 densification | Pruning + k=3 Merging |
| **OOM 대응** | 없음 | Anchor offloading + Keyframe CPU 이동 |

### 6.3 멀티카메라에서 OOM이 발생하는 이유

1. **중복 Gaussian 폭발**: 동일 영역이 C개 카메라에서 보이면 C배 Gaussian 생성
2. **Optimizer state 폭발**: Gaussian 수 × 2 (Adam의 momentum 저장)
3. **크로스카메라 매칭 불안정**: 잘못된 대응 → 드리프트 → 비효율적 Gaussian 증가

**해결책 (2512.08498 논문):**
- Inter-camera redundancy-free sampling (재투영 + 깊이 비교로 병합)
- 중앙 카메라만 최적화하는 경량 BA

## 7. 실험 환경 및 결과

### 7.1 환경 설정
- GPU: RTX 4060 Ti (16GB)
- 카메라: 9대 Rig (High 5 + Low 4)
- 해상도: 960×960 (downsampling 2 적용)

### 7.2 완료된 구현

**완료된 구현 (260111/260113):**
- Rig 기반 SfM으로 초기 포즈 확보 → 논문 3.1 대체
- 3D 포인트 +35%, PSNR +1.24dB 개선 확인

### 7.3 실제 GPU 메모리 사용량 (측정 완료)

| 단계 | 최소 | 최대 | 평균 |
|------|------|------|------|
| COLMAP Feature Extraction | 3,360 MB | 3,382 MB | ~3,370 MB |
| COLMAP Bundle Adjustment | 391 MB | 540 MB | ~450 MB |
| NVS Training (초기) | 1,765 MB | 1,855 MB | ~1,800 MB |
| NVS Training (후반) | 9,000 MB | **11,009 MB** | ~10,000 MB |

**Peak GPU Memory: 11,009 MB (67% of 16GB)** → RTX 4060 Ti 16GB에서 안전 동작

### 7.4 시간대별 GPU 메모리 추이

```
시간(분)    0    2    4    6    8   10   12   14
           |    |    |    |    |    |    |    |
GPU(GB)    3.4  1.8  1.8  0.4  0.4  5.4  10.0 10.7
           └─COLMAP─┘              └──NVS Training──┘
```

## 8. 코드 수정 내역

### 8.1 수정된 파일 요약

| 파일 | 수정 내용 |
|------|----------|
| `dataloaders/image_dataset.py` | Multi-camera intrinsics 로딩, 하위 디렉토리 지원 |
| `scene/keyframe.py` | Per-camera intrinsics 저장, FOV 계산, PINHOLE 내보내기 |
| `scene/scene_model.py` | Per-keyframe FOV 렌더링, Inter-camera redundancy 제거 |
| `train.py` | Keyframe 생성 시 intrinsics 전달 |
| `utils.py` | 재귀적 이미지 디렉토리 탐색 |

### 8.2 핵심 구현: Inter-Camera Redundancy 제거

**논문 3.3절 구현** - 다른 카메라에서 이미 생성된 Gaussian과 중복되는 새 Gaussian 제거:

```python
# scene_model.py - add_new_gaussians()
current_camera_id = getattr(keyframe, 'camera_id', None)
if current_camera_id is not None and len(new_pts) > 0:
    # 다른 카메라의 최근 keyframe들에서 중복 체크
    for other_kf in other_camera_kfs[:3]:
        # 새 포인트를 다른 카메라 뷰로 투영
        pts_in_other = new_pts @ other_Rt[:3, :3].T + other_Rt[:3, 3]
        # 깊이 비교로 중복 판단 (5% 임계값)
        depth_diff = torch.abs(pts_depth - sampled_depth) / sampled_depth
        redundant = depth_diff < 0.05
    # 중복 Gaussian 제거
    if redundancy_mask.any():
        new_pts = new_pts[~redundancy_mask]
```

### 8.3 기존 핵심 파일 설명

- `train.py`: 학습 루프, keyframe 관리, 실시간 처리 파이프라인
- `scene/scene_model.py`: Gaussians, anchors, keyframes 통합 관리, 렌더링/최적화 메서드
- `scene/keyframe.py`: 카메라 파라미터, 이미지 피라미드, depth 추정 관리
- `scene/anchor.py`: 앵커 offloading 로직 (GPU 메모리 최적화)

### 8.4 주파수 스케줄러 코드 수정

**수정된 파일:**

| 파일 | 수정 내용 |
|------|----------|
| `utils.py` | `compute_frequency_score()` 함수 추가 - 이미지 주파수 점수 계산 |
| `args.py` | 주파수 스케줄러 CLI 파라미터 추가 |
| `train.py` | `compute_adaptive_iterations()` 함수 및 스케줄러 통합 |
| `run_full_pipeline.py` | 주파수 스케줄러 파라미터 전달 |

**핵심 함수:**

```python
# utils.py - compute_frequency_score()
def compute_frequency_score(image: torch.Tensor) -> float:
    """이미지의 주파수 점수 계산 (고주파 = 높은 점수)"""
    gray = 0.299 * image[0] + 0.587 * image[1] + 0.114 * image[2]
    laplacian = torch.tensor([[0, 1, 0], [1, -4, 1], [0, 1, 0]],
                             device=image.device, dtype=image.dtype)
    laplacian = laplacian.unsqueeze(0).unsqueeze(0)
    gray_4d = gray.unsqueeze(0).unsqueeze(0)
    edges = F.conv2d(gray_4d, laplacian, padding=1)
    return edges.abs().mean().item()
```

```python
# train.py - compute_adaptive_iterations()
def compute_adaptive_iterations(freq_score, min_iters, max_iters, alpha):
    """주파수 점수 기반 적응형 반복 횟수 계산"""
    normalized = (freq_score - global_min) / (global_max - global_min + 1e-8)
    normalized = max(0.0, min(1.0, normalized))
    adaptive_iters = min_iters + (max_iters - min_iters) * (normalized ** alpha)
    return int(round(adaptive_iters))
```

**CLI 파라미터:**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `--use_frequency_scheduler` | False | 주파수 스케줄러 활성화 |
| `--freq_min_iters` | 10 | 저주파 영역 최소 반복 횟수 |
| `--freq_max_iters` | 30 | 고주파 영역 최대 반복 횟수 |
| `--freq_alpha` | 1.0 | 스케줄링 커브 조정 (1.0=선형)  |

## 9. 주파수 스케줄러 실험 결과

### 9.1 성능 비교

| 항목 | Baseline | Frequency Scheduler | 변화 |
|------|----------|---------------------|------|
| NVS 학습 시간 | 213.3초 | 207.1초 | **-3% (-6.2초)** |
| 등록된 Keyframes | 330개 | 333개 | +3개 |
| 회전 오차 (R°) | 0.048° | 0.044° | **-7% 개선** |
| 이동 오차 (t) | 0.0015 | 0.0015 | 동일 |
| Peak GPU Memory | 11,009 MB | 10,561 MB | **-4% (-448 MB)** |

### 9.2 개선점 요약

1. **학습 시간 단축 (-3%)**: 저주파 영역에서 반복 횟수 감소로 전체 학습 시간 절약
2. **품질 향상 (-7% 회전 오차)**: 고주파 영역에 집중 학습으로 디테일 품질 개선
3. **메모리 효율 (-4%)**: 불필요한 반복 감소로 GPU 메모리 사용량 절감

### 9.3 사용법

```bash
# 기본 사용
python run_full_pipeline.py --use_frequency_scheduler

# 파라미터 조정
python run_full_pipeline.py \
    --use_frequency_scheduler \
    --freq_min_iters 10 \
    --freq_max_iters 30 \
    --freq_alpha 1.0
```
