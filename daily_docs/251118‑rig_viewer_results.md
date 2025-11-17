## 1. 전체 파이프라인 다이어그램
![](https://i.imgur.com/UYJGsfb.png)

## 2. 단계별 명령어 블록 요약

### 2.1 구동 환경
- `OS` : Windows 11 24H2 (PowerShell 사용)
- `CPU` : Ryzen 7700 (8코어 16스레드)
- `RAM` : DDR5 64GB
- `GPU` : RTX 4060Ti 16GB

### 2.2 360 영상 → 멀티 카메라 이미지 + 메타데이터 추출

1. Blender 360 Extractor Tool
    - `school_01.insv`를 입력으로 사용하여 5개의 카메라 뷰(Mid_Cam01 ~ Mid_Cam05)로 분해.
    - 각 타임스텝마다 동일한 인덱스의 파일명을 사용하여 5장의 이미지를 저장.
    - 5개 카메라가 링(Mid) 상에서 어떻게 배치되어 있는지에 대한 정적 rig 구성 정보를 camera_groups_2025-11-14.json으로 저장 (카메라별 위치·회전, 전체 링의 radius/height/tilt/rotation_offset 등).
    - 프레임별 타임스탬프 등 추가 메타데이터를 `frames_meta.json`에 저장.

**생성된 주요 파일/폴더:**
- `images_rig/Mid_Cam01/…, images_rig/Mid_Cam02/… … Mid_Cam05/…` : 5개 카메라별로 정리된 원본 이미지
- `camera_groups_2025-11-14.json` : Mid 링에서 사용된 5개 카메라(Mid_Cam01~Mid_Cam05)의 3D 위치·회전 및 링 파라미터를 정의하는 정적 rig 설정 파일
- `frames_meta.json` : 각 프레임의 타임스탬프 등 부가 메타데이터

![](https://i.imgur.com/PXwSa2b.png)
![](https://i.imgur.com/kbhLSms.png)


### 2.3 리그 정보 준비 (rig_config.json 생성)

- `camera_groups_2025-11-14.json`을 참고하여, COLMAP에서 요구하는 최소한의 rig 포맷(rig_id, cameras, image_prefix, ref_sensor)에 맞춘 `rig_config.json`을 작성함.

- 생성된 `rig_config.json` 내용
```json
[
  {
    "rig_id": 1,
    "cameras": [
      {
        "image_prefix": "Mid_Cam01/",
        "ref_sensor": true
      },
      {
        "image_prefix": "Mid_Cam02/"
      },
      {
        "image_prefix": "Mid_Cam03/"
      },
      {
        "image_prefix": "Mid_Cam04/"
      },
      {
        "image_prefix": "Mid_Cam05/"
      }
    ]
  }
]
```
- 의미
	- rig_id = 1 : 물리적인 Insta360 X5 장치 하나를 하나의 rig로 정의
	- image_prefix : 각 센서(카메라)에 해당하는 이미지가 들어있는 서브폴더 이름
		- 예: Mid_Cam01/ 아래의 모든 이미지 → rig 1의 sensor 1
	- ref_sensor: true : Mid_Cam01을 rig의 기준 좌표계로 사용 (나머지 카메라는 이 센서 기준 상대 자세로 표현)

**중요 : `camera_groups_2025-11-14.json`에 포함된 위치·회전 수치를 COLMAP에 직접 주입하지 않고, Mid_Cam01~05를 하나의 rig로 묶기 위한 센서 그룹 구성에만 활용함.**

### 2.4 COLMAP 재구성 (rig 정보 없이, baseline)

- rig 정보를 사용하지 않은 상태에서 우선 COLMAP automatic_reconstructor를 수행하여
baseline sparse 모델들을 생성함.
```powershell
& "C:\Users\kapr\Desktop\colmap-x64-windows-cuda\COLMAP.bat" automatic_reconstructor `
  --workspace_path . `
  --image_path images `
  --workspace_format STEREO `
  --sparse sparse_no_rig
```

- 생성된 각 모델 통계 확인 명령어 수행
```powershell
(base) PS C:\Users\kapr\Desktop\251114-school_01> & "C:\Users\kapr\Desktop\colmap-x64-windows-cuda\COLMAP.bat" model_analyzer --path sparse_no_rig\0
I20251118 00:18:29.339482  9196 model.cc:451] Rigs: 3
I20251118 00:18:29.339846  9196 model.cc:452] Cameras: 3
I20251118 00:18:29.339885  9196 model.cc:453] Frames: 7
I20251118 00:18:29.339917  9196 model.cc:454] Registered frames: 7
I20251118 00:18:29.339963  9196 model.cc:456] Images: 7
I20251118 00:18:29.340000  9196 model.cc:457] Registered images: 7
I20251118 00:18:29.340024  9196 model.cc:459] Points: 0
I20251118 00:18:29.340043  9196 model.cc:460] Observations: 0
I20251118 00:18:29.340067  9196 model.cc:462] Mean track length: 0.000000
I20251118 00:18:29.340093  9196 model.cc:464] Mean observations per image: 0.000000
I20251118 00:18:29.340119  9196 model.cc:467] Mean reprojection error: 0.000000px

(base) PS C:\Users\kapr\Desktop\251114-school_01> & "C:\Users\kapr\Desktop\colmap-x64-windows-cuda\COLMAP.bat" model_analyzer --path sparse_no_rig\1
I20251118 00:18:29.439260  9436 model.cc:451] Rigs: 2
I20251118 00:18:29.439616  9436 model.cc:452] Cameras: 2
I20251118 00:18:29.439661  9436 model.cc:453] Frames: 10
I20251118 00:18:29.439701  9436 model.cc:454] Registered frames: 10
I20251118 00:18:29.439726  9436 model.cc:456] Images: 10
I20251118 00:18:29.439751  9436 model.cc:457] Registered images: 10
I20251118 00:18:29.439773  9436 model.cc:459] Points: 3082
I20251118 00:18:29.439794  9436 model.cc:460] Observations: 7563
I20251118 00:18:29.439816  9436 model.cc:462] Mean track length: 2.453926
I20251118 00:18:29.439845  9436 model.cc:464] Mean observations per image: 756.300000
I20251118 00:18:29.439867  9436 model.cc:467] Mean reprojection error: 1.025990px

(base) PS C:\Users\kapr\Desktop\251114-school_01> & "C:\Users\kapr\Desktop\colmap-x64-windows-cuda\COLMAP.bat" model_analyzer --path sparse_no_rig\2
I20251118 00:18:33.467528  5060 model.cc:451] Rigs: 5
I20251118 00:18:33.467958  5060 model.cc:452] Cameras: 5
I20251118 00:18:33.468013  5060 model.cc:453] Frames: 290
I20251118 00:18:33.468056  5060 model.cc:454] Registered frames: 290
I20251118 00:18:33.468083  5060 model.cc:456] Images: 290
I20251118 00:18:33.468109  5060 model.cc:457] Registered images: 290
I20251118 00:18:33.468172  5060 model.cc:459] Points: 78610
I20251118 00:18:33.468192  5060 model.cc:460] Observations: 569350
I20251118 00:18:33.468231  5060 model.cc:462] Mean track length: 7.242717
I20251118 00:18:33.468270  5060 model.cc:464] Mean observations per image: 1963.275862
I20251118 00:18:33.468317  5060 model.cc:467] Mean reprojection error: 0.919648px
```

**결과**
- 0번 : Frames 7, Points 0 (실패)
- 1번 : Frames 10, Points 3,082 (부분 유효)
- 2번 : Frames 290, Images 290, Points 78,610, Mean reprojection error ≈ 0.92 px (주 모델)

**충분한 프레임 수(290장)와 포인트 수(78,610개)를 가지며, 재투영 오차가 약 0.92 px 수준인 sparse_no_rig\2 모델을 이후 rig 구성 실험의 기준 모델로 선정함.**

### 2.5 rig_configurator로 rig 기반 모델 생성

1. 출력 폴더 생성
```powershell
New-Item -ItemType Directory -Path sparse_rig -ErrorAction SilentlyContinue | Out-Null
```

2. rig_configurator 실행
```powershell
& "C:\Users\kapr\Desktop\colmap-x64-windows-cuda\COLMAP.bat" rig_configurator `
  --database_path database.db `
  --input_path sparse_no_rig\2 `
  --rig_config_path rig_config.json `
  --output_path sparse_rig
```
- 역할:
	- `database.db`에서 각 이미지의 카메라 ID/파일명을 읽음
	- `rig_config.json`의 image_prefix와 매칭해서 **이 이미지들은 동일 시점의 5카메라 세트**라는 rig frame을 구성함.
	- sparse_no_rig\2의 camera pose를 그대로 사용하되, **rig 단위(Frame)**와 센서(sensor) 구조로 재조직함.

3. 새 모델 확인
```powershell
(base) PS C:\Users\kapr\Desktop\251114-school_01> & "C:\Users\kapr\Desktop\colmap-x64-windows-cuda\COLMAP.bat" model_analyzer `
>>   --path sparse_rig
I20251117 13:13:08.637059  4976 model.cc:451] Rigs: 1
I20251117 13:13:08.637505  4976 model.cc:452] Cameras: 5
I20251117 13:13:08.637548  4976 model.cc:453] Frames: 58
I20251117 13:13:08.637578  4976 model.cc:454] Registered frames: 58
I20251117 13:13:08.637605  4976 model.cc:456] Images: 290
I20251117 13:13:08.637641  4976 model.cc:457] Registered images: 290
I20251117 13:13:08.637687  4976 model.cc:459] Points: 78610
I20251117 13:13:08.637706  4976 model.cc:460] Observations: 569350
I20251117 13:13:08.637740  4976 model.cc:462] Mean track length: 7.242717
I20251117 13:13:08.637775  4976 model.cc:464] Mean observations per image: 1963.275862
I20251117 13:13:08.637928  4976 model.cc:467] Mean reprojection error: 0.919648px
```
- 결과:
	- Points / Observations / reprojection error가 sparse_no_rig\2 와 동일함.
	- 기하 정보는 그대로 유지하면서 **rig 구조만 입힌** 상태가 됨됨.

---
## 3. Viewer에서 시각적 검증

### 3.1 시각적 검증 방식
1. ROI 선택 : 이미지를 4×4 격자(16개 셀)로 분할
2. 분산 분석 : 각 셀에 대해 픽셀 강도 분산 계산
3. 상위 8개 선택 : 분산이 가장 높은 8개 셀 선택(텍스처가 풍부한 영역)
4. 지표 계산 : 전체 영역 및 ROI 모두에 대해 PSNR 및 SSIM 계산

### 3.2.1 View 1 - 포스터 및 시계 디테일 비교
![](https://i.imgur.com/lfFzNeF.jpeg)

| Method   | PSNR (Global) | SSIM (Global) | PSNR (ROI Mean) | SSIM (ROI Mean) |
| -------- | ------------- | ------------- | --------------- | --------------- |
| auto     | 28.92 dB      | 0.9133        | 28.05 dB        | 0.8936          |
| no_rig_2 | 23.24 dB      | 0.8603        | 21.48 dB        | 0.7822          |
| rig      | 33.07 dB      | 0.9510        | 32.46 dB        | 0.9451          |
### 3.2.2 View 2 - 기둥 + 목재 텍스처 비교 1
![](https://i.imgur.com/KsNKpGx.jpeg)

| Method | PSNR (Global) | SSIM (Global) | PSNR (ROI Mean) | SSIM (ROI Mean) |
|--------|---------------|---------------|-----------------|-----------------|
| auto | 29.11 dB | 0.9349 | 28.93 dB | 0.9078 |
| no_rig_2 | 23.11 dB | 0.8909 | 22.61 dB | 0.8224 |
| rig | 33.38 dB | 0.9610 | 32.91 dB | 0.9427 |
### 3.2.3 View 3 - 외부 출입문 + 기둥 + 목재 텍스처 비교
![](https://i.imgur.com/fGSIhPs.jpeg)

| Method | PSNR (Global) | SSIM (Global) | PSNR (ROI Mean) | SSIM (ROI Mean) |
|--------|---------------|---------------|-----------------|-----------------|
| auto | 31.90 dB | 0.9547 | 30.94 dB | 0.9333 |
| no_rig_2 | 24.38 dB | 0.9218 | 23.92 dB | 0.8659 |
| rig | 33.38 dB | 0.9631 | 33.30 dB | 0.9450 |

### 3.2.4 View 4 - 기둥 + 목재 텍스처 비교 2
![](https://i.imgur.com/lBHr67T.jpeg)

| Method   | PSNR (Global) | SSIM (Global) | PSNR (ROI Mean) | SSIM (ROI Mean) |
| -------- | ------------- | ------------- | --------------- | --------------- |
| auto     | 31.00 dB      | 0.9512        | 29.24 dB        | 0.9317          |
| no_rig_2 | 25.25 dB      | 0.9249        | 23.96 dB        | 0.8780          |
| rig      | 34.25 dB      | 0.9728        | 33.25 dB        | 0.9596          |

### 3.3 방법별 PSNR / SSIM 비교 결과

- 네 개의 뷰(View 1~4) 모두에서 PSNR·SSIM 지표가 rig > auto > no_rig_2 순으로 나타남.
- 특히 rig 설정을 적용한 경우, Global 지표뿐 아니라 텍스처가 풍부한 ROI에서도 auto 대비 수 dB 높은 PSNR과 더 큰 SSIM을 보임.
- 반대로 no_rig_2는 카메라 포즈 정렬이 불안정하여, 바닥 반사나 유리문 주변에서 블러 및 고스팅이 두드러지고, 정량 지표도 가장 낮게 측정됨.
- 따라서, Insta360 X5의 5개 카메라 이미지를 rig 단위로 취급하여 포즈를 정렬하는 방식이 viewer에서의 시각적 품질 향상에 실질적인 효과가 있음을 확인함.


---
