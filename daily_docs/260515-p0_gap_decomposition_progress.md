# 260515 - OTF Rig 품질 차이 원인 분해 및 다음 실험 방향

- 데이터셋: Insta360 X5 EQR -> 9 virtual pinhole view x 23 timestamp = 207 frame.
- 기준 평가: 지침서 기준에 맞춰 207 frame 전체를 render 한 reconstruction metric 을 주 기준으로 사용함.

 **품질 차이 원인 분해**, **pose / 초기 3D point 영향 분리**, **confidence signal prototype**을 현재 결과 기준으로 정리함.

---

## 1. 한눈에 보는 답변

| 질문                                                     | 현재 답                                                                             |
| ------------------------------------------------------ | -------------------------------------------------------------------------------- |
| Gaussian을 더 많이 만들면 품질 차이가 줄어드는가?                       | 아니오. accepted Gaussian 수는 약 2.7배 늘었지만 reconstruction PSNR은 오르지 않았음.              |
| 지침서의 past-keyframe sliding-window refinement는 바로 가능한가? | 현재 optimizer에서는 불안정함. rig timestamp packet 단위로 구현하면 scaling explosion으로 완주하지 못함. |
| pose가 주된 원인인가?                                         | 일부 영향은 있음. OTF pose 사용 시 약 -0.39 dB 손실이 있으나 전체 품질 차이를 설명하지는 못함.                  |
| 초기 3D point / Gaussian center가 주된 원인인가?                | 거의 아님. OTF Gaussian center도 offline 3DGS 초기점으로 잘 수렴함.                            |
| confidence signal은 쓸 만한가?                              | 그렇다. Gradient EMA가 가장 강한 단일 신호이고, visibility 계열 신호와 일부 독립적임.                     |
| 다음 실험 방향은?                                             | 단순 생성량 증가보다 gradient 기반 refinement 신호와 visibility 신호를 결합한 선택 정책이 더 타당함.          |

---

## 2. 지침서 요청과 본 문서의 대응

| 지침서 요청                      | 본 문서 처리                                                                     |
| --------------------------- | --------------------------------------------------------------------------- |
| 6 dB 품질 차이 분해               | Gaussian 생성 강도 증가와 rig timestamp packet 단위 sliding-window refinement 결과로 정리 |
| 5-way 3-seed 평균과 표준편차       | pose / 초기 3D point 영향 분리 표로 정리                                              |
| confidence signal prototype | gradient EMA, rendering visibility count, cross-view visibility 결과로 정리      |


---

## 3. 실험 조건 정의

| 조건                                                | 의미                                                                                             | 검증 질문                              |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------- |
| 기본 streaming 결과                                   | 현재 OTF rig 기본 설정. 원본 OTF식 LoG 기반 Bernoulli Gaussian 생성 사용                                      | 기준선                                |
| Gaussian 생성 강도 증가                                 | Gaussian 생성 확률을 높여 accepted Gaussian 수를 늘림                                                     | 생성 수 부족이 원인인가?                     |
| rig timestamp packet 단위 sliding-window refinement | 현재 timestamp의 train view 전체와 과거 5~10개 timestamp packet 일부 train view를 같은 optimization step에 반영 | past-keyframe refinement 부재가 원인인가? |

여기서 **timestamp packet**은 같은 timestamp에서 생성된 rig의 train view 묶음을 의미함. 본 데이터에서는 holdout view를 제외하면 보통 8개 train view가 하나의 packet을 이룸.

---

## 4. 품질 차이 원인 분해 결과

아래 표는 seed 0, 1, 2 실행 결과의 평균 ± 표준편차임.

| 실험 조건 | post-hoc PSNR | holdout PSNR | 평균 accepted Gaussian 생성 수 | 판정 |
|---|---:|---:|---:|---|
| 기본 streaming 결과 | 21.046 ± 0.087 | 19.236 ± 0.115 | 29,825 ± 383 | 기준 |
| Gaussian 생성 강도 2배 증가 | 20.902 ± 0.095 | 19.206 ± 0.077 | 52,121 ± 723 | 생성 수는 증가했지만 품질 개선 없음 |
| Gaussian 생성 강도 4배 증가 | 20.616 ± 0.171 | 18.884 ± 0.230 | 81,974 ± 1,075 | 생성 수는 더 증가했지만 품질은 악화 |

**해석**

- Gaussian 생성 강도를 높이면 accepted Gaussian 수는 크게 늘어남.
- 그러나 reconstruction PSNR은 개선되지 않음.
- 따라서 현재 결과만 보면, 품질 차이의 주된 원인을 단순 Gaussian 생성 수 부족으로 보기는 어려움.

---

## 5. Rig Timestamp Packet 단위 Sliding-Window Refinement

지침서의 "이전 5~10 keyframe"은 rotation-only rig 환경에서는 개별 pinhole image 1장이 아니라, **한 timestamp의 rig packet**으로 보는 것이 더 자연스러움. 따라서 본 실험은 다음 의미로 수행됨.

