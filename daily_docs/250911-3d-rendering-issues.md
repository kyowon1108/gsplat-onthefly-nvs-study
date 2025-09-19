## 문제 상황
- `render.py`로 렌더링하면 결과가 나오지 않았음
- 최적화된 가우시안 포인트 클라우드를 3D로 실시간 뷰어로 보고 싶었음
- SIBR viewer 빌드 시 의존성 문제 발생

## 해결 과정 및 시행착오

### 1. render.py 문제 해결

```bash
# conda 환경 활성화 필요
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gaussian_splatting

# 모델 경로 지정하여 실행
python render.py -m output/truck
```

**결과**: 251개의 다양한 각도에서 렌더링된 이미지가 `output/truck/train/ours_30000/renders/`에 생성됨

### 2. SIBR Viewer 빌드 문제 해결

#### 주요 의존성 문제들

**A. OpenCV 버전 문제**
```bash
# 에러: OpenCV 4.5 required but 4.2.0 found
find_package(OpenCV 4.5 REQUIRED)
```
- Perplexity에 검색한 결과, cmake 설정 파일을 수정하면 괜찮다고 답변함.
- 이전에 4.5.5 버전으로 설치하다가 환경변수 경로가 꼬여서 실패함.

**✅ 해결**: cmake 설정 파일 수정
```bash
# SIBR_viewers/cmake/linux/dependencies.cmake 수정
# 248번 줄 변경
find_package(OpenCV 4.2 REQUIRED)  # 4.5 → 4.2로 변경
```

**B. Embree 버전 문제**
```bash
# 에러: embree 3.0 required but 4.4.0 found
find_package(embree 3.0 )
```
- 4.4.0 버전을 다운로드 했는데, 3.0을 요구해서 검색해보니 요구사항을 제거하면 이슈가 없을 것이라고 함.

**✅ 해결**: 버전 요구사항 제거
```bash
# 127번 줄 수정
find_package(embree )  # 버전 요구사항 제거
```

#### 빌드 과정

**✅ 성공적인 빌드 명령어**
```bash
cd SIBR_viewers
rm -rf build && mkdir build && cd build

# cmake 설정
cmake .. -DCMAKE_BUILD_TYPE=Release -DSIBR_BUILD_REMOTE_SERVER=ON -DSIBR_BUILD_GAUSSIAN_VIEWER=ON

# 빌드 (멀티코어 사용)
make -j$(nproc)

# 설치
make install
```

## 최종 완성된 명령어 세트

### 환경 설정
```bash
# conda 환경 활성화
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gaussian_splatting
cd /home/kapr/Desktop/gaussian-splatting
```

### 1. 이미지 렌더링
```bash
# 최적화된 가우시안 포인트 클라우드로 이미지 렌더링
python render.py -m output/truck

# 결과 확인
ls output/truck/train/ours_30000/renders/  # 렌더링된 이미지들
ls output/truck/test/ours_30000/renders/   # 테스트 이미지들
```

### 2. 3D 뷰어 (SIBR Gaussian Viewer)
```bash
# SIBR 뷰어 실행
./SIBR_viewers/install/bin/SIBR_gaussianViewer_app --model-path output/truck

# 다양한 옵션들
./SIBR_viewers/install/bin/SIBR_gaussianViewer_app \
  --model-path output/truck \
  --width 1920 --height 1080 \
  --fullscreen
```

### 3. 다른 모델들 뷰어로 보기
```bash
# 다른 최적화된 가우시안 포인트 클라우드들
./SIBR_viewers/install/bin/SIBR_gaussianViewer_app --model-path output/truck_test
python view_3d.py -m output/truck_test --port 8083
```

## 주요 파일들 위치

### 최적화된 가우시안 포인트 클라우드
```
output/truck/point_cloud/iteration_30000/point_cloud.ply  # 메인 모델 파일
output/truck/cfg_args                                     # 설정 파일
```

### 렌더링 결과
```
output/truck/train/ours_30000/renders/                    # 최적화에 사용된 카메라 뷰포인트에서의 렌더링 결과
output/truck/test/ours_30000/renders/                     # 최적화에 사용되지 않은 새로운 카메라 뷰포인트에서의 렌더링 결과 (Novel View Synthesis)
```

### 뷰어 바이너리
```
SIBR_viewers/install/bin/SIBR_gaussianViewer_app          # SIBR 뷰어
SIBR_viewers/install/bin/SIBR_remoteGaussian_app          # 리모트 뷰어
```

## 시스템 요구사항

### 필수 패키지들
```bash
# 시스템 패키지들 (이미 설치됨)
- OpenCV 4.2.0
- GLFW 3
- GLEW
- Assimp
- Boost
- CUDA 11.8
- Embree 4.4.0
```

## 성능 정보

### 모델 크기
- **Gaussian splats**: 2,068,025개 포인트
- **모델 파일 크기**: ~100MB
- **메모리 사용량**: 4GB ~ 10GB (GPU) - 처음에는 4GB정도 먹다가, 후반으로 갈 수록 메모리를 더 먹으면서 작동함. ==원인은 아직 찾아보지 않음.==

### 렌더링 성능
- **SIBR Viewer**: 실시간 (30+ FPS)

## 트러블슈팅

### 일반적 문제들
1. **conda 환경 미활성화**: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate gaussian_splatting`
2. **DISPLAY 변수 미설정**: GUI 뷰어를 위해 X11 forwarding 필요
3. **CUDA 메모리 부족**: GPU 메모리 24GB 권장이라고 공식문서에 나옴. 테스트케이스는 크게 메모리를 먹지 않았지만 많은 사진을 처리할 겨우 기하급수적으로 늘어날 것으로 예상함.

### SIBR 빌드 문제
1. **의존성 버전 충돌**: cmake 파일에서 버전 요구사항 완화
2. **컴파일 경고**: 무시해도 됨 (정상 빌드됨)

## 조작법

![](https://i.imgur.com/33VIjAN.png)

### SIBR Viewer 조작법
- **마우스 드래그**: 시점 회전
- **마우스 휠**: 줌 인/아웃
- **키보드 Y**: Trackball/WASD 모드 전환
