# 260518 - 최신 Timestamp Packet 기준 OTF Rig 품질 차이 원인 재측정
## 1. 질문 -> 답 요약

| 질문                                                                             | 현재 3-seed 기준 답                                                                                                                                      |
| ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gaussian 생성 수 부족이 online streaming과 offline batch 3DGS 사이의 품질 차이 원인인가?         | **아님.** 생성 강도를 높일수록 holdout PSNR이 19.680 -> 19.400 -> 19.107로 단조 하락함.                                                                               |
| 과거 timestamp window sampling이 품질 차이를 유의미하게 줄이는가?                               | **아님.** pose freeze 대비 +0.10~0.14 dB 정도만 회복하고 timestamp packet streaming 기준선에는 복귀하지 못함.                                                             |
| pose와 초기 3D point 중 어느 쪽 영향이 큰가?                                               | **pose 영향이 더 큼.** offline batch 3DGS에서 pose-only 손실은 -0.250 dB, init-only 손실은 -0.043 dB임.                                                           |
| online OTF pose와 Gaussian center 초기점이 offline SfM 기준과 비교해 batch 학습 초기값으로 충분한가? | **그렇다.** OTF pose와 OTF Gaussian center 초기점을 offline batch 3DGS에 넣으면 COLMAP 기준 대비 -0.04~-0.29 dB 수준으로 수렴함. 추정 pose / point 자체가 약 6 dB 품질 차이의 주 병목은 아님. |
| Gaussian confidence 후보 신호로 무엇이 유효한가?                                           | gradient EMA가 final opacity와 가장 높은 순위 상관을 보임. Visibility count와 cross-view visibility는 서로 상관이 높아, 둘을 동시에 쓰면 정보가 중복될 가능성이 큼.                         |

핵심은 online streaming과 offline batch 3DGS 사이의 품질 차이가 **추정 pose / 초기 3D point의 정확도 문제라기보다, online 최적화 체제와 pose refinement 방식, Gaussian 생성/유지/제거 정책 문제**에 더 가깝다는 점임.

---

## 2. 실험 조건 정의

| 조건명                                                      | 의미                                                                                                    | 검증 질문                                             |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 최신 timestamp packet streaming 기준선                    | 최신 timestamp를 학습할 때 마지막으로 append된 view 1장만 과대표집하지 않고, 해당 timestamp packet의 train view 중 하나를 sampling함 | rig 구조에 맞춘 새 streaming 기준선                        |
| Gaussian 생성 강도 증가                                        | Gaussian 생성 확률 강도를 높여 최종 Gaussian 수를 늘림                                                               | 생성 수 부족이 원인인가?                                    |
| pose freeze                                              | streaming 중 rig pose update를 완전히 막음                                                                   | 현재 pose update가 품질에 기여하는가?                        |
| pose freeze + 과거 timestamp window sampling               | pose를 고정한 상태에서 latest timestamp를 뽑지 않는 일반 sampling step 중 일부를 과거 5개 또는 10개 timestamp window에서 무작위로 뽑음 | past-keyframe sliding-window sampling이 품질을 회복하는가? |
| 작은 pose learning rate + 과거 timestamp window 무작위 sampling | pose를 완전히 고정하지 않고 매우 작은 learning rate로만 움직이게 둔 보조 조건                                                  | 완전 freeze와 작은 pose update의 차이는 무엇인가?              |

- timestamp packet : 같은 timestamp에서 생성된 rig view 묶음을 의미함. 본 데이터에서는 holdout view를 제외하면 보통 8개 train view가 하나의 packet을 이룸.

---

## 3. 품질 차이 원인 분해 결과

- seed 0, 1, 2 실행 결과의 평균 ± 표준편차

