#### 1. conda 실행
``` bash
(base) kapr@kaprUb22:~$ source ~/miniconda3/etc/profile.d/conda.sh
```

#### 2. conda 환경 activate
``` bash
(base) kapr@kaprUb22:~$ conda activate gaussian_splatting
```

#### 3. git 저장소로 이동
``` bash
(gaussian_splatting) kapr@kaprUb22:~$ cd /home/kapr/Desktop/gaussian-splatting
```

#### 4. train.py 작동
``` bash
(gaussian_splatting) kapr@kaprUb22:~/Desktop/gaussian-splatting$ python train.py -s data/tandt/train -m output/train
Optimizing output/train
Output folder: output/train [10/09 09:28:00]
Tensorboard not available: not logging progress [10/09 09:28:00]
Reading camera 301/301 [10/09 09:28:00]
Converting point3d.bin to .ply, will happen only the first time you open the scene. [10/09 09:28:00]
Loading Training Cameras [10/09 09:28:01]
Loading Test Cameras [10/09 09:28:02]
Number of points at initialisation :  182686 [10/09 09:28:02]
Training progress:  23%|████████▋                            | 7000/30000 [05:03<21:42, 17.65it/s, Loss=0.0864041, Depth Loss=0.0000000]
[ITER 7000] Evaluating train: L1 0.061922325193881994 PSNR 20.546619033813478 [10/09 09:33:06]

[ITER 7000] Saving Gaussians [10/09 09:33:06]
Training progress: 100%|████████████████████████████████████| 30000/30000 [30:26<00:00, 16.42it/s, Loss=0.0591384, Depth Loss=0.0000000]

[ITER 30000] Evaluating train: L1 0.033260392397642134 PSNR 25.225400924682617 [10/09 09:58:29]

[ITER 30000] Saving Gaussians [10/09 09:58:29]

Training complete. [10/09 09:58:33]
```

#### 5. 최적화된 가우시안 포인트 클라우드로 render.py 작동
``` bash
(gaussian_splatting) kapr@kaprUb22:~/Desktop/gaussian-splatting$ python render.py -m output/train
Looking for config file in output/train/cfg_args
Config file found: output/train/cfg_args
Rendering output/train
Loading trained model at iteration 30000 [10/09 09:58:52]
Reading camera 301/301 [10/09 09:58:53]
Loading Training Cameras [10/09 09:58:53]
Loading Test Cameras [10/09 09:58:55]
Rendering progress: 100%|█████████████████████████████████████████████████████████████████████████████| 301/301 [01:10<00:00,  4.29it/s]
Rendering progress: 0it [00:00, ?it/s]
```

#### 6. SIBR_gaussianViewer_app 실행
``` bash
(gaussian_splatting) kapr@kaprUb22:~/Desktop/gaussian-splatting$ ./SIBR_viewers/install/bin/SIBR_gaussianViewer_app --model-path output/train
[SIBR] --  INFOS  --:	Initialization of GLFW
[SIBR] --  INFOS  --:	OpenGL Version: 4.6.0 NVIDIA 570.133.07[major: 4, minor: 6]
Number of input Images to read: 301
Number of Cameras set up: 301
[SIBR] --  INFOS  --:	Error: can't load mesh '/home/kapr/Desktop/gaussian-splatting/data/tandt/train/sparse/0/points3d.txt.
[SIBR] --  INFOS  --:	Error: can't load mesh '/home/kapr/Desktop/gaussian-splatting/data/tandt/train/sparse/0/points3d.ply.
[SIBR] --  INFOS  --:	Error: can't load mesh '/home/kapr/Desktop/gaussian-splatting/data/tandt/train/sparse/0/points3d.obj.
LOADSFM: Try to open /home/kapr/Desktop/gaussian-splatting/data/tandt/train/sparse/0/points3D.bin
Num 3D pts 182686
[SIBR] --  INFOS  --:	SfM Mesh '/home/kapr/Desktop/gaussian-splatting/data/tandt/train/sparse/0/points3d.txt successfully loaded.  (182686) vertices detected. Init GL ...
[SIBR] --  INFOS  --:	Init GL mesh complete 
Warning: GLParameter user_color does not exist in shader PointBased
[SIBR] --  INFOS  --:	Loading 1078488 Gaussian splats
[SIBR] --  INFOS  --:	Initializing Raycaster
[SIBR] --  INFOS  --:	Interactive camera using (0.009,1100) near/far planes.
Warning: GLParameter user_color does not exist in shader points_shader
Switched to trackball mode.
Switched to trackball mode.
Switched to fps&pan mode.
Switched to trackball mode.
Switched to fps&pan mode.
Switched to trackball mode.
Switched to fps&pan mode.
Switched to trackball mode.
Switched to fps&pan mode.
[SIBR] --  INFOS  --:	Deinitialization of GLFW
(gaussian_splatting) kapr@kaprUb22:~/Desktop/gaussian-splatting$ 


```