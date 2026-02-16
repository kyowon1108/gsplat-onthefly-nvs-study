# 260216 - on-the-fly-nvs Rig 제약 대응 검증 보고

## 0. SfM 처리 시간 비교(별도 참고)

이 섹션은 260205 비교 문서 기준의 시간 비교 참고용임.  
운영 판정 계산에는 사용하지 않음.

| 단계 | On-the-fly | COLMAP Rig SfM |
|---|---:|---:|
| Image Reorganization | - | 0.01s |
| Rig Config Creation | - | <0.01s |
| Feature Extraction | - | 4.85s |
| Rig Configurator | - | 0.80s |
| Sequential Matching | - | 1319.93s |
| Mapper | - | 91.15s |
| 총 소요 시간 | 129.34s | 1416.74s |

## 1. 목적

260131 기준 설정이 운영 기준(통과율 `9/12`, fallback 기준 `0.35`)을 만족하는지 확인함.
R1/R2/R3는 rotation-only 가정 이탈 스트레스에서 기준 유지 여부를 확인하는 검증 항목임.

## 2. 확인 질문(R1/R2/R3)

| 항목 | 무엇을 틀어 확인했는지 | 확인 이유 |
|---|---|---|
| R1. 회전 민감도 | `translation perturbation`(0.0/0.5/1.0/2.0%) 주입 | rotation-only 가정 이탈 시 `fallback_triggered_rate`가 기준 `0.35`를 초과하는지 확인하기 위함임 |
| R2. 보조 포즈 경로 안정성 | 경로 A/B(`detach=true/false`) 변경 | 경로 변경 시 `nan_detected` 발생 또는 학습 중단 여부를 확인하기 위함임 |
| R3. 보조 시점 화질 유지 | 기준설정 단계에서 산출한 하한을 기준적용 단계에 고정 적용 | 기준적용 단계에서도 통과율 기준(`>=75%`)을 유지하는지 확인하기 위함임 |

### 2.1 260131 프로세스 매핑

| 검증 항목 | 260131 프로세스 구간 | 실제 진행 방식 | 확인 지표 |
|---|---|---|---|
| R1. 회전 민감도 | `2.1 변경된 Incremental 흐름`의 Step1(Tracking) + Step3(Aux Gaussian Spawn safety check) | Tracking pose에 `translation perturbation`을 주입하고, Step3 fallback 분기(`pairs>=500`, `a>0`, `nonpos<0.3`) 위반으로 인한 `fallback_triggered_rate`를 집계함 | 통과율, `fallback_triggered_rate` |
| R2. 보조 포즈 경로 안정성 | `2.1 변경된 Incremental 흐름`의 Step4(Optimization) | Step4에서 aux pose gradient 경로를 A/B(`detach=true/false`)로 바꿔 동일 데이터·시드·설정으로 재실행함 | `nan_detected`, winner(A/B) |
| R3. 보조 시점 화질 유지 | Step4 이후 `aux_eval_summary.csv` 산출 결과 | 기준설정 단계에서 산출한 aux 화질 하한(mean/min_cam/gap)을 기준적용 단계에 고정 적용해 통과율을 확인함 | aux 화질 통과율 |

### 2.2 검증 위치 다이어그램

```mermaid
flowchart LR
    S1["Step1 Tracking"] --> S2["Step2 Ref Gaussian Spawn"] --> S3["Step3 Aux Spawn + Safety Check"] --> S4["Step4 Optimization"] --> S5["Step5 Aux-view Evaluation"]
    R1["R1: perturbation 주입"] -.-> S1
    R1b["R1: fallback 조건 확인"] -.-> S3
    R2["R2: detach true/false 비교"] -.-> S4
    R3["R3: mean/min_cam/gap 하한 적용"] -.-> S5
```

- R1은 Step1에서 pose perturbation을 주입하고 Step3에서 fallback 조건 위반(`pairs>=500`, `a>0`, `nonpos<0.3`) 발생을 집계하는 검증임.
- R2는 Step4 최적화 구간에서 detach 설정 A/B를 바꿔 `nan_detected`와 winner 변화를 확인하는 검증임.
- R3는 Step5 평가 구간에서 기준설정 단계 하한(mean/min_cam/gap)을 기준적용 단계에 고정 적용해 통과율을 확인하는 검증임.