| 조건                                                                |   holdout PSNR |  post-hoc PSNR |  SSIM | LPIPS | 최종 Gaussian 수 |
| ----------------------------------------------------------------- | -------------: | -------------: | ----: | ----: | ------------: |
| timestamp packet streaming 기준선                                    | 19.680 ± 0.128 | 21.270 ± 0.070 | 0.653 | 0.373 |         0.99M |
| Gaussian 생성 강도 증가, scaler 4                                       | 19.400 ± 0.142 | 21.043 ± 0.150 | 0.641 | 0.381 |         1.34M |
| Gaussian 생성 강도 증가, scaler 8                                       | 19.107 ± 0.192 | 20.803 ± 0.189 | 0.624 | 0.395 |         1.73M |
| pose freeze                                                       | 19.180 ± 0.128 | 20.900 ± 0.022 | 0.629 | 0.391 |         1.01M |
| pose freeze + 과거 5 timestamp window 무작위 sampling           | 19.283 ± 0.041 | 20.900 ± 0.033 | 0.627 | 0.390 |         1.02M |
| pose freeze + 과거 10 timestamp window 무작위 sampling          | 19.323 ± 0.158 | 20.900 ± 0.071 | 0.629 | 0.389 |         1.01M |
| 작은 pose learning rate + 과거 5 timestamp window 무작위 sampling | 19.560 ± 0.078 | 21.157 ± 0.048 | 0.644 | 0.376 |         1.01M |

**해석**
- Gaussian 생성 강도를 높이면 최종 Gaussian 수는 크게 늘지만 PSNR, SSIM, LPIPS가 모두 악화됨.
- 따라서 현재 timestamp packet 기준에서도 생성 수 부족이 주원인이라는 가설은 지지되지 않음.
- pose freeze는 streaming 기준선 대비 약 -0.50 dB 손실을 만듦.
- 과거 5\~10 timestamp window 무작위 sampling은 pose freeze 위에서만 +0.10\~0.14 dB 정도의 작은 회복을 보임.
- 작은 pose learning rate를 둔 보조 조건은 완전 freeze보다 뚜렷하게 좋아지고 streaming 기준선에 가까워짐.

---

## 4. Pose 정확도 교차검증

| 조건                                                         |        ATE RMSE | RPE translation | RPE rotation | Sim(3) scale |
| ---------------------------------------------------------- | --------------: | --------------: | -----------: | -----------: |
| 최신 timestamp packet streaming 기준선                          | 0.0113 ± 0.0016 |          0.0070 |       0.045° |         9.86 |
| Gaussian 생성 강도 증가, scaler 4                                | 0.0175 ± 0.0033 |          0.0097 |       0.050° |         9.91 |
| Gaussian 생성 강도 증가, scaler 8                                | 0.0242 ± 0.0079 |          0.0124 |       0.050° |         9.95 |
| pose freeze                                                | 0.0233 ± 0.0019 |          0.0132 |       0.073° |         9.87 |
| pose freeze + 과거 5 timestamp window 무작위 sampling           | 0.0266 ± 0.0010 |          0.0133 |       0.069° |         9.86 |
| pose freeze + 과거 10 timestamp window 무작위 sampling          | 0.0242 ± 0.0058 |          0.0138 |       0.073° |         9.89 |
| 작은 pose learning rate + 과거 5 timestamp window 무작위 sampling | 0.0174 ± 0.0035 |          0.0096 |       0.054° |         9.86 |

**해석**
- Sim(3) scale이 모든 조건에서 9.86~9.95 범위로 일관되어 정렬 자체는 정상으로 보임.
- timestamp packet streaming 기준선은 rendering 품질뿐 아니라 COLMAP 기준 pose error도 가장 낮음.
- Gaussian 생성 강도 증가는 rendering 품질과 pose metric을 동시에 악화시킴.
- 이번 결과에서는 pose freeze가 drift 방지 효과라기보다, streaming 중 photometric pose refinement가 주던 이득을 제거한 조건처럼 관찰됨.
- 과거 timestamp window 무작위 sampling은 pose error를 개선하지 못함.
- 작은 pose learning rate는 freeze 대비 pose metric과 rendering 품질을 함께 회복함.

---

## 5. Pose와 초기 3D Point 영향 분리

