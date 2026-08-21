# PostShot 3DGS 학습 결과 비교

## 1. 실험 환경

| 항목 | 값 |
|------|---|
| 플랫폼 | Windows 11 24H2 |
| CPU | AMD Ryzen 7 7700 (8 core / 16 threads) |
| GPU | NVIDIA GeForce RTX 4060 Ti (16GB) |
| 도구 | PostShot |
| 데이터셋 | 새빛관 (260111 SfM 결과 기반) |

## 2. 실행 시간

| 조건 | 소요 시간 |
|------|----------|
| No Rig | 22분 48초 |
| Rig | 22분 04초 |

## 3. 정성적 결과

### 3.1 임의 샘플 6개 비교

| Id | Raw | No Rig | Rig |
|-----------|-----|--------|-----|
| 1 | <img src="../video_picture/260113/260113-raw_20.webp" width="250"> | <img src="../video_picture/260113/260113-no_rig_20.webp" width="250"> | <img src="../video_picture/260113/260113-rig_20.webp" width="250"> |
| 2 | <img src="../video_picture/260113/260113-raw_40.webp" width="250"> | <img src="../video_picture/260113/260113-no_rig_40.webp" width="250"> | <img src="../video_picture/260113/260113-rig_40.webp" width="250"> |
| 3 | <img src="../video_picture/260113/260113-raw_60.webp" width="250"> | <img src="../video_picture/260113/260113-no_rig_60.webp" width="250"> | <img src="../video_picture/260113/260113-rig_60.webp" width="250"> |
| 4 | <img src="../video_picture/260113/260113-raw_80.webp" width="250"> | <img src="../video_picture/260113/260113-no_rig_80.webp" width="250"> | <img src="../video_picture/260113/260113-rig_80.webp" width="250"> |
| 5 | <img src="../video_picture/260113/260113-raw_100.webp" width="250"> | <img src="../video_picture/260113/260113-no_rig_100.webp" width="250"> | <img src="../video_picture/260113/260113-rig_100.webp" width="250"> |
| 6 | <img src="../video_picture/260113/260113-raw_120.webp" width="250"> | <img src="../video_picture/260113/260113-no_rig_120.webp" width="250"> | <img src="../video_picture/260113/260113-rig_120.webp" width="250"> |

## 4. 정량적 결과

> Raw 이미지(1920x1920)를 렌더링 해상도(1177x1177)로 리사이즈하여 비교함

### 4.1 개별 결과

| Id | No Rig PSNR | Rig PSNR | No Rig SSIM | Rig SSIM | No Rig LPIPS | Rig LPIPS |
|----|-------------|----------|-------------|----------|--------------|-----------|
| 1 | 21.72 | 24.04 | 0.7236 | 0.8261 | 0.1942 | 0.0978 |
| 2 | 24.00 | 25.21 | 0.8319 | 0.8588 | 0.1402 | 0.0825 |
| 3 | 20.53 | 23.63 | 0.6989 | 0.8287 | 0.2226 | 0.1375 |
| 4 | 20.19 | 21.08 | 0.7207 | 0.8078 | 0.2062 | 0.1458 |
| 5 | 24.19 | 23.44 | 0.7875 | 0.7875 | 0.1809 | 0.1467 |
| 6 | 21.55 | 22.20 | 0.6903 | 0.7450 | 0.2757 | 0.1802 |

### 4.2 평균 결과

| 조건 | PSNR | SSIM | LPIPS |
|------|------|------|-------|
| No Rig | 22.03 | 0.7421 | 0.2033 |
| Rig | 23.27 | 0.8090 | 0.1317 |

### 4.3 분석

**Rig SfM이 모든 지표에서 우수함.**
- PSNR: +1.24 dB (23.27 vs 22.03)
- SSIM: +0.067 (0.8090 vs 0.7421)
- LPIPS: -0.072 (0.1317 vs 0.2033)

**But, PSNR이 전반적으로 낮은 이유**
- Raw -> 렌더링 해상도 리사이즈로 인한 GT 품질 저하
- NVS 특성상 25~35dB가 일반적인 범위 (3DGS 논문 기준)
- Test view 렌더링 시 학습 뷰와의 차이 존재

## 5. 결론

1. **Rig SfM 적용 시 3DGS 품질 향상** : 모든 정량 지표에서 No Rig 대비 개선
2. **실행 시간 유사** : Rig 22분 04초 vs No Rig 22분 48초 (Rig가 약간 빠름)
3. **3D 포인트 증가 효과** : 260111 SfM 결과에서 Rig 적용 시 3D 포인트 35% 증가가 3DGS 학습 품질에 긍정적 영향
