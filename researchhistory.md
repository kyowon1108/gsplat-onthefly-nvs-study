# Research History Index

> 3D Gaussian Splatting On-the-fly NVS 연구 문서의 중앙 인덱스

---

## Phase 1: 환경 구축 & 기초 학습 (9/11 ~ 9/13)

- [250911-installation-commands.md](daily_docs/250911-installation-commands.md) - Ubuntu 22.04 + CUDA 11.8 + Gaussian Splatting 설치
- [250911-3d-rendering-issues.md](daily_docs/250911-3d-rendering-issues.md) - SIBR Viewer 빌드 문제 해결 (OpenCV/Embree 버전 충돌)
- [250911-sparse-settings.md](daily_docs/250911-sparse-settings.md) - COLMAP Sparse Reconstruction 파이프라인 정리
- [250912-first-feedback.md](daily_docs/250912-first-feedback.md) - 평가 메트릭(PSNR, SSIM, LPIPS) 학습 및 용어 정리
- [250912-metrics-issues.md](daily_docs/250912-metrics-issues.md) - Train/Test Split

---

## Phase 2: Intel RealSense D435 실험 (9/19 ~ 10/16)

- [250919-third-feedback.md](daily_docs/250919-third-feedback.md) - RealSense D435 첫 실내 촬영, 카메라 파라미터 고정 실험
- [250925-retry-viewsense.md](daily_docs/250925-retry-viewsense.md) - 640x480 해상도 실험, SSIM 0.75로 품질 낮음 확인
- [250929-try-viewsense-fhd.md](daily_docs/250929-try-viewsense-fhd.md) - FHD 해상도 실험 iPhone 촬영 이미지와의 차이 분석
- [250929-try-viewsense-fhd-report.md](daily_docs/250929-try-viewsense-fhd-report.md) - D435 vs iPhone 품질 비교 상세 분석
- [251002-outdoor-camera-params-comparison.md](daily_docs/251002-outdoor-camera-params-comparison.md) - 야외 환경 실험, 고정 파라미터가 자동 추정보다 우수함
- [251016-visual-quality-analysis.md](daily_docs/251016-visual-quality-analysis.md) - 부분 재구성 vs 전체 재구성, View Coverage 중요성 체크

---

## Phase 3: Insta360 X5 360도 카메라 실험 (11/5 ~ 11/18)

- [251105-3dgut_with_Insta360_X5.md](daily_docs/251105-3dgut_with_Insta360_X5.md) - 3DGUT 분석, Insta360 X5 캘리브레이션 파라미터 정리
- [251113-insta360_school_view.md](daily_docs/251113-insta360_school_view.md) - Blender 360 Extractor로 다시점 이미지 추출, 290장 생성
- [251118‑rig_viewer_results.md](daily_docs/251118‑rig_viewer_results.md) - COLMAP rig_configurator 적용, Rig 기반 PSNR 10dB 향상

---

## Phase 4: Rig 최적화 & 파이프라인 구축 (11/18 ~ 12/2)

- [251202-school_rig_adjust.md](daily_docs/251202-school_rig_adjust.md) - 좌표계 변환(OpenGL→COLMAP), 마스킹 기법, 자동화 파이프라인

---

## 핵심 인사이트

| 발견 | 내용 |
|------|------|
| 품질 영향 순서 | 조명 > 해상도 > 카메라 파라미터 |
| View Coverage | Point Cloud 개수보다 중요 |
| Rig 기반 재구성 | 개별 카메라 재구성보다 우수 |
| 360도 카메라 | 수평 Coverage 강점, 수직 한계 |

---

## 리소스

- **이미지/영상**: [video_picture/](video_picture/)