timestamp packet streaming 결과를 OTF source로 사용해, online OTF가 추정한 pose와 Gaussian center가 offline batch 3DGS에서 어느 정도 쓸 수 있는지를 분리해 본 결과

- OTF pose: latest streaming baseline seed 0, 1, 2에서 export된 pose.
- OTF init: latest streaming baseline에서 spawn된 Gaussian center.
- 비교 기준: COLMAP rig-constrained SfM.
- 정렬: COLMAP 기준으로 Sim(3)-Umeyama 정렬.
- 초기점 개수: COLMAP point 수에 맞춰 deterministic count-matched sampling으로 맞춤.
- 학습: 3DGS 30,000 iteration.

| 비교 조건                                  | pose   | 초기 3D point |       30k PSNR |
| -------------------------------------- | ------ | ----------- | -------------: |
| COLMAP pose + COLMAP points            | COLMAP | COLMAP      | 26.453 ± 0.021 |
| OTF pose + COLMAP points               | OTF    | COLMAP      | 26.203 ± 0.027 |
| COLMAP pose + OTF Gaussian center init | COLMAP | OTF         | 26.410 ± 0.017 |
| OTF pose + OTF Gaussian center init    | OTF    | OTF         | 26.167 ± 0.031 |

Per-seed paired delta는 COLMAP pose + COLMAP points 조건을 기준으로 계산함.

| 효과                                              |       30k PSNR 차이 |
| ----------------------------------------------- | ----------------: |
| pose-only: pose만 OTF로 교체                        | -0.250 ± 0.018 dB |
| init-only: 초기 3D point만 OTF Gaussian center로 교체 | -0.043 ± 0.025 dB |
| combined: pose와 초기 3D point를 모두 OTF로 교체         | -0.286 ± 0.044 dB |

**해석**
- OTF Gaussian center는 offline batch 3DGS의 count-matched 초기점으로 사용했을 때 COLMAP sparse point 대비 -0.043 ± 0.025 dB로, 30k PSNR 기준 seed noise 수준의 차이만 보임.
- OTF pose는 초기점보다 더 큰 손실을 만들지만, 그 크기는 약 -0.25 dB로 online streaming과 offline batch 3DGS 사이의 약 6 dB 품질 차이 전체를 설명하기에는 작음.
- pose와 초기점을 모두 OTF로 사용해도 offline batch 3DGS에서는 26.167 dB까지 수렴함.
- 따라서 online OTF의 추정 pose / 초기 3D point 자체가 online streaming과 offline batch 3DGS 사이의 품질 차이의 주 병목이라고 보기는 어려움.
- 남는 차이는 같은 pose / point가 offline에서는 잘 수렴하지만 streaming에서는 낮은 품질에 머무르는 이유, 즉 online 최적화 예산, pose refinement 방식, Gaussian 생성/유지/제거 정책 쪽에서 찾아야 함.

---

## 6. Gaussian Confidence 후보 신호 결과

| 신호                    | 의미                                                        | 해석 목적                                                 |
| --------------------- | --------------------------------------------------------- | ----------------------------------------------------- |
| Gradient EMA          | 각 Gaussian의 gradient magnitude exponential moving average | 학습 중 의미 있게 조정되는 Gaussian을 찾기 위한 parameter-side 신호     |
| Visibility count      | 각 Gaussian이 rendering 과정에서 visible로 잡힌 횟수                 | 실제 output에 자주 관여하는 Gaussian을 찾기 위한 visibility-side 신호 |
| Cross-view visibility | 같은 timestamp의 다른 rig view에서 이미 보이는 정도                     | rig multi-view coverage를 반영하기 위한 geometry-side 신호     |

###  6.1 신호 간 Spearman Correlation

|                       | Gradient EMA | Visibility count | Cross-view visibility |
| --------------------- | -----------: | ---------------: | --------------------: |
| Gradient EMA          |        1.000 |            0.338 |                 0.156 |
| Visibility count      |        0.338 |            1.000 |                 0.670 |
| Cross-view visibility |        0.156 |            0.670 |                 1.000 |

