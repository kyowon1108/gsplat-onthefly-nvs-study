## 0. 환경 정리
- OS : Ubuntu 22.04
- GPU : RTX 4060Ti 16GB
- CUDA version : 11.8
- Python version : 3.9.*

## 1. 기존 설치 정리 (Cleanup)
- 환경변수 설정(~/bashrc), apt 버전 충돌 해결 등으로 여럿 건드린 것이 있어서, 일단 git clone한 내용을 한번 초기화한 후 진행.
### 기존 디렉토리 및 환경 확인
```bash
# 기존 gaussian 관련 디렉토리 검색
find /home/kapr -name "*gaussian*" -type d 2>/dev/null | head -10

# 기존 conda 환경 확인
conda env list | grep -i gaussian

# 기존 pip 패키지 확인
pip list | grep -i gaussian
```

### 기존 설치 제거
```bash
# 기존 디렉토리 삭제
rm -rf /home/kapr/Desktop/gaussian-splatting

# 기존 conda 환경들 삭제
conda env remove -n gaussian_splatting -y
conda env remove -n gaussian_splatting_py38 -y
```

## 2. GPU 및 CUDA 설정

### Nvidia driver 설치
``` shell
# 그래픽카드 최신 상황에 맞춰 driver 설치
sudo apt install ubuntu-drivers-common -y

ubuntu-drivers devices
sudo ubuntu-drivers autoinstall

sudo reboot
```

### CUDA 설치 (기존 것 제거)
``` shell
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run

sudo chmod +x cuda_11.8.0_520.61.05_linux.run
sudo sh cuda_11.8.0_520.61.05_linux.run
```

### Miniconda 설치 (기존 것 제거)
``` shell
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

bash Miniconda3-latest-Linux-x86_64.sh
source ~/.bashrc
```

### GPU 상태 확인
```bash
# GPU 정보 및 CUDA 드라이버 확인
nvidia-smi

# NVCC 컴파일러 버전 확인
nvcc --version
```

**출력 결과:**
- GPU: NVIDIA GeForce RTX 4060 Ti (16GB)
- CUDA Driver: 12.8
- NVCC: CUDA 11.8 (컴파일 타겟)

## 3. Gaussian Splatting 저장소 복제

```bash
# 저장소 복제 (서브모듈 포함)
git clone https://github.com/graphdeco-inria/gaussian-splatting --recursive
```
- recursive를 안붙이면 서브 모듈이 다운로드가 안되었음.
## 4. Conda 환경 생성 및 설정

### 새로운 conda 환경 생성
```bash
# Python 3.9 환경 생성
conda create -n gaussian_splatting python=3.9 -y
```
- 기존 3.7, 3.8 환경에서 실행하니 충돌나는 경우가 있었어서, 3.9로 시행함.

### 환경 활성화 및 PyTorch 설치
```bash
# conda 스크립트 소스 및 환경 활성화
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gaussian_splatting

# PyTorch 2.0.1 + CUDA 11.8 설치 (시간 소요: 약 5분)
pip install torch==2.0.1 torchvision==0.15.2 --index-url https://download.pytorch.org/whl/cu118
```

## 5. Python 의존성 설치

### 기본 패키지들 설치
```bash
# 활성화된 환경에서 기본 패키지 설치
conda activate gaussian_splatting
pip install plyfile tqdm opencv-python joblib
```

## 6. CUDA 확장 모듈 빌드

### 각 서브모듈 빌드 및 설치
```bash
cd /home/kapr/Desktop/gaussian-splatting

# diff-gaussian-rasterization 빌드
pip install submodules/diff-gaussian-rasterization/

# simple-knn 빌드
pip install submodules/simple-knn/

# fused-ssim 빌드
pip install submodules/fused-ssim/
```

## 7. 설치 확인 테스트

### CUDA 및 PyTorch 작동 확인
```bash
# CUDA 가용성 및 GPU 정보 확인
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}'); print(f'Device count: {torch.cuda.device_count()}'); print(f'Current device: {torch.cuda.current_device()}'); print(f'Device name: {torch.cuda.get_device_name(0)}')"
```

### CUDA 확장 모듈 임포트 테스트
```bash
# 주요 CUDA 확장들 임포트 테스트
python -c "from diff_gaussian_rasterization import GaussianRasterizationSettings, GaussianRasterizer; print('diff_gaussian_rasterization: OK'); from fused_ssim import fused_ssim; print('fused_ssim: OK'); print('CUDA extensions working!')"
```

## 8. 테스트 데이터셋 다운로드

### 데이터 디렉토리 생성 및 데이터셋 다운로드
```bash
# 데이터 디렉토리 생성
mkdir -p /home/kapr/Desktop/gaussian-splatting/data
cd /home/kapr/Desktop/gaussian-splatting/data

# Tanks and Temples 데이터셋 다운로드 (651MB)
wget https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/datasets/input/tandt_db.zip

# 압축 해제
unzip tandt_db.zip
```

### 데이터셋 구조 확인
```bash
# 다운로드된 데이터셋 확인
ls /home/kapr/Desktop/gaussian-splatting/data/
ls /home/kapr/Desktop/gaussian-splatting/data/tandt/
```

## 9. 학습 명령어

### 전체 학습 (기본 30,000 iteration)
```bash
# 환경 활성화
conda activate gaussian_splatting
cd /home/kapr/Desktop/gaussian-splatting

# 전체 학습 실행
python train.py -s data/tandt/truck -m output/truck
python train.py -s data/tandt/train -m output/train
python train.py -s data/db/drjohnson -m output/drjohnson
python train.py -s data/db/playroom -m output/playroom
```
![](https://i.imgur.com/Kp4SSs5.png)

### 렌더링
```bash
# 최적화된 가우시안 포인트 클라우드로 렌더링
python render.py -m output/truck

# 특정 해상도로 렌더링
python render.py -m output/truck --resolution 1920
```
![](https://i.imgur.com/SgciQ16.png)

- 어떤 문제가 있는지 모르지만, 실행이 끝까지 되지 않았음.
### 평가 메트릭 계산 (아직 미시행)
```bash
# PSNR, SSIM, LPIPS 등 계산
python metrics.py -m output/truck
```


## 10. 재부팅 등 다시 시작하는 경우

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gaussian_splatting
```