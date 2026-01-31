# On-the-fly NVS Multiview Gaussian Spawning

## Part 1: 원본 On-the-fly NVS 파이프라인

### 1.1 전체 구조

([arXiv:2512.08498](https://arxiv.org/pdf/2512.08498) 기반 파이프라인) 단일 ref camera 비디오 스트림에서 실시간으로 3DGS scene을 구축함.

```mermaid
flowchart LR
    subgraph Bootstrap["Bootstrap (KF 0~7)"]
        B1["8 KF 수집"] --> B2["miniBA<br/>focal + pose + 3D kpts<br/>공동 최적화"]
        B2 --> B3["add_new_gaussians × 8<br/>mono depth + guided MVS"]
        B3 --> B4["optimization × 30 iter"]
    end
    subgraph Incremental["Incremental (KF 8~N)"]
        I1["PnP tracking"] --> I2["miniBA 보정"]
        I2 --> I3["add_new_gaussians<br/>mono depth + guided MVS"]
        I3 --> I4["optimization × 30 iter"]
    end
    subgraph Eval["Evaluation"]
        E1["test KF에서<br/>PSNR / SSIM / LPIPS"]
    end
    Bootstrap --> Incremental --> Eval
```

### 1.2 Bootstrap

초기 8 프레임을 수집해서 miniBA로 focal, pose, 3D keypoints를 공동 최적화함. 그 후 각 keyframe마다 `add_new_gaussians`로 초기 Gaussian scene을 생성함.

### 1.3 Incremental

매 keyframe마다 아래 순서를 반복함:

```mermaid
flowchart TD
    A["PnP: 이전 KF들과 feature matching → pose 추정"] --> B["miniBA: central pose만 최적화<br/>(나머지 카메라는 rig 상대변환으로 유도)"]
    B --> C["add_new_gaussians"]
    subgraph spawn["Gaussian Spawn 상세"]
        C1["Laplacian sampling<br/>(LoG 연산자 → 텍스처 edge에 높은 삽입 확률)"]
        C2["Guided MVS depth<br/>(이전 KF들과 stereo matching → triangulated 3D points)"]
        C3["align_depth()<br/>triangulated pts ↔ mono depth<br/>least-squares fitting → bake-in"]
        C4["Occlusion check + Gaussian pruning"]
        C1 --> C2 --> C3 --> C4
    end
    C --> spawn
    spawn --> D["Optimization × 30 iter<br/>(photometric loss + depth loss)"]
```

### 1.4 align_depth() 메커니즘

mono depth(Depth-Anything-V2)는 상대적 inverse depth만 출력하므로 절대 스케일 정렬이 필요함.

```mermaid
flowchart TD
    subgraph bake["align_depth() — 일회성 fitting"]
        TRI["triangulated 3D points"] --> LS["least-squares fitting<br/>mono_idepth × s + o ≈ tri_idepth"]
        MONO["Depth-Anything-V2<br/>raw mono_idepth"] --> LS
        LS --> BAKE["mono_idepth 데이터에<br/>직접 s, o 적용 (bake-in)"]
    end
    subgraph param["depth_scale / depth_offset (nn.Parameter)"]
        INIT["초기값: scale=1.0, offset=0.0"] --> LEARN["optimization에서<br/>depth loss로 점진적 학습"]
    end
    bake -.- NOTE["bake-in 결과는<br/>nn.Parameter에 반영 안 됨"]
    NOTE -.- param
```

`align_depth()`는 fitting된 s, o를 `mono_idepth` 텐서에 직접 곱/더하기로 반영(bake-in)하지만, `depth_scale`/`depth_offset` nn.Parameter는 건드리지 않음. 즉 bake-in 후에도 nn.Parameter는 초기값(1.0, 0.0)을 유지함. 이 분리가 aux camera depth alignment 시 문제를 일으켰음 (Part 2 참조).

### 1.5 논문 rig vs 현재 데이터

| 항목 | 논문 ([arXiv:2512.08498](https://arxiv.org/pdf/2512.08498)) | 현재 데이터 |
|------|------------------------|------------|
| Rig 형태 | 물리적 하드웨어 (헬멧 마운트) | 가상 pinhole 배열 |
| Baseline | 수 cm~수십 cm | ≈ 0 (rotation-only) |
| 삼각측량 | 동일 프레임 내 카메라 간 가능 | 불가 (temporal만 가능) |
| 캘리브레이션 | Calibration-free (자동 추정) | `blender_rig.json`에 사전 정의 |
| 카메라 수 | 3~9대 | 5대 (High_Cam06/07/08, Low_Cam07/08) |
| Focal length | miniBA에서 최적화 | 480.0 고정 |

5대 가상 카메라가 동일 좌표에서 회전만 다르므로, 동일 프레임 내 카메라 간에는 시각차(parallax)가 없음. 삼각측량에는 시각차가 필수이므로 동일 프레임 내 카메라 간 삼각측량은 불가능하고, 촬영자 보행으로 인한 temporal baseline에만 의존함.

---

## Part 2: 변경한 파이프라인

### 2.1 변경된 Incremental 흐름

```mermaid
flowchart TD
    subgraph step1["1. Tracking (변경 없음)"]
        PNP["PnP + miniBA (ref only)"]
    end
    subgraph step2["2. Ref Gaussian Spawn (변경 없음)"]
        REF["add_new_gaussians<br/>Laplacian → guided MVS → align_depth() → occlusion check"]
    end
    subgraph step3["3. Aux Gaussian Spawn (신규)"]
        AUX["4개 aux cam 각각:"]
        MONO["Depth-Anything-V2 (518×518 → 960×960)"]
        RENDER["GS render (aux view) → rendered_invdepth"]
        FIT["per-camera reproj fitting<br/>sample_reprojection_pairs() → fit_affine_robust()"]
        SAFE{"pairs≥500 &<br/>a>0 &<br/>nonpos<0.3?"}
        SPAWN["aligned_idepth = mono × a + b<br/>→ Laplacian + occlusion + budget(1000/cam)<br/>→ Gaussian init (opacity=0.03)"]
        SKIP["skip"]
        AUX --> MONO --> RENDER --> FIT --> SAFE
        SAFE -->|Pass| SPAWN
        SAFE -->|Fail| SKIP
    end
    subgraph step4["4. Optimization (변경)"]
        OPT["30 iter × 5-cam photometric loss (L1+SSIM)<br/>ref만 depth loss / ref만 pose gradient"]
    end
    step1 --> step2 --> step3 --> step4
```

원본 대비 달라진 부분

| 항목 | 원본 | 변경 후 |
|------|------|--------|
| Optimization loss | ref 1-cam photometric loss | 5-cam photometric loss (L1 + SSIM) |
| Gaussian spawn | ref camera만 | ref + aux 4대 (KF 8~ 활성화) |
| Aux depth alignment | 해당 없음 | per-camera reprojection fitting |
- ref camera : 중심 카메라 pose
- aux camera : 중심 카메라를 제외한 나머지 카메라 pose

### 2.2 Aux Gaussian Spawning

aux camera 4대(High_Cam06/08, Low_Cam07/08)에서 Gaussian을 추가 spawn함. `multiview_spawn_warmup=8` 이후(KF 8~)부터 활성화됨.

bootstrap 구간(KF 0~7)에서는 비활성화함. 근본 원인은 GS scene이 초기화 단계라 ref rendered depth가 부정확하기 때문이며, reproj fitting이 이 depth를 기준으로 대응점을 수집하므로 fitting 결과도 신뢰할 수 없음.

aux camera는 ref와 optical center가 같으므로(rotation-only rig) guided MVS를 쓸 수 없음. mono depth만 사용함.

### 2.3 Per-Camera Reprojection Depth Alignment

aux의 mono depth를 절대 스케일로 정렬하기 위해 per-camera 독립 affine fitting을 수행함.

ref에서는 `align_depth()`가 triangulated points를 기준으로 fitting하지만, aux에서는 triangulated points가 없음 (baseline ≈ 0이므로). 대신 GS rendered depth를 매개로 aux↔ref 대응점을 수집함.

```mermaid
flowchart TD
    subgraph reproj["sample_reprojection_pairs()"]
        S1["aux view에서 5000개 pixel 랜덤 샘플"]
        S2["GS rendered_invdepth로<br/>aux pixel → 3D world → ref project"]
        S3["ref rendered_invdepth에서<br/>해당 위치의 invdepth bilinear sample"]
        S4["(x=aux_mono_idepth,<br/>y=ref_rendered_idepth, w=1.0) 쌍 수집"]
        S1 --> S2 --> S3 --> S4
    end
    subgraph fit["fit_affine_robust()"]
        F1["WLS: y = a·x + b"] --> F2["Huber reweighting (δ=0.01)"]
        F2 --> F3["Refit → (a, b, inlier_frac)"]
    end
    subgraph check["Safety Checks"]
        C1{"pairs ≥ 500?<br/>a > 0?<br/>nonpos < 0.3?"}
        C1 -->|Pass| OK["aligned = mono × a + b<br/>→ spawn 진행"]
        C1 -->|Fail| NG["skip"]
    end
    reproj --> fit --> check
```

safety check 조건 하나라도 실패하면 해당 camera/KF skip함.

| 조건 | 의미 |
|------|------|
| pairs < 500 | 대응점 부족 → fitting 불안정 |
| a ≤ 0 | mono↔render 간 양의 상관 없음 |
| nonpos_ratio ≥ 0.3 | aligned_idepth ≤ 0 pixel이 30% 이상 → depth 무한대/음수 |


---

## Part 3: 평가

### 3.1 정량 비교

| Metric | 원본 (ref-only) | **최종 (multiview spawn)** |
|--------|----------------|--------------------------|
| PSNR | 16.686 | **17.331** (+0.645) |
| SSIM | 0.505 | **0.528** (+0.023) |
| LPIPS | 0.437 | **0.423** (-0.014) |
| Gaussians | 740,626 | 720,861 |
| Time (s) | 28.60 | 129.34 |

시간이 28s → 129s로 늘어난 이유 : 5-cam rendering + aux depth fitting + aux spawning 오버헤드 때문

### 3.2 Per-Camera Fitting 통계

<img src="../video_picture/260131/per_camera_fitting_stats.png" width="900">

| Camera | 성공/전체 | skip률 | a (median±std) | b (median±std) | pairs (median) | 총 spawned |
|--------|---------|--------|---------------|---------------|---------------|-----------|
| High_Cam06 | 10/26 | 62% | 0.396±0.190 | 1.633±0.408 | 1,687 | 10,000 |
| High_Cam08 | 18/21 | 14% | 0.245±0.169 | 1.031±0.314 | 4,232 | 17,316 |
| Low_Cam07 | 19/26 | 27% | 0.512±0.198 | 1.584±0.305 | 1,581 | 19,000 |
| Low_Cam08 | 17/25 | 32% | 0.457±0.332 | 1.455±0.395 | 3,841 | 17,000 |

a 값이 카메라마다 0.245~0.512로 다르므로 per-camera 독립 fitting이 필요했음을 수치로 확인함. 총 63K spawn이며, safety check의 skip 메커니즘이 fitting 불안정 케이스를 차단함. 통계의 a/b/pairs median은 성공한 KF만의 중앙값이며 skip된 KF는 제외됨.

### 3.3 정성적 비교: GT vs 최종 렌더링

#### frame_00001

| Camera | GT | Render |
|--------|----|----|
| High_Cam07 (Ref) | <img src="../video_picture/260131/gt_kf000_High_Cam07.png" width="400"> | <img src="../video_picture/260131/b3_2_kf000_High_Cam07.png" width="400"> |
| High_Cam06 (Left 45°) | <img src="../video_picture/260131/gt_kf000_High_Cam06.png" width="400"> | <img src="../video_picture/260131/b3_2_kf000_High_Cam06.png" width="400"> |
| High_Cam08 (Right 45°) | <img src="../video_picture/260131/gt_kf000_High_Cam08.png" width="400"> | <img src="../video_picture/260131/b3_2_kf000_High_Cam08.png" width="400"> |
| Low_Cam07 (Down-Left) | <img src="../video_picture/260131/gt_kf000_Low_Cam07.png" width="400"> | <img src="../video_picture/260131/b3_2_kf000_Low_Cam07.png" width="400"> |
| Low_Cam08 (Down-Right) | <img src="../video_picture/260131/gt_kf000_Low_Cam08.png" width="400"> | <img src="../video_picture/260131/b3_2_kf000_Low_Cam08.png" width="400"> |

#### frame_00301

| Camera | GT | Render |
|--------|----|----|
| High_Cam07 (Ref) | <img src="../video_picture/260131/gt_kf010_High_Cam07.png" width="400"> | <img src="../video_picture/260131/b3_2_kf010_High_Cam07.png" width="400"> |
| High_Cam06 (Left 45°) | <img src="../video_picture/260131/gt_kf010_High_Cam06.png" width="400"> | <img src="../video_picture/260131/b3_2_kf010_High_Cam06.png" width="400"> |
| High_Cam08 (Right 45°) | <img src="../video_picture/260131/gt_kf010_High_Cam08.png" width="400"> | <img src="../video_picture/260131/b3_2_kf010_High_Cam08.png" width="400"> |
| Low_Cam07 (Down-Left) | <img src="../video_picture/260131/gt_kf010_Low_Cam07.png" width="400"> | <img src="../video_picture/260131/b3_2_kf010_Low_Cam07.png" width="400"> |
| Low_Cam08 (Down-Right) | <img src="../video_picture/260131/gt_kf010_Low_Cam08.png" width="400"> | <img src="../video_picture/260131/b3_2_kf010_Low_Cam08.png" width="400"> |

#### frame_00521

| Camera | GT | Render |
|--------|----|----|
| High_Cam07 (Ref) | <img src="../video_picture/260131/gt_kf020_High_Cam07.png" width="400"> | <img src="../video_picture/260131/b3_2_kf020_High_Cam07.png" width="400"> |
| High_Cam06 (Left 45°) | <img src="../video_picture/260131/gt_kf020_High_Cam06.png" width="400"> | <img src="../video_picture/260131/b3_2_kf020_High_Cam06.png" width="400"> |
| High_Cam08 (Right 45°) | <img src="../video_picture/260131/gt_kf020_High_Cam08.png" width="400"> | <img src="../video_picture/260131/b3_2_kf020_High_Cam08.png" width="400"> |
| Low_Cam07 (Down-Left) | <img src="../video_picture/260131/gt_kf020_Low_Cam07.png" width="400"> | <img src="../video_picture/260131/b3_2_kf020_Low_Cam07.png" width="400"> |
| Low_Cam08 (Down-Right) | <img src="../video_picture/260131/gt_kf020_Low_Cam08.png" width="400"> | <img src="../video_picture/260131/b3_2_kf020_Low_Cam08.png" width="400"> |

#### frame_00721

| Camera | GT | Render |
|--------|----|----|
| High_Cam07 (Ref) | <img src="../video_picture/260131/gt_kf030_High_Cam07.png" width="400"> | <img src="../video_picture/260131/b3_2_kf030_High_Cam07.png" width="400"> |
| High_Cam06 (Left 45°) | <img src="../video_picture/260131/gt_kf030_High_Cam06.png" width="400"> | <img src="../video_picture/260131/b3_2_kf030_High_Cam06.png" width="400"> |
| High_Cam08 (Right 45°) | <img src="../video_picture/260131/gt_kf030_High_Cam08.png" width="400"> | <img src="../video_picture/260131/b3_2_kf030_High_Cam08.png" width="400"> |
| Low_Cam07 (Down-Left) | <img src="../video_picture/260131/gt_kf030_Low_Cam07.png" width="400"> | <img src="../video_picture/260131/b3_2_kf030_Low_Cam07.png" width="400"> |
| Low_Cam08 (Down-Right) | <img src="../video_picture/260131/gt_kf030_Low_Cam08.png" width="400"> | <img src="../video_picture/260131/b3_2_kf030_Low_Cam08.png" width="400"> |
