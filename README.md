# 3D Gaussian Splatting On-the-Fly NVS Study

3D Gaussian Splatting 기반 실시간 Novel View Synthesis 연구 기록

---

## 개요

**목표**: 360도 카메라(Insta360 X5), COLMAP Rig SfM, on-the-fly NVS를 결합한 다중 카메라 NVS 파이프라인 구축

**현재 진행 상황 (2026-03-02 기준)**: Phase 4 - Saebit 9-view Rig 파이프라인 통합 및 Render-vs-GT 평가 완료

---

## 이력

전체 기록은 [researchhistory.md](researchhistory.md) 참조

| Phase | 기간 | 내용 |
|-------|------|------|
| 1 | 2025-09-11 ~ 2025-10-16 | 환경 구축, 평가 메트릭 학습, RealSense D435 베이스라인 실험 |
| 2 | 2025-11-05 ~ 2025-12-02 | Insta360 X5 360도 촬영, Rig 좌표계 정렬 및 자동화 파이프라인 구축 |
| 3 | 2025-12-23 ~ 2026-01-13 | Rig SfM 비교 실험, 3DGS 품질 향상 검증 |
| 4 | 2026-01-19 ~ 2026-03-02 | on-the-fly NVS 멀티카메라 Rig 지원, 운영 검증, Saebit 통합 |

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

---

## 폴더 구조

```
├── daily_docs/      # 일별 연구 기록
├── terms_docs/      # 기술 용어 정리
├── final_docs/      # 최종 결과물
├── code_docs/       # 실험 코드
└── video_picture/   # 이미지/영상 자료
```

---

## 문서 규칙

- 파일명: `YYMMDD-description.md`
- 카테고리별 폴더 분류
- 시간순 정렬
