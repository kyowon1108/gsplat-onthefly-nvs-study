# 260319 - Saebit Rig Pipeline Integration Report

---

## 1. 실행 환경

| 항목 | 값 |
|---|---|
| GPU | RTX 4060 Ti 16GB |
| Python 환경 | `conda activate onthefly_nvs` |
| 해상도 | 960 x 960 |
| 사용 뷰 | 9-view (`High_Cam01,02,06,07,08 + Low_Cam01,02,07,08`) |
| Ref view | `High_Cam06` |

---

## 2. 정량 결과 (최종 Render-vs-GT 기준)

### 2.1 추출

| 항목 | 값 |
|---|---|
| sampled_frames | 26 |
| processed_video_frames (원본 비디오 전체 프레임) | 919 |
| views | 9 |
| intrinsics | `fx=fy=480, cx=cy=480` |

### 2.2 COLMAP bootstrap (8 timestamp)

| 항목 | 값 |
|---|---|
| registered_images | 72 / 72 |
| registration_ratio | 1.0000 |
| num_points3D | 17,173 |
| mean reproj error | 0.5485 px |
| median reproj error | 0.4327 px |

시간 측정:

| 항목 | 값 |
|---|---|
| total pipeline time | 32.00 s |
| prep_subset | 0.17 s |
| make_rig_config | 0.06 s |
| feature_extractor | 1.88 s |
| rig_configurator | 0.32 s |
| sequential_matcher | 19.04 s |
| mapper | 10.26 s |
| inspect_result | 0.27 s |

### 2.3 최종 Render vs GT

| 항목 | 값 |
|---|---|
| num_pairs | 59 |
| mean_psnr | 16.2319 |
| median_psnr | 16.1223 |
| mean_ssim_global | 0.7595 |
| median_ssim_global | 0.7646 |
| mean_mae | 0.1097 |
| median_mae | 0.1084 |

해석 주석:
- `num_pairs=59`는 학습 시 `--test_hold 4`를 사용해 keyframe 인덱스 기준 `i % 4 == 0` 테스트 샘플만 평가했기 때문(총 234개 중 59개).

### 2.4 참고 실행 통계 (품질 비교 지표 아님)

| 항목 | 값 |
|---|---|
| on-the-fly time | 60.7818 s |
| on-the-fly FPS | 3.8498 |
| num anchors | 1 |
| num keyframes | 234 |

---

## 3. 정성 결과

### 3.1 전체 비교 GIF
<img src="../video_picture/260302/render_vs_gt.gif" width="960">

### 3.2 샘플 프레임 비교

| View / Frame | GT | OnTheFlyNVS | PostShot |
|---|---|---|---|
| High_Cam06 / frame_000000 | <img src="../video_picture/260319/High_Cam06__frame_000000__gt.png" width="280"> | <img src="../video_picture/260319/High_Cam06__frame_000000__nvs.png" width="280"> | <img src="../video_picture/260319/High_Cam06__frame_000000__postshot.png" width="280"> |
| High_Cam07 / frame_000013 | <img src="../video_picture/260319/High_Cam07__frame_000013__gt.png" width="280"> | <img src="../video_picture/260319/High_Cam07__frame_000013__nvs.png" width="280"> | <img src="../video_picture/260319/High_Cam07__frame_000013__postshot.png" width="280"> |
| High_Cam08 / frame_000024 | <img src="../video_picture/260319/High_Cam08__frame_000024__gt.png" width="280"> | <img src="../video_picture/260319/High_Cam08__frame_000024__nvs.png" width="280"> | <img src="../video_picture/260319/High_Cam08__frame_000024__postshot.png" width="280"> |
| Low_Cam08 / frame_000020 | <img src="../video_picture/260319/Low_Cam08__frame_000020__gt.png" width="280"> | <img src="../video_picture/260319/Low_Cam08__frame_000020__nvs.png" width="280"> | <img src="../video_picture/260319/Low_Cam08__frame_000020__postshot.png" width="280"> |

---
