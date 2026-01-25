# Rig-Aware All-9-Cameras Bootstrap 구현 설계

## 1. 배경 및 문제 정의

### 1.1 260123 원인 분석

**Rotation-only Rig의 특성 때문에 수행 불가**

| 특성 | 의미 |
|------|------|
| 같은 위치, 다른 방향 | 공간적 baseline 없음 (baseline ≈ 0) |
| 삼각측량 불가 | 같은 frame 내 depth 정보 획득 불가 |
| 멀티뷰 기하학 이득 없음 | 동일 3D 점을 여러 각도에서 보지만 깊이 추정에 기여 못함 |

**논문(arXiv:2512.08498)과의 차이**

| 논문 가정 | 현재 데이터 | 차이점 분석 |
|----------|------------|-------------|
| 물리적 분리 카메라 (baseline 존재) | Rotation-only rig (baseline ≈ 0) | 같은 frame 내 triangulation 불가 |
| Inter-camera stereo 가능 | Inter-camera stereo 불가 | Temporal baseline만 활용 가능 |
| 1개 카메라 pose → 나머지 유도 | 동일 적용 가능 (rig constraint) | R_i = R_rel_i × R_central |

### 1.2 All-9-Cameras Bootstrap 접근법

| 항목 | 값 |
|------|---|
| Bootstrap 정보량 | 72 views (9 cams × 8 frames) |
| Observations | ~36,000 (frame당 ~4,500) |
| Baseline 활용 | Temporal baseline (frame 간 이동) |
| 학술적 근거 | BundledSLAM, MultiCol BA 방식 |

---

## 2. All-9-Cameras Bootstrap 설계

### 2.1 핵심 아이디어

- 9개 카메라의 모든 observations 활용 (reprojection error 합산)
- Central camera (`High_Cam08`) pose만 BA로 최적화
- 나머지 카메라 pose는 rig constraint로 유도: `R_i = R_rel_i × R_central`

```mermaid
flowchart LR
    subgraph OBS["9개 카메라 Observations"]
        C0["cam0"]
        C1["cam1"]
        C2["..."]
        C8["cam8"]
    end

    subgraph BA["Bundle Adjustment"]
        E["Σ reprojection error"]
    end

    subgraph OUT["출력"]
        P["Central pose × 8 frames"]
    end

    C0 --> E
    C1 --> E
    C2 --> E
    C8 --> E
    E --> P
```

### 2.2 All-9-Cameras 접근법의 이점

| 이점 | 설명 |
|------|------|
| **정보 최대화** | central camera 대비 더 많은 observations |
| **Robustness 향상** | 한 카메라의 bad feature가 전체에 영향 적음 |
| **학술적 표준** | COLMAP, BundledSLAM 동일 접근법 |

---

## 3. 프로세스 플로우

### 3.1 전체 파이프라인

| Stage | 입력 | 처리 | 출력 |
|-------|------|------|------|
| 1 | EQR 8K | 9개 pinhole 변환 | 960×960 × 9 |
| 2 | 9 images | Feature extraction (XFeat) | 9 × DescribedKeypoints |
| 3 | 9 cams × 8 frames | All-9-Cameras Bootstrap | 8 central poses |
| 4 | New frame | All-cam PnP → Central pose | Central pose |
| 5 | Central keyframes | 3DGS optimization | Rendered view |

### 3.2 상세 플로우

```mermaid
flowchart TD
    INPUT["Insta360 X5 EQR Video Stream"]

    S1["Stage 1: EQR → Pinhole 변환"]
    S2["Stage 2: Feature Extraction (XFeat)"]
    S3["Stage 3: Bootstrap BA<br/>(8 frames → 8 central poses)"]
    S4["Stage 4: Incremental PnP + MiniBA"]
    S5["Stage 5: 3DGS Optimization"]

    OUTPUT["Rendered Novel View"]

    INPUT --> S1 --> S2
    S2 -->|"frame 0-7"| S3
    S3 --> S4
    S2 -->|"frame 8+"| S4
    S4 --> S5 --> OUTPUT
    OUTPUT -.->|"next frame"| INPUT
```

---

## 4. 참고문헌

1. **BundledSLAM** (arXiv:2403.19886)
   - Multi-camera pose estimation
   - https://arxiv.org/abs/2403.19886

2. **MultiCol Bundle Adjustment** (IJCV 2016)
   - Generalized camera model
   - Urban & Jutzi

3. **On-the-fly NVS** (arXiv:2512.08498)
   - 기본 파이프라인
   - https://arxiv.org/abs/2512.08498

4. **COLMAP Rig BA**
   - Rig constraint 구현 참고
   - https://colmap.github.io/rigs.html
