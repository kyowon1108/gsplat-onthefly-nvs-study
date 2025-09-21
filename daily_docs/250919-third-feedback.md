### feedback

- 방 찍은거 가우시안으로 해보기 (완료)

- process 자체에 대한 이해 및 정리

- 30일에 김동준 교수님 대학원 수업 듣기 (가우시안과 카메라 파라미터에 관한 이야기 할 예정)
 
- 웹캠으로 내부 파라미터를 얻는방법 (opencv 패키지 등 설치해서) 가우시안 스플래팅 적용
 
- 가우시안 스플래팅에 내부 파라미터 건드리지 않게 하는 옵션 적용해서 colmap 적용해서 최적화 적용

- README 에 지금까지 한 것들 정리해서 넣기

---

#### 1. 방 찍은거 가우시안으로 해보기
- 학습 시간은 1시간 걸림.
- on the fly nvs보다는 조금 더 품질이 좋아 보임. (시각적으로 확인했을 때)

#### 2. intel viewsense d435 사용해 가우시안 스플래팅 적용
- 내부 파라미터가 고정되어 있으므로, train.py나 convert.py에 인자를 주어 변경할 수 있다고 판단.
- 사용 명령어
  ```bash
  take_picture : python realsense_capture.py captured_images --mode manual --num-images 150
  render : python convert.py -s data/room --camera PINHOLE
  train : python train.py -s data/room -m output/room
  render : python render.py -m output/room
  view : ./SIBR_viewers/install/bin/SIBR_gaussianViewer_app --model-path output/room
  ```

##### 학습 결과
![intel viewsense d435로 학습한 과정](../video_picture/250922_gaussian_viewsense_room_log.png)
- Dataset: 126 views, 848×480@30 fps, 노출 고정, 실내 조명 일정
- Training: 30k it, 59m 02s, 최종 PSNR 32.8 dB, Eval 주기 1000 it
- Viewing: render.py 126/126 완료, 평균 2.1 it/s

