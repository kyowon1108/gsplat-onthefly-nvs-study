## 문제 상황
- `python metrics.py -m output/toilet_tissue` 실행 시 모든 메트릭이 NaN 값으로 출력됨
- SSIM, PSNR, LPIPS 모두 `nan` 표시
- 메트릭 평가가 제대로 작동하지 않음

```bash
Scene: output/toilet_tissue
Method: ours_30000

SSIM : nan
PSNR : nan
LPIPS: nan
```

## 문제 원인 분석
### 1. 근본 원인
- **Test 이미지 부재**: 메트릭 계산을 위한 렌더링된 테스트 이미지가 없었음
- `output/toilet_tissue/test/ours_30000/renders/` 디렉토리가 비어있음 (0개 파일)
- 원본 학습이 `--eval` 플래그 없이 진행되어 train/test 분할이 없었음
  
### 2. 메트릭 계산 원리
메트릭 평가를 위해서는 다음 구조가 필요:
```
output/toilet_tissue/
└── test/
└── ours_30000/
├── gt/ # Ground truth 이미지 (원본)
└── renders/ # 렌더링된 이미지 (비교 대상)
```
  
메트릭은 렌더링된 이미지와 ground truth 이미지를 비교하여 계산됨:
- **PSNR**: 픽셀 단위 차이 측정
- **SSIM**: 구조적 유사성 측정
- **LPIPS**: 지각적 유사성 측정
  
## 해결 과정
  
### 1. Test Split 생성
```bash
# COLMAP sparse/0 디렉토리로 이동
cd ~/Desktop/gaussian-splatting/data/toilet_tissue/sparse/0
  
# LLFF 관례에 따라 8번째마다 테스트 이미지로 지정하는 test.txt 파일 생성
python3 -c "
with open('images.txt', 'r') as f:
lines = f.readlines()
  
test_images = []
image_lines = [line for line in lines if line.strip() and not line.startswith('#')]
  
# Take every 8th image as test (LLFF convention)
for i, line in enumerate(image_lines):
if i % 8 == 0: # Every 8th image becomes test
image_id = line.strip().split()[0]
test_images.append(image_id)
  
# Write test.txt file
with open('test.txt', 'w') as f:
for img_id in test_images:
f.write(img_id + '\n')
  
print(f'Created test split with {len(test_images)} test images out of {len(image_lines)} total images')
"
```
  
**결과**: 856개 이미지 중 107개를 테스트 이미지로 분할
  
### 2. Test 이미지 렌더링
```bash
# 환경 활성화
cd ~/Desktop/gaussian-splatting
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gaussian_splatting
  
# --eval 플래그와 함께 렌더링 실행
python render.py -m output/toilet_tissue --eval
```

**결과**:
- LLFF hold-out 방식 인식: `"------------LLFF HOLD-------------"`
- 374개 훈련 이미지 렌더링
- 54개 테스트 이미지 렌더링 생성
  
### 3. 최종 메트릭 평가
```bash
# 메트릭 계산 실행
python metrics.py -m output/toilet_tissue
```

## 해결 결과  

### ✅ 성공적인 메트릭 값 획득
```bash
Scene: output/toilet_tissue
Method: ours_30000

SSIM : 0.9538822 # 매우 높은 구조적 유사성 (1에 가까울수록 좋음)
PSNR : 36.1466827 # 높은 화질 (일반적으로 30dB 이상이면 양호)
LPIPS: 0.0935497 # 낮은 지각적 거리 (0에 가까울수록 좋음)
```
  
### 📊 메트릭 해석
- **SSIM 0.954**: 원본과 렌더링 결과가 매우 유사한 구조를 가짐
- **PSNR 36.15dB**: 높은 품질의 복원 성능
- **LPIPS 0.094**: 인간의 지각으로 봤을 때 원본과 매우 유사


### 📁 생성된 파일 구조

```
output/toilet_tissue/
├── train/
│ └── ours_30000/
│ └── renders/ # 374개 훈련 렌더링 이미지
└── test/
└── ours_30000/
├── gt/ # 54개 ground truth 이미지
└── renders/ # 54개 테스트 렌더링 이미지
```

## 학습된 교훈  
### 1. Train/Test Split의 중요성
- Gaussian Splatting에서 제대로 된 평가를 위해서는 `--eval` 플래그가 필수
- 메트릭 계산은 학습에 사용되지 않은 테스트 이미지에서만 의미가 있음
  
### 2. LLFF Convention
- 매 8번째 이미지를 테스트로 사용하는 것이 표준
- `test.txt` 파일로 수동 분할 가능
  
### 3. 올바른 렌더링 방법
```bash
# 잘못된 방법 (테스트 이미지 생성 안됨)
python render.py -m output/model_name

# 올바른 방법 (테스트 이미지 생성됨)
python render.py -m output/model_name --eval
```

## 향후 권장사항

### 새로운 데이터셋 학습 시

```bash
# 처음부터 eval 모드로 학습
python train.py -s data/dataset_name -m output/model_name --eval

# 렌더링 (자동으로 test split 적용됨)
python render.py -m output/model_name --eval

# 메트릭 계산
python metrics.py -m output/model_name
```

### 기존 모델 평가 시
1. Test split 생성 (`test.txt` 파일)
2. `--eval` 플래그로 재렌더링
3. 메트릭 계산
