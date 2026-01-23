#!/bin/bash
# On-the-fly NVS 실행 명령어
# High_Cam08 (기준 카메라) 기반 단일 카메라 학습

# 데이터셋 경로
DATASET_PATH="/opt/ftp/files/260119/on-the-fly-nvs/extracted_pinhole_cam08"

# 학습 실행
python train.py \
    --data_path "$DATASET_PATH" \
    --downsampling 1.0 \
    --skip_colmap \
    --test_hold 5 \
    --result_path "results/000001"

# 옵션 설명:
# --data_path: 추출된 pinhole 이미지 경로
# --downsampling: 다운샘플링 비율 (1.0 = 원본 해상도)
# --skip_colmap: COLMAP 초기화 스킵 (pre-computed poses 사용)
# --test_hold: 테스트용으로 N번째 프레임마다 홀드 (5 = 20%)
# --result_path: 결과 저장 경로
