### 1. Feature Extraction (특징점 추출)
```bash
cd ~/Desktop/gaussian-splatting/data/toilet_tissue colmap feature_extractor --database_path database.db --image_path images
```

- 428개 이미지에서 SIFT 특징점 추출
- 각 이미지당 약 2,000-5,000개 특징점 추출
- SIMPLE_RADIAL 카메라 모델로 자동 설정

### 2. Sequential Matching (순차 매칭)
```bash
colmap sequential_matcher --database_path database.db
```

- 428개 이미지 간 특징점 매칭
- 4,881개의 매치 생성
- 0.452분 소요 (exhaustive_matcher보다 훨씬 빠름)

### 3. Sparse Reconstruction (희소 재구성)
```bash
colmap mapper --database_path database.db --image_path images --output_path sparse/0
```

- 367개 이미지 등록 성공
- Bundle adjustment로 카메라 파라미터 최적화
- 생성된 파일들:
    - cameras.bin (24KB) - 카메라 파라미터
    - images.bin (46MB) - 이미지 정보 및 포즈
    - points3D.bin (18MB) - 3D 포인트 클라우드
    - project.ini (1.5KB) - 프로젝트 설정

### 4. Image Undistortion (이미지 왜곡 보정)
```bash
colmap image_undistorter --image_path images --input_path sparse/0 --output_path undistorted --output_type COLMAP
```

- 문제: SIMPLE_RADIAL → PINHOLE 변환 필요 (Gaussian Splatting 호환성)
- 428개 이미지 모두 왜곡 보정
- 0.116분 소요
- 최종 결과: undistorted/sparse/0/ 에 PINHOLE 카메라 모델 파일들 생성

### 5. Directory Structure Fix
```bash
cd ~/Desktop/gaussian-splatting/data/toilet_tissue/undistorted mkdir -p sparse/0 mv sparse/*.bin sparse/0/
```

- Gaussian Splatting이 기대하는 디렉토리 구조로 맞춤

### 6. 최종 결과
- 127,659개 3D 포인트 생성
 - 428개 카메라 모두 정상 등록
- PINHOLE 카메라 모델로 변환 완료
- train.py 성공적 실행 (10 iterations 테스트)