괄호 없는 값은 seed 0, 1, 2 평균임. Seed별 범위는 다음과 같음.

| 비교                                        |    seed별 범위 |
| ----------------------------------------- | ----------: |
| Gradient EMA vs Visibility count          | 0.327-0.349 |
| Gradient EMA vs Cross-view visibility     | 0.137-0.168 |
| Visibility count vs Cross-view visibility | 0.657-0.686 |

### 6.2 Final Opacity와의 Spearman Correlation

Final opacity는 Gaussian이 최종적으로 살아남아 rendering에 기여한 정도를 보는 간접 지표임. 품질의 직접 측정은 아니지만 confidence 후보 신호의 1차 검증 기준으로 사용함.

| 신호                    | final opacity와의 Spearman correlation |    seed별 범위 |
| --------------------- | -----------------------------------: | ----------: |
| Gradient EMA          |                               +0.545 | 0.535-0.551 |
| Visibility count      |                               +0.517 | 0.499-0.536 |
| Cross-view visibility |                               +0.399 | 0.387-0.411 |

**해석**
- 세 신호 모두 final opacity와 양의 상관을 보임.
- 단일 신호로는 Gradient EMA가 final opacity와 가장 높은 순위 상관을 보임.
- Visibility count와 cross-view visibility는 서로 상관이 높아 둘 다 넣으면 정보가 중복될 가능성이 큼.
- 다음 Gaussian confidence 점수는 세 신호를 모두 같은 비중으로 넣기보다, **Gradient EMA + visibility 계열 신호 하나**를 정규화해 결합하는 방향이 더 합리적임.

---

## 7. Quality vs Latency Trade-off Plot

**확인하려는 질문:** Gaussian을 더 많이 만들면 품질 차이를 줄일 수 있는가, 아니면 시간만 늘고 품질은 떨어지는가?

![Quality vs latency trade-off](video_pire/260518/fig1_quality_vs_latency_v2.png)

| 표시   | 의미                                                                  | 해석                       |
| ---- | ------------------------------------------------------------------- | ------------------------ |
| x축   | timestamp packet 하나를 처리하는 평균 online wall-clock 시간. bootstrap 구간은 제외 | 오른쪽일수록 online 처리 비용이 큼   |
| y축   | holdout view의 PSNR                                                  | 위쪽일수록 unseen view 품질이 좋음 |
| 점 하나 | 하나의 실험 조건에 대한 seed 0, 1, 2 평균                                       | 조건별 품질-시간 trade-off 비교   |
| 오차막대 | seed 0, 1, 2 사이의 표준편차                                               | 길수록 seed에 따른 변동이 큼       |

- Gaussian 생성 강도를 높이면 Gaussian 수와 latency는 증가하지만 holdout PSNR은 떨어짐.
- 반대로 timestamp packet 기준 streaming baseline은 가장 높은 품질과 낮은 latency를 동시에 보임.
- 따라서 현재 gap의 원인을 "생성 수 부족"으로 보기 어렵고, 단순히 더 많이 spawn하는 방향은 trade-off도 나쁨.

## 8. Gradient EMA Histogram 및 Top/Bottom Gaussian 시각화

**확인하려는 질문:** 어떤 Gaussian이 아직 optimization signal을 받고 있으며, gradient 기반 신호만으로 pruning 여부를 판단해도 되는가?

![Gradient EMA histogram and spatial map](video_picture/260518/fig2_gradient_ema_hist_topbottom_v2.png)

- Gradient EMA : Gaussian center에 들어온 gradient의 moving average. 값이 큰 Gaussian은 아직 refinement signal을 강하게 받고 있는 점이고, 값이 작은 Gaussian은 이미 수렴했거나 자주 보이지 않는 점이 섞여 있음.

