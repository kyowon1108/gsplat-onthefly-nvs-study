# multicam_dataset.py에서 추출 - 기준 카메라 인덱스 정의
# 경로: on-the-fly-nvs/insta360/multicam_dataset.py (lines 28-37)

# Reference camera index based on paper methodology:
# Pixel-wise feature distance 기반 pairwise 거리 합이 최소인 카메라를 선정
# | Camera     | Angle | Distance Sum |
# |------------|-------|--------------|
# | High_Cam01 | 0°    | 4.793        |
# | High_Cam02 | 45°   | 6.027        |
# | High_Cam06 | 225°  | 6.027        |
# | High_Cam07 | 270°  | 4.793        |
# | High_Cam08 | 315°  | 4.359 (최소) |
REFERENCE_CAMERA_INDEX = 4  # High_Cam08 (315°, 거리 합 최소)
