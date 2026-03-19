# 260319 - Saebit Rig Pipeline Integration Report

---

## 1. 실행 환경

| 항목 | 값 |
|---|---|
| GPU | RTX 4060 Ti 16GB |
| Python 환경 | `conda activate onthefly_nvs` |
| 해상도 | 960 x 960 |
| 사용 뷰 | 9-view (`High_Cam01,02,06,07,08 + Low_Cam01,02,07,08`) |
| Ref view | `High_Cam07` |

---

## 2. 정성 결과

### 샘플 프레임 비교

| View / Frame | GT | OnTheFlyNVS | PostShot |
|---|---|---|---|
| High_Cam06 / frame_000000 | <img src="../video_picture/260319/High_Cam06__frame_000000__gt.png" width="280"> | <img src="../video_picture/260319/High_Cam06__frame_000000__nvs.png" width="280"> | <img src="../video_picture/260319/High_Cam06__frame_000000__postshot.png" width="280"> |
| High_Cam07 / frame_000013 | <img src="../video_picture/260319/High_Cam07__frame_000013__gt.png" width="280"> | <img src="../video_picture/260319/High_Cam07__frame_000013__nvs.png" width="280"> | <img src="../video_picture/260319/High_Cam07__frame_000013__postshot.png" width="280"> |
| High_Cam08 / frame_000024 | <img src="../video_picture/260319/High_Cam08__frame_000024__gt.png" width="280"> | <img src="../video_picture/260319/High_Cam08__frame_000024__nvs.png" width="280"> | <img src="../video_picture/260319/High_Cam08__frame_000024__postshot.png" width="280"> |
| Low_Cam08 / frame_000020 | <img src="../video_picture/260319/Low_Cam08__frame_000020__gt.png" width="280"> | <img src="../video_picture/260319/Low_Cam08__frame_000020__nvs.png" width="280"> | <img src="../video_picture/260319/Low_Cam08__frame_000020__postshot.png" width="280"> |

---

## 3. 코드 분석 결과
- 