| 항목 | 구현 의미 |
|---|---|
| 현재 step | 현재 timestamp의 train view 전체를 render 하고, 평균 photometric loss를 계산 |
| 과거 window | 현재 timestamp 이전 5개 또는 10개 timestamp packet |
| 과거 packet 사용 | 각 과거 timestamp packet에서 train view 2개 또는 4개를 선택 |
| pose 처리 | 과거 replay loss는 pose gradient에 반영하지 않음 |
| update 대상 | 현재 packet과 과거 packet에서 보이는 Gaussian을 함께 update 대상으로 사용 |
| 성격 | 전체 sequence를 다시 푸는 global bundle adjustment가 아니라, streaming 제약 안의 local photometric refinement |

안전장치를 끈 상태에서 아래 조건은 모두 iter=270 학습 중 scaling explosion으로 종료됨.

| 조건                                                                    | 결과    |                         붕괴 시점 | scaling.max |
| --------------------------------------------------------------------- | ----- | ----------------------------: | ----------: |
| 현재 timestamp packet 전체만 사용                                            | crash | keyframe 99 / timestamp 11 부근 |         165 |
| 현재 timestamp packet 전체 + 과거 5 timestamp, 각 timestamp 당 train view 2개  | crash | keyframe 99 / timestamp 11 부근 |         232 |
| 현재 timestamp packet 전체 + 과거 5 timestamp, 각 timestamp 당 train view 4개  | crash | keyframe 99 / timestamp 11 부근 |         480 |
| 현재 timestamp packet 전체 + 과거 10 timestamp, 각 timestamp 당 train view 2개 | crash | keyframe 99 / timestamp 11 부근 |         408 |

**해석**

- 과거 packet을 쓰지 않고 현재 timestamp packet 전체만 사용해도 crash가 발생함.
- 따라서 원인은 과거 replay 자체라기보다, 여러 view의 loss와 visibility를 한 step에 묶는 update 구조가 현재 optimizer 설정과 맞지 않는 데 있음.
- 이 결과는 지침서의 sliding-window refinement 방향이 중요하지 않다는 뜻이 아니라, 현재 optimizer로는 packet-level multi-view update를 바로 적용하기 어렵다는 뜻임.

---

## 6. Pose와 초기 3D Point 영향 분리

아래 표는 seed 0, 1, 2 기준 평균 ± 표준편차임. COLMAP pose + COLMAP sparse point는 기준값으로 사용함.

| 비교 조건 | pose | 초기 3D point | 초기점 수 | 30,000 iter PSNR | COLMAP 기준 대비 |
|---|---|---|---:|---:|---:|
| COLMAP pose + COLMAP sparse point | COLMAP rig pose | COLMAP mapper sparse point | 41,678 | 26.488 | - |
| COLMAP pose + OTF Gaussian 중심점 | COLMAP rig pose | OTF Gaussian 중심점 중 41,678개 sampling | 41,678 | 26.389 ± 0.046 | -0.10 ± 0.05 |
| OTF pose + COLMAP sparse point | scale / rotation / translation 정렬된 OTF pose | COLMAP mapper sparse point | 41,678 | 26.099 ± 0.070 | -0.39 ± 0.07 |
| OTF pose + OTF Gaussian 중심점 | scale / rotation / translation 정렬된 OTF pose | OTF Gaussian 중심점 중 41,678개 sampling | 41,678 | 26.114 ± 0.064 | -0.38 ± 0.06 |

OTF Gaussian 중심점 기반 초기화는 OTF Gaussian의 **중심 위치**를 count-matched sparse initialization으로 사용한 것임. Scale / opacity / spherical harmonics를 그대로 재사용한 것은 아님.

| 비교                   |               결과 | 해석                                                             |
| -------------------- | ---------------: | -------------------------------------------------------------- |
| 초기 3D point 영향       |  -0.10 ± 0.05 dB | OTF Gaussian 중심점은 offline 3DGS 초기점으로 거의 손색 없음                  |
| pose 영향              |  -0.39 ± 0.07 dB | OTF pose는 손실을 만들지만, streaming 품질 차이 전체를 설명하지는 못함               |
| OTF pose 조건에서 초기점 교체 | 26.099 vs 26.114 | 같은 OTF pose에서는 COLMAP sparse point와 OTF Gaussian 중심점 차이가 거의 없음 |

**해석**

- OTF Gaussian 중심점 geometry는 큰 실패로 보기 어려움.
- OTF pose는 초기점보다 더 큰 영향을 주지만, offline 3DGS에서 26 dB 이상으로 수렴하므로 전체 품질 차이의 주된 원인으로 보기는 어려움.
- 따라서 남는 핵심 원인은 streaming 중 제한된 최적화, Gaussian lifecycle, selective refinement 정책 쪽임.

---

## 7. Confidence Signal Prototype 결과

지침서에서 요청한 세 confidence signal은 아래 의미로 측정함.

