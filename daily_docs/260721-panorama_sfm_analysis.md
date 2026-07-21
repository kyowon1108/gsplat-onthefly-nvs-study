| colmap 방식 | 설명                                                                                                |
| --------- | ------------------------------------------------------------------------------------------------- |
| S         | EQR 원본을 COLMAP 4.1 native spherical 카메라로 직접 재구성.                                                  |
| P         | 공식 `panorama_sfm.py`로 EQR을 12개 pinhole view로 잘라 intrinsics/rig를 고정한 rig로 재구성(12 view는 같은 중심을 공유). |

---
## 원인 종류

1. **feature는 멀쩡한데 3D 연결만 무너지는 spike**
2. **같은 입력인데 run마다 다른 frame이 튀는 spike**
3. **사진도 match도 정상인데 mapper가 조립에 실패**
4. **사진은 끝까지 정상인데 pose가 조금씩 밀리는 drift**

- 명확한 원인이 특정 scene에서 나오는 것이 아니라, 같은 seed로 돌릴 때마다도 결과가 달라지는 것으로 보아 명확한 사유를 매길 수 없었으나, 일단 발생하는 패턴 4가지에 대해 간단하게 분석을 진행함.

---

## 1. **feature는 멀쩡한데 3D 연결만 무너지는 spike (S에서만 발생)**
![](../video_picture/260721/1_lone-monk.png)
![](../video_picture/260721/1_pavillion_and_restroom.png)

- feature의 2D 대응은 풍부하지만 그것이 일관된 3D 구조로 삼각측량되지 못했고, 소수의 애매한 3D 앵커만으로 pose가 추정되면서 해당 frame만 궤적 밖으로 이탈함.
- 같은 frame에서 P는 intrinsics와 rig 기하가 고정되어 있어 이 붕괴가 발생하지 않음.

---

## 2. **같은 입력인데 run마다 다른 frame이 튀는 spike (S, P 둘 다 발생)**
![](../video_picture/260721/2_.png)
- 동일한 입력에 대해 12개 run 중 5개가 spike를 보였는데, 실패 frame이 f80, f94, f70, f10으로 실행마다 결과가 달랐음.
- 특히 동일 seed로 다시 실행해 보았으나 서로 다른 frame(f80 vs f94)에서 실패함.
- 확실한 원인을 찾지 못함.

---

## 3. **사진도 match도 정상인데 mapper가 조립에 실패 (P에서만 발생)**
![](../video_picture/260721/3_bistro.png)
- ego Bistro scene에서 15~29개의 연결되지 못한 component로 계속 조각남.
- 각 component에서는 match가 정상이었음에도 불구하고 명확한 결과가 드러나지 않은 것
- mapper의 rig frame 등록 과정이 seed에 따라 결과가 크게 달라질 수 있음으로 이해함.

---
## 4. **사진은 끝까지 정상인데 pose가 조금씩 밀리는 drift (S, P 둘 다 발생)**
![](../video_picture/260721/4_fisher_hut.png)

- 한 번의 잘못된 등록이 아니라 지속적인 미세 drift가 발생함.
- 하지만, 특정 scene의 문제인지에 대한 명확한 결과를 찾을 수 없었음.