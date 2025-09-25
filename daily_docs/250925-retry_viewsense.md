# Room2_640480 처리 과정 전체 명령어

## 처리 단계

### 1. COLMAP 처리 스크립트 생성
```bash
python3 run_colmap_room2.py
```

### 2. COLMAP 실행 (conda 환경 활성화 후)
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate gaussian_splatting && python run_colmap_room2.py
```

### 3. COLMAP 출력을 Gaussian Splatting 형식으로 변환
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate gaussian_splatting && python convert.py -s data/room2_640480 --skip_matching
```

### 4. 디렉토리 구조 조정 (convert.py 오류 해결)
```bash
cp -r data/room2_640480/colmap_workspace data/room2_640480/distorted
```

### 5. 다시 변환 실행
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate gaussian_splatting && python convert.py -s data/room2_640480 --skip_matching
```

### 6. 전체 변환 (포인트 클라우드 생성 포함)
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate gaussian_splatting && python convert.py -s data/room2_640480
```

### 7. 학습 실행
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate gaussian_splatting && python train.py -s data/room2_640480 --eval
```

### 8. 렌더링 실행
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate gaussian_splatting && python render.py -m output/[checkpoint_directory] -s data/room2_640480
```

### 9. 뷰어 실행
```bash
./SIBR_viewers/install/bin/SIBR_gaussianViewer_app --model-path output/room2_640480
```

## 카메라 파라미터

Intel RealSense D435 640x480 카메라 파라미터:
- fx = 382.613
- fy = 382.613
- cx = 320.183
- cy = 237.712

## 결과 시각화

### 뷰어 데모 GIF
<!-- 10초 분량의 뷰어 움직임 GIF 추가 예정 -->
![Viewer Demo](./viewer_demo_250925.gif)

## 평가 결과

### 정량적 메트릭
- **SSIM**: [값 추가 예정]
- **LPIPS**: [값 추가 예정]
- **PSNR**: [값 추가 예정]

## 이유 분석

### input된 이미지 수
![](250925_viewsense_input_image_list.png)
- 총 370개의 640x480 이미지를 사용함.

### 처리된 이미지 수
![](250925_viewsense_images_image_list.png)