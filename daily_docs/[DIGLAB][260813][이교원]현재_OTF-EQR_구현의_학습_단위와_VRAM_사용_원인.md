지난 미팅 (2026-08-12)
- GS의 Gaussian·camera parameter update가 실제로 1 view 단위인지 코드로 확인하기.
- mini-batch와 active window를 구분하고, active window 영상을 모두 GPU에 상주시킬 필요가 있는지 확인하기.
- 과거 OOM 조건을 재현하여 VRAM과 system memory 중 실제 원인을 구분하기.

합의 사항 → 상태
- [완료] 한 optimizer step에서 1개 keyframe view를 렌더링하고 Gaussian과 camera parameter를 함께 갱신함을 확인함.
- [완료] active window는 mini-batch가 아니라 optimizer가 view를 선택하는 후보 집합임을 확인함.
- [완료] active window 전체의 GPU 상주는 필수 조건이 아니라 현재 코드의 keyframe 관리 방식임을 확인함.
- [진행] 동일한 outdoor scene과 active window 50 조건으로 OOM 재현 및 keyframe memory 분리 실험 진행 중임.

이번 결과 / 막힌 것 / 다음
- 결과: 기존 OOM은 1-view mini-batch 계산보다 과거 keyframe의 image·depth tensor가 system memory에 누적되면서 발생했음을 확인함.
- 막힌 것: 현재 코드는 학습 후보 집합과 GPU 상주 집합을 active_frames_gpu 하나로 함께 관리함.
- 다음: active window 50은 유지하고, 선택된 view만 GPU로 전송하는 keyframe cache 구조의 시간·메모리 변화를 비교함.

---

## 1. 개요
- 현재 OTF-EQR 구현에서 GS 학습의 mini-batch 단위와 active window의 역할을 코드 기준으로 확인함.
- 기존 outdoor scene의 OOM을 동일 조건으로 재현하고, OOM이 optimizer의 1-view 연산에서 발생한 것인지 과거 keyframe과 anchor가 누적되면서 발생한 것인지 구분함.

### 1-1. 확인 항목

| 항목               | 확인할 내용                                      |
| ---------------- | ------------------------------------------- |
| Mini-batch       | 한 optimizer step에서 사용하는 view 수              |
| Parameter update | Camera와 Gaussian parameter가 같은 step에서 갱신되는지 |
| Active window    | Mini-batch와 다른 개념인지                         |
| GPU 상주           | Active window 전체 영상을 GPU에 둘 필요가 있는지         |
| OOM              | VRAM과 시스템 메모리 중 실제 부족한 자원                   |
| 장기 실행            | Scene 길이에 따라 증가하는 메모리 항목                    |

---

## 2. OTF-EQR 학습 단위

### 2-1. Mini-batch 단위
- 현재 OTF-EQR의 Gaussian Splatting 학습은 한 optimizer step에서 keyframe view 1장을 사용함.
- 한 step에서 선택한 view 전체를 렌더링하고, GT 영상과 비교하여 L1·SSIM·depth loss를 계산한 뒤 한 번의 backward를 수행함.

### 2-2. Camera와 Gaussian parameter 갱신
- Train keyframe 한 장에서 계산한 동일한 loss에 대해 backward를 수행함.
- 이후 같은 optimizer step에서 다음 갱신을 수행함.
    1. 선택된 keyframe의 **camera·exposure·depth parameter** 갱신
    2. 해당 view에서 관측된 **Gaussian parameter** 갱신

---

## 3. Active window와 GPU 상주 구조

### 3-1. Active window의 역할
- Active window는 각 optimizer step에서 사용할 view를 선택하기 위한 후보 집합임.
- 예를 들어, Active window가 50이면 매 step마다 50장 중 1장을 선택함. (iteration은 default로 30)

### 3-2. 현재 upstream 코드의 동작
현재 upstream 코드는 `active_frames_gpu`를 다음 두 목적으로 함께 사용함.

- 학습할 keyframe을 선택하는 후보 목록
- 실제 GPU에 tensor가 상주한 keyframe 목록

CPU로 이동한 keyframe은 GPU 메모리만 해제되면서, 동시에 학습 후보에서도 제외됨.

따라서 active window 전체가 GPU에 있어야 하는 학습상의 제약이 있는 것이 아니라, 학습 후보 관리와 GPU 상주 관리를 하나의 목록으로 구현한 상태임.

### 3-3. GPU 상주의 이유

- Active window 영상을 GPU에 상주시키면 optimizer step마다 image·depth·confidence tensor를 CPU에서 GPU로 전송하지 않아도 됨.

- 이는 처리 시간을 줄이기 위한 구현 방식이지만, **mini-batch가 1 view이므로 active window 전체를 반드시 GPU에 보관할 필요는 없음.**

---

## 4. 기존 OOM 재현

### 4-1. 실행 조건

|항목|조건|
|---|---|
|Dataset|ODGS-SLAM `outdoor_Ex`|
|입력 영상|3,000 frames|
|입력 해상도|3840×1920|
|학습 해상도|1920×960, downsampling 2|
|Active window|50|
|Seed|0|
|Optimization|Keyframe당 30 iterations|

### 4-2. OOM 발생 지점

- 기존 구현은 frame 822, keyframe 295에서 프로세스가 종료됨.
- **시스템 메모리 부족**으로 프로세스가 종료된 경우였음.

| 항목                                | 종료 직전 값      |
| --------------------------------- | ------------ |
| 프로세스 메모리                          | 15,359.6 MiB |
| Keyframe image·depth CPU tensor   | 11,620.9 MiB |
| Frozen anchor Gaussian CPU tensor | 517.9 MiB    |
| 사용 가능한 시스템 메모리                    | 27.7 MiB     |

---

## 5. OOM 원인 분석

### 5-1. Keyframe tensor 누적

각 keyframe은 다음 데이터를 보관함.

- 입력 영상과 image pyramid
- Depth와 confidence
- Provider depth
- 최근 렌더링한 inverse range
- Mask
- Camera 및 exposure parameter

Anchor가 생성되면 과거 keyframe을 CPU로 이동하지만, `scene.keyframes`와 anchor가 해당 keyframe 객체를 계속 보관함.

따라서 VRAM 사용량은 감소하지만, **과거 keyframe의 image·depth tensor가 시스템 메모리에 계속 누적됨.**

### 5-2. Anchor Gaussian 누적

과거 Gaussian도 anchor 단위로 CPU에 저장됨.

다만 이번 OOM 직전에는 **keyframe CPU tensor가 11,620.9 MiB였고 frozen anchor Gaussian은 517.9 MiB**였음.

따라서 이번 OOM의 주원인은 **과거 keyframe의 image·depth tensor 누적**임.

---

## 6. 원 논문 비교

- 원 논문은 대규모 scene에서 Active Gaussian을 anchor로 저장하고 CPU로 이동하여 GPU 메모리를 제한한다고 설명함.
- CityWalk 실험에서는 anchor 적용 후 GPU 메모리가 약 150 images 이후 22 GB에서 안정화됐다고 보고함.
- 다만 원 논문의 실험 환경은 RTX 4090 24 GB와 시스템 메모리 128 GB이었음. (현재 컴퓨터는 RTX 4070Ti 12 GB와 시스템 메모리 32 GB인 상태, WSL에서는 사실상 15GB 사용 가능)

---
