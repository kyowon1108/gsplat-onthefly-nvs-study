# 260326 - On-the-fly NVS Rig-Aware Implementation Report

---

## 1. 실행 환경

| 항목 | 값 |
|---|---|
| GPU | RTX 4060 Ti 16GB |
| Python 환경 | `conda activate onthefly_nvs` |
| 데이터셋 | Saebit 화단 (EQR → 9-view pinhole 추출) |
| 해상도 | 960 × 960 |
| 총 프레임 수 | 23 timestamp |
| 카메라 구성 | 9-view (High 5 + Low 4) |
| Ref camera | High_Cam07 |
| Aux cameras | High_Cam01/02/06/08, Low_Cam01/02/07/08 |

---

## 2. 핵심 변경 사항

### 2.1 변경 요약표

| 구분 | 원본 upstream | 변경 후 rig-aware | 목적 |
|---|---|---|---|
| **입력 계약** | 단일 이미지 시퀀스 | 9-view timestamp bundle | 전체 rig를 입력으로 사용 |
| **Dataset** | `ImageDataset` | `RigImageDataset` | timestamp 단위 묶음 제공 |
| **Keyframe** | `Keyframe` (단일 pose) | `RigKeyframe` (ref + aux obs) | 모든 view 관측 보관 |
| **Pose 추정** | ref-view PnP + mini BA | ref seed + rig-constrained refinement | aux view 2D-3D로 ref pose 보정 |
| **Gaussian spawn** | ref view만 | ref-first + aux unexplained spawn | coverage 확장 |
| **Optimization** | ref 1-cam loss | ref 중심 (aux loss 실험 경로 존재) | 안정성 우선 |
| **Metadata** | pose/camera 중심 | rig metadata 추가 저장 | 재현성 확보 |

### 2.2 프로세스 비교 다이어그램

#### 원본 upstream 프로세스

```mermaid
flowchart TD
    A[단일 이미지 시퀀스] --> B[Feature Extraction]
    B --> C[Keyframe Decision]
    C --> D{Bootstrap or Incremental?}
    D -->|Bootstrap| E[Temporal Mini BA<br/>focal + pose 초기화]
    D -->|Incremental| F[PnP + Mini BA<br/>ref pose만]
    E --> G[Keyframe 생성]
    F --> G
    G --> H[add_new_gaussians<br/>ref view만]
    H --> I[Optimization<br/>ref 1-cam loss]
    I --> J[저장]
```

#### 변경 후 rig-aware 프로세스

```mermaid
flowchart TD
    A[9-view timestamp bundle] --> B[Ref Feature Extraction]
    B --> C[Keyframe Decision<br/>ref 기준]
    C --> D{Bootstrap or Incremental?}
    D -->|Bootstrap| E[Ref Temporal Bootstrap<br/>유지]
    D -->|Incremental| F[Ref-view PnP seed<br/>+ Aux 2D-3D Refinement]
    E --> G[RigKeyframe 생성<br/>ref + aux obs]
    F --> G
    G --> H1[Ref-first spawn]
    H1 --> H2[Aux unexplained spawn]
    H2 --> H3[World-space dedup]
    H3 --> I[Optimization<br/>ref 중심]
    I --> J[저장 + rig metadata]
```

---

## 3. 주요 변경 지점 상세

### 3.1 입력 계약: 단일 이미지 → Timestamp Bundle

```
timestamp 0:
  ref_image: High_Cam07/frame_00000.png
  aux_images: [High_Cam01/.., High_Cam02/.., ..., Low_Cam08/..] (8개)
  rig_relative_Rts: blender_rig.json 기준 상대 변환

timestamp 1:
  ref_image: High_Cam07/frame_00001.png
  ...
```

### 3.2 Incremental Pose Refinement

**원본 흐름**:
```
ref-view 2D-3D PnP → mini BA (ref pose만 최적화) → pose 확정
```

**변경 후 흐름**:
```
1. Ref-view PnP → seed pose 생성
2. Aux view descriptor 추출
3. Aux view 2D-3D 매칭 (기존 3D point → aux view 투영)
4. Rig-constrained refinement (aux 관측으로 ref pose 보정)
5. RigKeyframe 생성
```

- Aux view의 2D-3D 대응을 활용하여 ref pose를 보정
- Rig relative pose를 고정 제약으로 사용하여 기하적 일관성 유지

#### 예시 이미지