## 3. 진행

### 3.1 실행 순서

1. 먼저 기준설정 단계를 실행해 R3 하한(mean/min_cam/gap)과 기준설정 단계 판정 결과를 산출함.
2. 다음으로 기준적용 단계에서 위 하한을 고정한 상태로 동일 데이터·시드·설정으로 재실행함.
3. 마지막으로 판정을 재계산해 기준적용 단계 결과와 일치하는지 대조함.

### 3.2 대상/조건

- 260131 기준 5개 virtual pinhole 시점(High_Cam06/07/08, Low_Cam07/08, ref=High_Cam07) 사용함.
- 동일 EQR 프레임에서 추출한 시점이라 camera center는 동일하고 회전만 다른 조건임.
- R1의 perturbation은 실제 운영 입력 재현이 아니라 가정 이탈 스트레스 확인 목적임.

## 4. 평가 결과

### 4.1 정량 평가

| 항목 | 기준 | 관측 결과 | 상태 |
|---|---|---|---|
| R1. 회전 민감도 | 통과율 `9/12`, fallback 기준 `0.35` | 통과율 `6/12`, 실패 run fallback `0.3628~0.4804` | 미충족 |
| R2. 보조 포즈 경로 안정성 | `nan_detected=False` 종료 | 기준설정/기준적용 모두 `nan_detected=False` 종료, winner `A->B` 변경 | 충족 |
| R3. 보조 시점 화질 유지 | 통과율 `>=75%`, `mean>=11.0714`, `min_cam>=10.0714`, `gap<=3.6314` | 기준설정 `15/15`, 기준적용 `13/15` (실패 2건: `min_cam=9.1529`, `min_cam=9.4249`) | 충족 |

최종 판정은 Hold임.

### 4.2 정성 평가

| 관측 원천 | 관측 내용 | 의미 |
|---|---|---|
| 운영 로그 | 실패 6 run 로그에서 `FALLBACK (skip): only ... pairs < 500`가 관측됨 | 대응쌍 부족이 fallback 발생 조건으로 기록됨 |
| 진단 CSV(`b3_2_fit_log.csv`) | 실패 6 run 합산에서 fallback row `261`, `a<=0` row `261`, `nonpos_ratio>=0.3` row `261`, `pairs<500` row `175` 관측됨 | fallback이 `pairs<500` 단독 원인이 아니라 `a<=0/nonpos_ratio` 조건과 함께 발생했음을 보여줌 |
| 기준설정 vs 기준적용 판정 | R2 winner가 `A->B`로 변경됨 | 기준설정 winner=A, 기준적용 winner=B로 단계 간 일관성 미충족임 |

카메라별 fitting/skip 통계(260131):

<img src="../video_picture/260131/per_camera_fitting_stats.png" width="1000">

## 5. 결론

| 의도한 부분 | 나온 결과 | 해석 |
|---|---|---|
| R1: 가정 이탈 상황에서도 fallback 급증 없이 유지되는지 확인함 | 통과율 `6/12`로 기준 `9/12` 미달, 실패 run fallback `0.3628~0.4804`로 기준 `0.35` 초과함 | R1 스트레스 조건에서 운영 기준 미충족임 |
| R2: 보조 포즈 경로가 발산 없이 유지되는지 확인함 | 기준설정/기준적용 모두 `nan_detected=False` 종료, winner `A->B` 변경됨 | 무발산은 충족했지만 winner 단계 일관성은 미충족임 |
| R3: 보조 시점 화질 하한이 운영 단계에서도 유지되는지 확인함 | 기준설정 `15/15`, 기준적용 `13/15`; 하한은 `mean>=11.0714`, `min_cam>=10.0714`, `gap<=3.6314`로 적용됨 | 운영 단계에서도 R3 기준 충족함(2건 실패는 `min_cam` 하한 미달) |
| 최종 운영 가능 여부를 판정함 | 최종 판정 Hold임 | Hold의 직접 원인은 R1 미충족이며, 다음 실험 3개로 R1 기준(`9/12`, `0.35`) 재검증이 필요함 |
