# 260326 - Local Window Pose Refine Research Note

## 1. 기준 스냅샷

- Code repo: `on-the-fly-nvs`
  - branch: `research/local-window-pose-refine`
  - base commit: `1bd79ed` (`Add rig debugging and COLMAP helper scripts`)
- Study repo: `gsplat-onthefly-nvs-study`
  - branch: `research/local-window-pose-refine`
  - base commit: `af0eded` (`modify: modify 260326 docs`)
- 기준 보고서:
  - `daily_docs/260326-ontheflynvs_rig_aware_implementation.md`

## 2. 현재 기준 결과

문서에서 현재 기준으로 채택한 결과는 `test_hold=4`, `--downsampling 1`을 사용한 아래 두 실험이다.

| Run | Result dir | Keyframes | Time (s) | PSNR | SSIM | LPIPS |
|---|---|---:|---:|---:|---:|---:|
| Ref Only | `/opt/ftp/files/260325/result/ref_only_hiqual_nodown` | 20 | 8.599 | 11.227 | 0.262 | 0.643 |
| Ref+Aux | `/opt/ftp/files/260325/result/ref_and_aux_hiqual_nodown` | 23 | 22.687 | 15.752 | 0.446 | 0.515 |

참고용으로 이전 실행 결과도 남긴다.

| Run | Result dir | Keyframes | Time (s) | PSNR | SSIM | LPIPS |
|---|---|---:|---:|---:|---:|---:|
| ref_only | `/opt/ftp/files/260325/result/ref_only` | 20 | 8.813 | 12.007 | 0.288 | 0.617 |
| ref_and_aux | `/opt/ftp/files/260325/result/ref_and_aux` | 23 | 20.484 | 14.392 | 0.393 | 0.566 |
| ref_only_hiqual | `/opt/ftp/files/260325/result/ref_only_hiqual` | 16 | 6.609 | 11.128 | 0.243 | 0.645 |
| ref_and_aux_hiqual | `/opt/ftp/files/260325/result/ref_and_aux_hiqual` | 23 | 22.431 | 15.168 | 0.417 | 0.539 |

## 3. 재현 명령

### 3.1 Ref Only baseline

```bash
cd /opt/ftp/files/260325/on-the-fly-nvs
conda activate onthefly_nvs
python train.py \
  -s /opt/ftp/files/260325 \
  -i images/High_Cam07 \
  -m /opt/ftp/files/260325/result/ref_only \
  --viewer_mode none \
  --fix_focal \
  --init_focal 480 \
  --test_hold 4 \
  --test_frequency 4
```

### 3.2 Ref+Aux baseline

```bash
cd /opt/ftp/files/260325/on-the-fly-nvs
conda activate onthefly_nvs
python train.py \
  -s /opt/ftp/files/260325 \
  -m /opt/ftp/files/260325/result/ref_and_aux \
  --viewer_mode none \
  --rig_mode \
  --rig_ref_view High_Cam07 \
  --rig_manifest '' \
  --rig_config_path /opt/ftp/files/260325/blender_rig.json \
  --fix_focal \
  --init_focal 480 \
  --test_hold 4 \
  --test_frequency 4
```

### 3.3 Ref Only hiqual + nodown

```bash
cd /opt/ftp/files/260325/on-the-fly-nvs
conda activate onthefly_nvs
python train.py \
  -s /opt/ftp/files/260325 \
  -i images/High_Cam07 \
  -m /opt/ftp/files/260325/result/ref_only_hiqual_nodown \
  --viewer_mode none \
  --fix_focal \
  --init_focal 480 \
  --test_hold 4 \
  --test_frequency 4 \
  --num_prev_keyframes_check 30 \
  --num_pts_miniba_incr 3000 \
  --iters_miniba_incr 40 \
  --pnpransac_samples 4000 \
  --downsampling 1
```

### 3.4 Ref+Aux hiqual + nodown

```bash
cd /opt/ftp/files/260325/on-the-fly-nvs
conda activate onthefly_nvs
python train.py \
  -s /opt/ftp/files/260325 \
  -m /opt/ftp/files/260325/result/ref_and_aux_hiqual_nodown \
  --viewer_mode none \
  --rig_mode \
  --rig_ref_view High_Cam07 \
  --rig_manifest '' \
  --rig_config_path /opt/ftp/files/260325/blender_rig.json \
  --fix_focal \
  --init_focal 480 \
  --test_hold 4 \
  --test_frequency 4 \
  --num_prev_keyframes_check 30 \
  --num_pts_miniba_incr 3000 \
  --iters_miniba_incr 40 \
  --pnpransac_samples 4000 \
  --rig_pose_refine_iters 60 \
  --rig_pose_refine_max_matches 768 \
  --downsampling 1
```

