### 1. Multi-Camera OTF에서 시간을 줄인 방법

[https://arxiv.org/abs/2512.08498](https://arxiv.org/abs/2512.08498)

- **Pose 4개 → rig pose 1개**
    - timestamp마다 중앙 pose 하나만 추정하고 나머지 camera pose는 상대 extrinsic으로 계산함.
    - 우리는 중앙 camera 대신 body frame을 기준으로 사용함.
- **Camera별 point subset**
    - 모든 point와 camera를 전부 연결하지 않고 camera별 3D point 집합을 유지하여 BA Jacobian 크기를 제한함.
    - 반복마다 일부 camera subset만 gradient를 계산하되 전체 camera residual로 결과를 검사함.
- **중복 없는 Gaussian 생성**
    - LoG 기준으로 새 정보가 있는 pixel만 Gaussian을 생성함.
    - 다른 camera의 Gaussian을 현재 camera에 재투영하여 위치·depth·화면상 크기가 같으면 합침.
    - 논문 결과에서 평균 Gaussian 수 674,278→585,672, memory 6,374→5,699 MB로 감소함.
- **필요한 view에만 iteration 배정**
    - 저해상도부터 시작하고 render와 입력의 주파수 차이가 큰 view에 iteration을 더 배정함.
    - 도로 장면은 camera당 10 iteration을 사용함. 단, 논문은 A100 결과이므로 현 환경에서 직접 시간을 측정해야 함.

---

### 2. 변경할 4 Camera OTF 흐름

1. **입력 단위 구성**
    - 같은 timestamp의 Front/Rear/Left/Right 4장을 `RigFrame` 하나로 묶음.
    - 카메라별 intrinsics, mask, 고정 `T_body_cam`을 함께 보관함.
2. **Fisheye 관측 생성**
    - 각 pixel을 equisolid 식( $f \sin(\theta / 2)$)으로 camera bearing으로 변환함.
    - `T_body_cam`을 이용해 bearing 방향뿐 아니라 camera 원점도 body 좌표로 변환함.
3. **초기 8 timestamp 수집**
    - 원본 OTF의 8 images를 **8 RigFrame = 32 images**로 변경함.
    - camera별 시간축 match와 같은 timestamp의 camera 간 match를 생성함.
4. **초기 body pose 계산**
    - ray 원점이 서로 다른 generalized relative-pose RANSAC으로 timestamp 간 body 이동을 구함.
5. **Rig MiniBA**
    - 최적화 변수는 8개 body pose와 3D point임.
    - camera extrinsic은 `rig.json` 값으로 고정함.
    - 4개 camera pose는 body pose에서 계산함.
    - residual은 pixel 거리가 아니라 예측 bearing과 관측 bearing 사이의 각도임.
6. **초기 Gaussian 생성**
    - 통과한 3D point와 radial range로 Gaussian을 생성함.
7. **이후 timestamp**
    - 4-camera feature → 기존 3D point match
    - generalized rig PnP RANSAC → body pose 1개
    - 4-camera pose-only BA
    - timestamp 단위 keyframe 판정
    - triangulation → Gaussian 추가·중복 제거 → mapping 순서

---