| 표시              | 의미                                | 해석                                                     |
| --------------- | --------------------------------- | ------------------------------------------------------ |
| 왼쪽 histogram    | Gaussian별 gradient EMA 분포         | 대부분의 Gaussian은 gradient signal이 매우 작고, 소수만 긴 tail을 형성함 |
| 분위수 선           | gradient EMA의 median / 상위 분위 기준   | 큰 gradient를 받는 Gaussian이 전체 중 극히 일부임을 확인               |
| 가운데 spatial map | gradient EMA 상위 0.5% Gaussian의 위치 | 아직 조정이 필요한 Gaussian이 공간적으로 어디에 몰리는지 확인                 |
| 오른쪽 spatial map | gradient EMA 하위 0.5% Gaussian의 위치 | low-gradient Gaussian이 바로 제거 대상인지 판단하기 어려움을 확인         |
| 점 색상            | visibility count 간접 지표            | gradient signal과 visibility 정보를 함께 해석하기 위한 보조 표기       |

- 그림에서 gradient EMA 분포는 매우 sparse한 long-tail 형태임.
- 상위 0.5% Gaussian은 특정 영역에 집중되어 있어 "아직 조정이 필요한 Gaussian"을 찾는 신호로 쓸 수 있음.
- 하위 0.5%는 "나쁜 Gaussian"을 뜻하지 않음. 이미 수렴한 Gaussian과 거의 보이지 않는 Gaussian이 같이 들어가므로, pruning 기준으로 쓰려면 visibility 계열 신호와 함께 봐야 함.

## 9. Visibility Count Distribution 및 Spatial Map

**확인하려는 질문:** 어떤 Gaussian이 실제 rendering 과정에서 자주 관측되는가, 그리고 이 신호가 gradient 기반 신호와 다른 정보를 주는가?

![Visibility count distribution and spatial map](video_picture/260518/fig3_visibility_count_dist_spatial_v2.png)

- Visibility count는 alpha contribution의 직접 누적값이 아니라, rendering 과정에서 visible로 잡힌 step count를 세는 간접 지표임.
- 값이 높으면 여러 step에서 자주 render-visible이었다는 뜻이고, 값이 낮다는 것만으로 곧바로 제거 대상이라고 볼 수는 없음.

| 표시              | 의미                                             | 해석                                             |
| --------------- | ---------------------------------------------- | ---------------------------------------------- |
| 왼쪽 histogram    | visibility count 분포를 linear scale로 표시          | 자주 보이는 Gaussian과 드물게 보이는 Gaussian의 전체 양감을 확인   |
| 가운데 histogram   | 같은 분포를 log scale로 표시                           | 적은 수의 tail과 rare case까지 확인                     |
| 오른쪽 spatial map | Gaussian 위치를 x-z 평면에 투영하고 visibility count로 색칠 | 자주 보이는 Gaussian이 공간적으로 어디에 분포하는지 확인            |
| colorbar        | visibility count 값                             | 노란색에 가까울수록 rendering 중 자주 visible로 잡힌 Gaussian |

- 분포는 넓게 퍼져 있고 공간적으로도 특정 영역에 높고 낮은 visibility가 나뉨.
- 앞의 Spearman 결과에서 visibility count는 final opacity와 양의 상관을 보였지만, cross-view visibility와 상관이 높아 둘 다 같은 역할로 넣으면 중복될 가능성이 큼.
- 따라서 Gaussian confidence 점수에는 gradient EMA와 visibility 계열 신호 하나를 조합하는 것이 더 타당함.

## 10. Cross-view Warped Coverage Residual 및 `P_s` vs `P_L` 비교

**확인하려는 질문:** ref view에서 새 Gaussian 생성 후보로 잡히는 영역이, 같은 timestamp의 다른 rig view alpha coverage로 이미 덮여 있는가?

| 표기                 | 의미                                                                        | 해석                                                                 |
| ------------------ | ------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `P_L`              | High_Cam07 (ref view)의 LoG 기반 기존 생성 점수 map                                | 기존 방식이 "새 Gaussian을 만들고 싶다"고 보는 후보 영역                              |
| `P_tilde_combined` | sibling view들의 rendered alpha coverage를 기준 view로 warp한 뒤 max-combine한 map | 같은 timestamp의 다른 rig view alpha coverage로 이미 덮인 영역                 |
| `P_s`              | `relu(P_L - P_tilde_combined)`                                            | 기존 LoG 기반 생성 후보 중 sibling view의 alpha coverage로 덮이지 않고 남은 잔여 생성 점수 |