## 4. 받은 피드백

핵심 피드백은 아래와 같다.

- 새 pose를 추정한 뒤, 이전 1~3개 keyframe도 같이 보정할 수 있어야 한다.
- 현재 방식은 새 frame pose를 잘못 잡으면 이후 keyframe들이 그 오차를 기준으로 계속 등록될 수 있다.
- 후반 keyframe에서 trajectory가 더 멀리 벌어지는 경향은 이 누적 오차와 관련 있어 보인다.

즉, `현재 frame만 맞추는 incremental 등록`에서 `짧은 시간 창(window) 단위의 국소 재정렬`로 확장하는 것이 다음 연구 주제다.

## 5. 현재 코드 구조 해석

### 5.1 현재 incremental 등록 경로

- `train.py`
  - `scene_model.get_prev_keyframes(...)`로 이전 keyframe들을 선택
  - `pose_initializer.initialize_incremental(...)` 또는 `initialize_incremental_rig(...)`로 **현재 frame pose만** 추정
  - `scene_model.add_keyframe(keyframe)`
  - `scene_model.add_new_gaussians()`
  - `scene_model.optimization_loop(args.num_iterations)`

### 5.2 왜 지금 구조로는 즉시 보정이 약한가

- `initialize_incremental(...)` / `initialize_incremental_rig(...)`는 반환값이 `현재 keyframe Rt` 하나다.
- 이전 keyframe pose를 다시 푸는 local BA 단계가 없다.
- 이후 `optimization_loop()`에서 keyframe pose가 gradient로 업데이트되긴 하지만, 샘플링된 active keyframe 하나씩 학습하는 형태라 새 keyframe 등록 직후에 최근 window를 집중 보정하는 구조는 아니다.

관련 파일:

- `on-the-fly-nvs/train.py`
- `on-the-fly-nvs/poses/pose_initializer.py`
- `on-the-fly-nvs/scene/scene_model.py`
- `on-the-fly-nvs/scene/keyframe.py`

## 6. 1차 연구 가설

가장 먼저 시도할 후보는 `pose-only local window refinement`다.

- 시점:
  - 새 keyframe을 등록한 직후
  - Gaussian spawn 전에 먼저 한 번 수행
- 최적화 대상:
  - `현재 keyframe + 이전 1~3 keyframe`
- 고정할 것:
  - scene Gaussians
  - rig relative pose
  - intrinsics
- 우선 제외할 것:
  - exposure
  - depth scale/offset
- 손실 후보:
  - 기존 2D-3D correspondence reprojection residual
  - 가능하면 현재 구현의 photometric/depth loss를 보조항으로 사용

이 접근의 장점은 구조 변경이 비교적 작고, 현재 incremental 흐름 사이에 끼워 넣기 쉽다는 점이다.

## 7. 구현 시작점 제안

### 7.1 삽입 지점

`train.py`에서 아래 순서 사이가 1차 훅 포인트다.

1. `scene_model.add_keyframe(keyframe)`
2. `scene_model.add_new_gaussians()`

즉, 새 keyframe을 scene에 넣은 뒤 곧바로 최근 window pose를 한 번 더 정렬하는 방식이다.

### 7.2 1차 구현 형태

예상 인터페이스:

```python
scene_model.refine_recent_keyframe_poses(
    window_size=4,
    iters=40,
    rig_mode=args.rig_mode,
)
```

초기 버전은 아래처럼 단순하게 가는 편이 안전하다.

- 최근 `N`개 keyframe 선택
- pose parameter(`rW2C`, `tW2C`)만 optimizer 대상에 포함
- scene Gaussian은 `torch.no_grad()` 또는 optimizer step 제외
- rig 모드에서는 aux pose를 독립 변수로 두지 않고 `rig_relative_Rts @ ref_pose` 제약 유지

## 8. 다음 분기에서 확인할 질문

1. local window refine를 `spawn 전`에 둘지, `spawn 후`에 둘지 어느 쪽이 더 안정적인가?
2. reprojection 기반만으로 충분한가, 아니면 photometric/depth 보조항이 바로 필요할까?
3. 이전 keyframe 1~3개만 조정해도 trajectory drift가 줄어드는가?
4. ref-only와 rig-aware에서 동일한 훅을 공유할 수 있는가?
5. fallback constant velocity가 들어간 프레임도 같은 local refine로 회복 가능한가?

## 9. branch 운영 메모

- 코드 연구 branch: `research/local-window-pose-refine`
- 문서 연구 branch: `research/local-window-pose-refine`
- 현재 branch는 baseline 보존 + 다음 실험 준비용이다.
- `submodules/Depth-Anything-V2` 상태 변경은 여전히 별도 이슈로 남아 있으므로 연구 커밋에서 건드리지 않는 편이 안전하다.
