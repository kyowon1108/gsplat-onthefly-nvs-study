# 1. Skyfall-GS Process
![](https://i.imgur.com/LHLLNGH.jpeg)
- notebooklm으로 생성한 사진.

## Stage 1. 재구성 (Reconstruction)
### 1-1. 기본 GS 수행
- 위성 이미지 + 위성 SfM으로 얻은 camera pose를 이용해 기본 3DGS 장면을 생성함.

### 1-2. Appearance Modeling (조명/계절이 다른 위성 사진 대응)
**Why?** : 조명/계절 때문에 이미지마다 조금씩 다르게 보이는 문제 발생.
- 이를 해결하기 위해 appearance MLP 쪽으로 분리해서 처리함.

![](https://i.imgur.com/iDlCNyI.png)
- 1. 입력
    - `c` : 기본 SH 색
    - `g` : Gaussian 위치/맥락 임베딩
    - `a` : 이미지 조명·조건 임베딩
2. 이 셋을 작은 MLP에 넣어서
    - `m` : 색에 곱해 줄 스케일 (채도/밝기 조정 느낌)
    - `Δc` : 색에 더해 줄 오프셋 (톤/색감 보정 느낌)
3. 최종 출력 색:
    - `c' = c * m + Δc`

### 1-3. Satellite 환경에서의 floaters 억제 (불투명도(Opacity) 엔트로피 정규화
**Why?** :  실제 표면이 아닌데도 Gaussian이 공중에 뜨는 floaters가 많이 발생함.
- 이때 opacity가 0(완전 투명)이나 1(완전 불투명)으로만 결정되도록 정규화 진행함.
![](https://i.imgur.com/aqnIQnR.png)

### 1-4. Pseudo-camera depth supervision
**Why?** : 지면에서 바라보았을 때 건물 높이나 거리감이 이상해지는 것을 줄이기를 위함.
- 장면 주변에 지상과 가까운 pseudo-cameas를 뿌려 GS로 RGB + depth를 렌더링함.
- 렌더된 RGB를 단안 깊이 모델(MoGe)에 넣어서 좀 더 그럴듯한 깊이 맵을 얻음.
- 이 때 GS depth와 MoGe depth는 절대 스케일이 다르니, 값 자체를 맞추는 대신 두 depth 맵의 패턴이 얼마나 비슷한지(상관)를 보고 loss로 사용.
![](https://i.imgur.com/a9TTVZ7.png)

## Stage 2. 합성 (Synthesis)
### 2-1. Diffusion Refinement
- Stage 1 GS로 렌더한 image에서는 특히 낮은 고도·지면 뷰는 텍스처가 깨지고, floaters가 많음.
- 이를 해결하기 위해 image를 input으로 넣고, model로는 FLowEdit + FLUX.1 조합 사용.
- **FlowEdit** : 완전 noise에서 image를 생성하는 것이 아닌, 기존 렌더링 + prompt 쌍을 받아 "현재 렌더링이 어떤 식으로 망가져 있는지, 어떤 느낌으로 고쳐줬으면 하는지"를 text로 전달해 구조는 가능한 유지한 채 texture/edge/shadow 같은 부분을 개선해 줌.
![](https://i.imgur.com/7Yo0jCt.png)

### 2-2. Multi-sample Diffusion
- Diffusion의 특성 (랜덤성)으로 인해 같은 view라도 생성할 때마다 detail이 조금씩 다른 이미지가 출력됨.
- But, view A와 B에서 본 같은 건물의 모양이 서로 모순되면 심각한 error가 발생함.
- 그래서 한 view당 Diffusion을 여러 번 돌린 결과를 전부 GS 학습에 사용함.

| Process |                                                                                                        |
| ------- | ------------------------------------------------------------------------------------------------------ |
| 1       | **GS 렌더링:** 선택한 카메라 포즈로 GS에서 이미지를 렌더해서 `I_render`를 얻는다.                                                |
| 2       | **Diffusion 샘플 1:** `I_render`를 FlowEdit + FLUX.1에 넣고, seed=1로 돌려 정제 이미지 `I_diff_1`을 얻는다.              |
| 3       | **Diffusion 샘플 2:** 같은 `I_render`를 seed=2로 돌려 `I_diff_2`를 얻는다.                                         |
| 4       | **Diffusion 샘플 N:** 같은 방식으로 seed를 바꿔가며 총 N번 실행해 `I_diff_1, ..., I_diff_N`을 만든다.                        |
| 5       | **Loss 계산:** GS 렌더 `I_render`와 각 정제 이미지 `I_diff_k`(k=1..N) 사이의 차이를 모두 계산하고, 이를 평균 내서 하나의 loss로 만든다.    |
| 6       | **GS 업데이트:** 이 평균 loss에 대해 GS 파라미터를 업데이트한다.                                                            |
| 7       | **반복:** 업데이트된 GS로 다시 1단계(렌더링)부터 반복하면서, 특정 샘플 하나가 아니라 여러 Diffusion 샘플이 공통으로 유지하는 구조 쪽으로 기하가 수렴하도록 유도한다. |

##### 2-3. Curriculum Learning for Camera Angles
- Stage 2의 loop를 모든 각도에 무작위로 적용하면 GS를 수행할 때 구조가 망가질 위험이 큼.
- Skyfall-GS에서는 이를 카메라 각도에 대해 교과정(curriculum)을 걸음.
- 전체를 여러 Episode로 나누고, Episode가 진행될 수록 카메라 고도(elevation)을 점점 낮춤.

| Episode | 고도각 예시 | 느낌                  |
| ------- | ------ | ------------------- |
| 1       | 85°    | 거의 위성 뷰 (거의 직하)     |
| 2       | 65°    | 아직 위에서 보는 느낌이 강함    |
| 3       | 45°    | 건물 옆/정면이 조금씩 보이기 시작 |
| 4       | 25°    | 정면/골목이 꽤 많이 보이는 각도  |
| 5       | 5°     | 거의 지면 시점에 가까운 뷰     |
- Episode 1–2:  
    이미 Stage 1에서 잘 맞추고 있던 “편한 각도”에서 Diffusion supervision을 받으면서  
    기존 구조를 더 정제하는 단계.
- Episode 3–5:  
    점점 어려운 각도(정면/골목/지면)를 추가하면서,  
    새 영역을 조금씩 학습하는 단계.

- 각 에피소드 안에서는
1. 장면 안에 **look-at point**들을 그리드처럼 깔고 (예: 3×3),​
2. 각 포인트 주위를 정해진 고도각으로 도는 orbital camera들을 샘플링해서,
3. 그 카메라들에서 렌더 -> Diffusion -> GS 재학습을 반복함.

---
# 2. GS가 하는 역할

## Stage 1
- 위성 이미지로부터 도시의 기본 3D 기하학(건물 배치, 도로, 지형) 재구성
- Appearance Modeling, Floater 억제, Depth 감독으로 "위성 시점에서 신뢰할 수 있는 3D 표현" 제공
- 결과: 위에서 내려다본 도시는 깨끗하지만, 지면 뷰는 아직 불완전한 상태

## Stage 2
- 항상 "유일한 3D 표현"이자 렌더링 엔진 역할 (Diffusion은 2D 정제만 담당)
- Diffusion이 만든 여러 개의 고품질 이미지들을 동시에 supervision으로 받음
- 특정 Diffusion 샘플 하나에 과적합하지 않고, 여러 샘플이 공통으로 유지하는 3D 구조 쪽으로 수렴
- 결과: 기하학적으로 일관된 3D 장면이면서, 지면 시점도 포토리얼한 렌더링 가능

---
# 3. Stage 2에서 GS와 Diffusion의 역할 분담

| 역할       | GS                             | Diffusion             |
| -------- | ------------------------------ | --------------------- |
| **주체**   | 3D 표현 + 렌더링                    | 2D 이미지 정제             |
| **책임**   | 기하학적 일관성 (모든 뷰에서 같은 건물은 같은 모양) | 포토리얼리즘 (텍스처, 조명, 디테일) |
| **입력**   | 카메라 포즈                         | GS 렌더링 (불완전한 이미지)     |
| **출력**   | 렌더된 이미지                        | 고품질 정제 이미지            |
| **업데이트** | O (매 iteration마다)              | X (고정된 사전학습 모델)       |
- GS 렌더링이 "Diffusion 입장에선 denoising 중간 단계"처럼 작동
- Diffusion이 개선한 이미지로 GS를 다시 학습시키는 반복
- 이를 통해 구조는 3D 일관되고, 텍스처는 고품질인 최종 결과 달성

