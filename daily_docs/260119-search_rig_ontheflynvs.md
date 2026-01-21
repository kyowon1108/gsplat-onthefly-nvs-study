# ontheflynvs에 rig sfm 적용

## 0. 참고 문헌
[https://arxiv.org/pdf/2512.08498](https://arxiv.org/pdf/2512.08498)

## 1. ontheflynvs 파이프라인 (현재 진행해야 함)

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

- **on-the-fly-nvs는 기본적으로 multi-camera rig(동시 다중 카메라 입력)을 지원하지 않기 때문에, 코드를 전부 수정해야 함.**

## 3. 논문의 핵심 기법

### 3.1 Calibration-Free 초기화 (Hierarchical Initialization)

![](../video_picture/260119/260119-innovation_1.png)

- 중앙 카메라 자동 식별: 카메라 그래프에서 다른 카메라들과의 경로 합이 최소인 중심 카메라 선택
- 계층적 트리 구조로 카메라 정렬, 각 카메라의 상대 포즈(Relative Pose) 획득

### 3.2 경량화된 Multi-Camera Bundle Adjustment

![](../video_picture/260119/260119-innovation_2.png)

- Rigid Rig 제약 활용: 중앙 카메라 포즈만 최적화, 나머지는 상대 변환으로 도출
- 계산 효율성 유지 + Wide-baseline 환경에서 궤적 안정성 확보

### 3.3 중복 없는 Gaussian Sampling (논문 Section 3.2: Redundancy-free Gaussian Sampling)

![](../video_picture/260119/260119-innovation_3.png)

- 인접 카메라 간 시야 중복 시 동일 영역에 중복 Gaussian 생성 방지
- 기존 Gaussian 투영(Reprojection) 후 깊이 차이 적으면 병합

### 3.4 주파수 기반 최적화 스케줄러 (논문 Section 3.3: Frequency-based Scheduling)

![](../video_picture/260119/260119-innovation_4.png)

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

## 5. 현재 rigged SfM 적용 방안

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
- 3.3 (중복 제거 Gaussian): **추가 적용 필요**
- 3.4 (주파수 스케줄러): **추가 적용 필요**

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

## 7. 현재 환경 적용 방안

### 7.1 환경 설정
- GPU: RTX 4060 Ti (16GB)
- 카메라: 9대 Rig (High 5 + Low 4)
- 해상도: 1920×1920 → 필요 시 960×960으로 축소

### 7.2 적용 전략

**이미 완료된 부분 (260111/260113):**
- Rig 기반 SfM으로 초기 포즈 확보 → 논문 3.1 대체
- 3D 포인트 +35%, PSNR +1.24dB 개선 확인

**추가 적용 필요:**
| 논문 기법 | 적용 방법 |
|----------|----------|
| 중복 제거 Gaussian (3.2) | 9카메라 간 겹치는 영역에서 Gaussian 병합 |
| 주파수 스케줄러 (3.3) | 디테일 영역에 iteration 집중 |

### 7.3 해상도 정책 (LOD 기반)

**단일 해상도 고정 대신 LOD 정책 적용:**

| 단계 | 해상도 | 트리거 조건 |
|------|--------|------------|
| 초기 | 1/4 (480×480) | 학습 시작 |
| 중간 | 1/2 (960×960) | 저주파 수렴 후 (DFT ratio 기준) |
| 최종 | Full (1920×1920) | 디테일 영역만 선택적 |

**이유**: 2512.08498 논문의 coarse-to-fine + 주파수 기반 업샘플 트리거 방식

### 7.4 실제 메모리 검증 방법

**필요한 측정값 (학습 중 수집):**
1. Peak VRAM 스냅샷 (시작/중간/후반)
2. 총 #Gaussians / Peak active #Gaussians
3. 실제 views/iteration 확인 (로그)
4. Anchor 생성 타이밍

※ 이 값들이 있어야 16GB 환경에 맞는 정확한 config 산출 가능

## 8. 코드 레포지토리

**클론 위치:** `~/Projects/Research/on-the-fly-nvs/`

**핵심 파일:**
- `train.py`: 학습 루프, keyframe 관리, 실시간 처리 파이프라인
- `scene/scene_model.py`: Gaussians, anchors, keyframes 통합 관리, 렌더링/최적화 메서드
- `scene/keyframe.py`: 카메라 파라미터, 이미지 피라미드, depth 추정 관리
- `scene/anchor.py`: 앵커 offloading 로직 (GPU 메모리 최적화)