![Incremental Pose Test With Actual Images](../video_picture/260326/frame_00321_incremental_pose_actual_images.png)

### 3.3 Gaussian Spawn: Coverage 확장

**원본**: ref view 시야에서만 Gaussian 생성

**변경 후**:
```mermaid
flowchart LR
    A[Ref-first spawn] --> B{Aux view rendering}
    B --> C[Unexplained 영역 탐지<br/>rendered depth 없는 곳]
    C --> D[Aux mono depth alignment<br/>per-camera reprojection fitting]
    D --> E[Aux spawn<br/>budget 1000/cam]
    E --> F[World-space dedup]
```

- Dedup으로 중복 Gaussian 제거

#### 실제 예시 이미지

![Rig Spawn Dedup Example](../video_picture/260326/frame_00321_rig_dedup_actual_images.png)

- ref spawn과 aux spawn으로 모인 candidate를 `dedup 전`과 `dedup 후`로 비교
---

## 4. 정량 평가

### 전체 메트릭 비교

| Metric | Ref Only HiQual | Ref+Aux HiQual | 개선 폭 |
|---|---:|---:|---:|
| PSNR | 11.128 | 15.168 | +4.040 |
| SSIM | 0.243 | 0.417 | +0.174 |
| LPIPS | 0.645 | 0.539 | -0.106 |
| Keyframes | 16 | 23 | +7 |
| Anchors | 1 | 1 | 0 |
| Time (s) | 6.609 | 22.431 | +15.822 |

---

## 5. 정성 평가

#### COLMAP GUI Trajectory Comparison

<table>
  <thead>
    <tr>
      <th width="50%">Ref Only HiQual</th>
      <th width="50%">Ref+Aux HiQual</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><img src="../video_picture/260326/ref_only_colmap_gui.png" alt="Ref Only HiQual COLMAP GUI"></td>
      <td><img src="../video_picture/260326/ref_aux_colmap_gui.png" alt="Ref+Aux HiQual COLMAP GUI"></td>
    </tr>
  </tbody>
</table>

<table>
  <thead>
    <tr>
      <th width="33.33%">GT</th>
      <th width="33.33%">Ref</th>
      <th width="33.33%">Ref+Aux</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td colspan="3"><strong>frame_00001</strong></td>
    </tr>
    <tr>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00001_gt.png" alt="frame_00001 GT"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00001_ref_hiqual.png" alt="frame_00001 Ref HiQual"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00001_refaux_hiqual.png" alt="frame_00001 Ref+Aux HiQual"></td>
    </tr>
    <tr>
      <td colspan="3"><strong>frame_00161</strong></td>
    </tr>
    <tr>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00161_gt.png" alt="frame_00161 GT"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00161_ref_hiqual.png" alt="frame_00161 Ref HiQual"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00161_refaux_hiqual.png" alt="frame_00161 Ref+Aux HiQual"></td>
    </tr>
    <tr>
      <td colspan="3"><strong>frame_00321</strong></td>
    </tr>
    <tr>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00321_gt.png" alt="frame_00321 GT"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00321_ref_hiqual.png" alt="frame_00321 Ref HiQual"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00321_refaux_hiqual.png" alt="frame_00321 Ref+Aux HiQual"></td>
    </tr>
    <tr>
      <td colspan="3"><strong>frame_00481</strong></td>
    </tr>
    <tr>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00481_gt.png" alt="frame_00481 GT"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00481_ref_hiqual.png" alt="frame_00481 Ref HiQual"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00481_refaux_hiqual.png" alt="frame_00481 Ref+Aux HiQual"></td>
    </tr>
    <tr>
      <td colspan="3"><strong>frame_00641</strong></td>
    </tr>
    <tr>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00641_gt.png" alt="frame_00641 GT"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00641_ref_hiqual.png" alt="frame_00641 Ref HiQual"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00641_refaux_hiqual.png" alt="frame_00641 Ref+Aux HiQual"></td>
    </tr>
    <tr>
      <td colspan="3"><strong>frame_00801</strong></td>
    </tr>
    <tr>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00801_gt.png" alt="frame_00801 GT"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00801_ref_hiqual.png" alt="frame_00801 Ref HiQual"></td>
      <td><img src="../video_picture/260326/qual_table_assets/frame_00801_refaux_hiqual.png" alt="frame_00801 Ref+Aux HiQual"></td>
    </tr>
  </tbody>
</table>