![Cross-view warp visualization example](video_picture/260518/fig4_pspl_ts11.png)

| 표시                        | 의미                                                      | 해석                                                |
| ------------------------- | ------------------------------------------------------- | ------------------------------------------------- |
| `ref GT` / `ref rendered` | 기준 view의 실제 이미지와 현재 rendering                           | spawn score가 어떤 rendering 실패와 연결되는지 확인            |
| `P_L`                    | 기존 LoG 기반 spawn score map                              | 기준 view만 봤을 때 새 Gaussian 후보로 잡히는 영역               |
| `P_tilde_combined`        | sibling view alpha coverage를 기준 view로 warp한 map         | 같은 timestamp의 다른 rig view alpha coverage로 이미 덮인 영역              |
| `P_s`                    | `P_L`에서 `P_tilde_combined`를 뺀 잔여 map               | sibling view의 alpha coverage로도 덮이지 않아 남는 생성 후보                 |
| overlay                   | 실제 이미지 위에 score map을 겹친 결과                              | score가 실제 image structure 어디에 걸리는지 확인             |

- 23 timestamp 기준으로 보면, sibling view의 warped alpha coverage를 반영한 뒤 잔여 생성 점수(`P_s`)가 기존 LoG 기반 score(`P_L`) 대비 평균 0.9296 ± 0.1138만큼 줄어듦.
- 이는 기존 LoG 기반 spawn score 중 상당 부분이 sibling view의 warped alpha coverage와 겹친다는 뜻임.
- 따라서 cross-view warped coverage residual은 "기준 view에서 새 Gaussian 생성 후보"를 줄이는 coverage prior로 볼 수 있음.

- 다만 warped alpha coverage는 photometric detail이 충분히 복원되었는지를 직접 보장하지 않음.
- 예시 이미지처럼 rendered view가 blurry해도 alpha coverage는 넓게 잡힐 수 있어, `P_s`만 단독으로 쓰면 실제로 필요한 Gaussian 생성까지 억제할 위험이 있음.
- 따라서 이 신호는 단독 생성 판단 기준이 아니라, image residual / detail 신호와 gradient EMA / visibility count 같은 Gaussian 단위 confidence 후보 신호와 결합해 검증해야 함.

---

## 11. 현재까지의 결론과 후속 보강 항목

| 항목                                         | 현재 판정                                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------------------- |
| Gaussian 생성 수 부족                           | 주 원인으로 보기 어려움. 생성 수를 늘릴수록 품질과 pose metric이 모두 악화됨.                                    |
| 과거 timestamp window 무작위 sampling 부족 | 주 원인으로 보기 어려움. pose freeze 조건에서 작은 회복만 보임.                                            |
| pose 처리 방식                                 | 현재까지 가장 민감한 streaming 축. 완전 freeze는 손실이 있고, 작은 pose learning rate는 손실 대부분을 회복함.       |
| OTF pose / 초기 3D point 정확도                 | offline batch 3DGS에서는 COLMAP 기준 대비 작은 손실만 보임. 추정 pose / point 자체가 online streaming과 offline batch 3DGS 사이의 품질 차이의 주 병목은 아님. |
| Gaussian confidence 후보 신호                  | Gradient EMA가 가장 강한 단일 신호이며, visibility 계열 신호 하나와 결합할 근거가 있음.                         |

현재까지의 결과만 보면, 품질 차이의 핵심은 단순 Gaussian 생성 수, 과거 window sampling 부족, 또는 online OTF의 pose / 초기 3D point 추정 실패가 아님.
같은 OTF pose / Gaussian center도 offline batch 3DGS에서는 높은 PSNR로 수렴하므로, 남은 차이는 **online 최적화 체제, pose refinement 방식, confidence 기반 Gaussian 생성/유지/제거 설계** 쪽에 더 가까워 보임.