| 신호 | 의미 | 해석 목적 |
|---|---|---|
| Gradient EMA | 각 Gaussian의 position / scaling gradient magnitude의 exponential moving average | 아직 더 학습이 필요한 Gaussian을 찾기 위한 parameter-side 신호 |
| Rendering visibility count | 각 Gaussian이 rendering 과정에서 보인 횟수 | 실제 output에 자주 관여하는 Gaussian을 찾기 위한 visibility-side 신호 |
| Cross-view visibility | 같은 timestamp의 다른 rig view에서 이미 보이는 정도 | rig multi-view coverage를 반영하기 위한 geometry-side 신호 |

신호 로깅을 켠 baseline의 holdout PSNR은 `19.32 ± 0.18`이고, 기본 streaming 결과는 `19.236 ± 0.115`임. 따라서 signal logging 자체가 학습 동작을 크게 바꾸지 않는 것으로 봄.

### 신호 간 독립성

아래 표는 seed 0, 1, 2의 Spearman rank correlation 평균임. 값이 낮을수록 두 신호가 서로 다른 정보를 담는다고 해석할 수 있음.

|  | Gradient EMA | Rendering visibility count | Cross-view visibility |
|---|---:|---:|---:|
| Gradient EMA | 1.000 | 0.372 | 0.151 |
| Rendering visibility count | 0.372 | 1.000 | 0.643 |
| Cross-view visibility | 0.151 | 0.643 | 1.000 |

**해석**

- Gradient EMA와 cross-view visibility는 상관이 낮아 서로 다른 정보를 담음.
- Gradient EMA와 rendering visibility count는 약한 상관으로, 함께 쓸 여지가 있음.
- Rendering visibility count와 cross-view visibility는 상관이 높아 둘 다 넣으면 정보가 중복될 가능성이 큼.

### Final Opacity와의 상관

Final opacity는 Gaussian이 최종적으로 살아남아 rendering에 기여하는 정도를 보는 proxy임. 품질의 직접 측정은 아니지만, confidence signal이 의미 있는 Gaussian을 가리키는지 확인하는 1차 기준으로 사용함.

| 신호 | final opacity와의 Spearman correlation | seed별 범위 |
|---|---:|---:|
| Gradient EMA | +0.564 | 0.558-0.574 |
| Rendering visibility count | +0.498 | 0.492-0.504 |
| Cross-view visibility | +0.383 | 0.376-0.387 |

**해석**

- 세 신호 모두 final opacity와 양의 상관을 보임.
- 단일 신호로는 Gradient EMA가 가장 강함.
- Rendering visibility count와 cross-view visibility는 둘 다 visibility 계열이라 중복성이 큼.
- 따라서 다음 confidence score는 세 신호를 모두 같은 비중으로 넣기보다, **Gradient EMA + visibility 계열 신호 하나**를 결합하는 방향이 더 합리적임.

### 한계

- Gradient EMA의 절대값은 매우 작으므로, score에 직접 넣기 전 정규화가 필요함.
- Final opacity는 품질 proxy일 뿐, holdout PSNR 기여도를 직접 측정한 것은 아님.
- Rendering visibility count는 rendering contribution의 저비용 proxy이므로, alpha contribution까지 직접 누적한 신호와는 구분해야 함.

---

## 8. 현재 결론과 다음 실험 방향

| 원인 후보 | 현재 판정 |
|---|---|
| 단순 Gaussian 생성 수 부족 | 생성 수를 크게 늘려도 품질이 오르지 않아 주 원인으로 보기 어려움 |
| past-keyframe sliding-window refinement 부재 | 지침서 방향으로 구현했지만 현 optimizer에서는 scaling explosion으로 완주하지 못함 |
| OTF pose 오류 | 약 -0.39 dB 손실이 있으나 전체 품질 차이를 설명하지 못함 |
| OTF Gaussian 중심점 geometry 오류 | 약 -0.10 dB 손실로 작음 |
| confidence signal | Gradient EMA가 가장 강한 단일 신호이며, visibility 계열 신호와 결합할 근거가 있음 |
| 남은 주요 후보 | selective revisit, Gaussian lifecycle, confidence 기반 선택 정책, packet-level update 안정화 |

다음 실험 방향은 단순히 Gaussian을 더 많이 만들거나 timestamp packet 전체를 그대로 한 step에 넣는 것이 아니라, **어떤 view / Gaussian을 다시 최적화할지 선택하는 기준**을 만드는 쪽이 더 타당함. 현재 결과 기준으로는 Gradient EMA와 visibility 계열 신호 하나를 결합한 confidence score가 가장 우선 검토할 후보임.

---

## Appendix. 실행 조건 요약

| 본문 조건 | 구현상 의미 |
|---|---|
| 기본 streaming 결과 | 원본 OTF식 Bernoulli Gaussian 생성, 기본 생성 강도 |
| Gaussian 생성 강도 2배 증가 | 기본 대비 Gaussian 생성 확률 강도 증가 |
| Gaussian 생성 강도 4배 증가 | Gaussian 생성 확률 강도를 더 크게 증가 |
| rig timestamp packet 단위 sliding-window refinement | 현재 timestamp packet 전체 view + 과거 5/10 timestamp packet 일부 view를 같은 optimization step에 반영 |
