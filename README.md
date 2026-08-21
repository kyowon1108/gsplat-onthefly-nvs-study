# 3D Gaussian Splatting On-the-Fly NVS Study

3D Gaussian Splatting 기반 실시간 Novel View Synthesis 연구 기록

---

## 개요

**목표**: 360도 카메라(Insta360 X5), COLMAP Rig SfM, on-the-fly NVS를 결합한 다중 카메라 NVS 파이프라인 구축

**현재 진행 상황 (2026-08-19 기준)**: Phase 8 - Blender 4-Camera Fisheye 주차장 환경에서 Offline GS 기준선 확보 및 On-the-fly 1단계 구현 결과 측정 완료

---

## 이력

전체 기록은 [researchhistory.md](researchhistory.md) 참조

| Phase | 기간 | 내용 |
|-------|------|------|
| 1 | 2025-09-11 ~ 2025-10-16 | 환경 구축, 평가 메트릭 학습, RealSense D435 베이스라인 실험 |
| 2 | 2025-11-05 ~ 2025-12-02 | Insta360 X5 360도 촬영, Rig 좌표계 정렬 및 자동화 파이프라인 구축 |
| 3 | 2025-12-23 ~ 2026-01-13 | Rig SfM 비교 실험, 3DGS 품질 향상 검증 |
| 4 | 2026-01-19 ~ 2026-03-02 | on-the-fly NVS 멀티카메라 Rig 지원, 운영 검증, Saebit 통합 |
| 5 | 2026-03-19 ~ 2026-04-27 | Rig-aware 구현, body pose / rigid aux 지원, COLMAP Rig SfM 정량 비교, pose 보정 자유도 ablation |
| 6 | 2026-05-05 ~ 2026-05-18 | Confidence warm-start 설계, drift 분석, rig spherical / stratified 비교, 품질 격차 원인 분해 |
| 7 | 2026-05-28 ~ 2026-07-21 | 공개 dataset 확장(360Roam, OB3D), COLMAP 4.1.0 Panorama SfM 비교, ODGS-SLAM 조사, native EQR vs pinhole 검토 |
| 8 | 2026-08-05 ~ 2026-08-19 | EQR Native OTF 전환, Blender 4-Camera 주차장 환경 구축, Offline GS 기준선, 4-Camera Fisheye OTF 1단계 |

---

## 핵심 발견

| 항목 | 결과 |
|------|------|
| 품질 영향 순서 | 조명 > 해상도 > 카메라 파라미터 |
| Rig SfM 효과 (260111) | 3D 포인트 +35%, Observations +119% |
| Rig → 3DGS (260113) | PSNR +1.24dB, SSIM +0.067, LPIPS -0.072 |
| 360도 카메라 | 수평 Coverage 우수, 수직 Coverage 한계 |
| On-the-fly Rig 운영 검증 (260216) | fallback 민감도, aux pose 경로, aux 품질 게이트 재검증 완료 |
| Saebit 9-view 통합 (260302) | COLMAP bootstrap 등록률 72/72, mean reproj 0.5485px, Render-vs-GT PSNR 16.2319 / SSIM 0.7595 |
| 실행 시간 참고 (260302) | COLMAP bootstrap 32.00s, on-the-fly 60.78s |
| COLMAP 4.1.0 Panorama SfM (260715) | spherical이 perspective_overlapping보다 빠르지만, 특정 scene에서 일부 frame pose가 튐. 일관된 정확도 우위는 확인되지 않음 |
| OB3D baseline (260630) | 일부 dataset은 bootstrap 이후 OOM으로 수행 불가 |
| Offline GS 기준선 (260812) | 5개 Scene held-out 60 view 평가에서 PSNR 28.88~35.62 dB, SSIM 0.8915~0.9687 |
| 4-Camera OTF 1단계 - 속도 (260819) | 전체 loop 33.9분 vs Offline 30k 학습 252.7분 → **7.5배 단축** |
| 4-Camera OTF 1단계 - 품질 (260819) | 카메라 영상 PSNR이 Offline 대비 11.66~16.44 dB 낮음 |
| 4-Camera OTF 1단계 - 실시간성 (260819) | timestamp 처리 p50 3378~3646 ms로 목표 166.7 ms 대비 20~22배 |
| 인접 camera overlap (260819) | 0–2 m 구간 3.78%, 2–15 m 구간 23.41% |

---

## 폴더 구조

```
├── daily_docs/      # 일별 연구 기록 및 미팅 보고
├── terms_docs/      # 기술 용어 정리
├── code_docs/       # 실험 코드 및 config
├── archive/         # 초기 피드백 기록 (2025-09)
└── video_picture/   # 이미지/영상 자료 (YYMMDD 폴더별)
```

---

## 문서 규칙

- **연구 기록**: `daily_docs/YYMMDD-description.md`
- **미팅 보고**: `daily_docs/[DIGLAB][YYMMDD][이름]주제.md`
- **자료**: `video_picture/YYMMDD/` — 문서에서 상대경로 `../video_picture/YYMMDD/파일`로 참조
- 정지 이미지는 WebP, 애니메이션은 GIF 사용
- 카테고리별 폴더 분류, 시간순 정렬
