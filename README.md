# 3D Gaussian Splatting On-the-Fly NVS Study

3D Gaussian Splatting 기반 실시간 Novel View Synthesis 연구 기록

---

## 개요

**목표**: 360도 카메라(Insta360 X5)와 COLMAP Rig 기반 SfM을 활용하여 3D Gaussian Splatting 품질을 향상시키는 파이프라인 구축

**현재 진행 상황**: Phase 5 - Rig SfM 적용 후 3DGS 학습 품질 검증 완료

---

## 이력

전체 기록은 [researchhistory.md](researchhistory.md) 참조

| Phase | 기간 | 내용 |
|-------|------|------|
| 1 | 9/11 ~ 9/13 | 환경 구축, 평가 메트릭 학습 (PSNR, SSIM, LPIPS) |
| 2 | 9/19 ~ 10/16 | Intel RealSense D435 실험, 해상도/조명 영향 분석 |
| 3 | 11/5 ~ 11/18 | Insta360 X5 360도 카메라 실험, Rig 기반 재구성 |
| 4 | 11/18 ~ 12/2 | 좌표계 변환(Blender→COLMAP), 자동화 파이프라인 |
| 5 | 12/23 ~ 1/13 | Rig SfM 비교 실험, 3DGS 품질 검증 |

---

## 핵심 발견

| 항목 | 결과 |
|------|------|
| 품질 영향 순서 | 조명 > 해상도 > 카메라 파라미터 |
| Rig SfM 효과 | 3D 포인트 +35%, Observations +119% |
| Rig → 3DGS | PSNR +1.24dB, SSIM +0.067, LPIPS -0.072 |
| 360도 카메라 | 수평 Coverage 우수, 수직 Coverage 한계 |

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
