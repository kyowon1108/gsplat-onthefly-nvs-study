# `raw_scaling.clamp` 이슈 정리

## 1. 문제 상황

- rig pipeline 개선 과정에서 iter≥20 부근 CUDA illegal memory access 가 발생함.

---

## 2. 임시 안정화 조치

- raw_scaling 을 log-space 에서 [-10, 3] 으로 clamp함.
- 의도는 `exp(raw_scaling)` 의 상한 (`exp(3) = 20`) 을 두어 Gaussian size 폭발을 막는 것.

cap 경계의 정확한 의미:

| cap 경계 | exp 값 | scene scale 0.1 대비 | 의미 |
|---|---|---|---|
| max = 3 | exp(3) ≈ **20** | **200×** | 큰 ellipsoid 까지는 허용 (sky / 원경 영역 cover 가능) |
| min = −10 | exp(−10) ≈ 4.5e−5 | 0.045% | 매우 작은 Gaussian 까지 허용 (point-like 도 OK) |

- max = 3 은 *log(20)* 에서 역산. *scene scale 의 200× 까지가 한계* 라는 heuristic.
- min 은 사실상 lower bound — 학습 중 raw_scaling 이 −10 까지 떨어지는 일은 드물어 발동 빈도 낮음.

### 2.1 학습 step 위치

```mermaid
flowchart TD
    A[loss.backward<br/>line 335] --> B["optimizer.step(visibility, N)<br/>line 352"]
    B --> B1[value 갱신]
    B --> B2[exp_avg 갱신]
    B --> B3[exp_avg_sq 갱신]
    B1 --> C["★ post-step hook<br/>(여기 clamp 가 있었음)"]
    B2 --> C
    B3 --> C
    C --> D1["raw_scaling.data.clamp_(±)<br/>value 만 자름"]
    C --> D2["raw_xyz.data.clamp_(±100)"]
    C --> D3["torch.nan_to_num_(...)"]
    D1 --> E[다음 iter forward]
    D2 --> E
    D3 --> E
    style C fill:#fef3c7,stroke:#f59e0b
    style D1 fill:#fee2e2,stroke:#dc2626
```

- `param.data.clamp_()` 형태 → autograd graph 와 무관하게 raw tensor 만 변경함.
- value 만 자르는 동안 `exp_avg` / `exp_avg_sq` 는 그대로 둔 것이 §4 의 desync 의 시발점.

---

## 3. 원인 해석

`raw_scaling.data.clamp_()` 는 parameter value 만 변경하고 Adam state 는 변경하지 않음. 따라서 실제 parameter 와 optimizer momentum 사이에 state mismatch 가 생김.

### 3.1 Adam optimizer 의 3 가지 state

| 변수 | 정식 명칭 | 수식 | 직관 | reach |
|---|---|---|---|---|
| `value` (θ) | parameter | θ_t = θ_{t-1} − lr · m_t / √v_t | Gaussian 의 *현재 값* | — |
| `exp_avg` (m) | 1 차 momentum | m_t = β_1 m_{t-1} + (1−β_1) g_t | grad 의 지수가중 평균 (방향) | β_1 = 0.9 → 약 10 step |
| `exp_avg_sq` (v) | 2 차 momentum | v_t = β_2 v_{t-1} + (1−β_2) g_t² | grad² 의 지수가중 평균 (크기 / 불확실성) | β_2 = 0.999 → 약 1000 step |

- `update = lr · m / √v` — m 이 *최근* grad 추세, √v 가 *장기* grad 변동.
- 본 base 의 `SparseGaussianAdam` 도 이 구조 그대로 — 매 `optimizer.step()` 에 *세 변수 모두 갱신* 이 표준.
- **clamp 가 value 만 자르고 m, v 는 그대로 두면 *세 변수 일관성 (Adam 의 가정)* 이 깨짐** — 이게 desync 의 본질.

### 3.2 예시 — 하늘 Gaussian 의 desync 시나리오

상황 설정:

- Insta360 9-rig 학습 중 sky 영역의 큰 Gaussian.
- 하늘은 *큰 영역 단일 컬러* → photometric loss 가 *하나의 큰 Gaussian* 으로 cover 하기를 선호.
- 본 base 는 ADC 부재 → 분해 메커니즘 없음 → raw_scaling 을 키우는 압력만 누적.

학습 step 별 변화 (가상 시나리오, β_1 = 0.9, β_2 = 0.999):

| step | grad g | m (1차) | v (2차) | θ (raw_scaling) | clamp | update m/√v |
|---:|---:|---:|---:|---:|:---:|---:|
| 18 | +0.5 | 0.40 | 0.25 | 2.95 | — | 0.80 |
| 20 | +1.5 | 0.53 | 0.27 | 2.97 | — | 1.01 |
| 21 | +2.0 | 0.68 | 0.28 | 2.9999 | — | 1.29 |
| **22** | +5.0 | 1.11 | 0.30 | **cap → 3.00** | **★** | 2.03 ← *desync 시작* |
| 23 | +2.0 | 1.20 | 0.30 | 3.00 (cap) | ★ | 2.19 |
| 24 | +3.0 | 1.38 | 0.30 | 3.00 (cap) | ★ | **2.52** |
| 25+ | — | 1.5+ ↑↑ | 0.30 (정체) | 3.00 + Δ_huge | — | **5+ spike** → overflow |

핵심 패턴:

- step 22 에서 cap 발동 → value (θ) 는 3.0 에 고정.
- m 은 *β_1 = 0.9* 로 *빠르게 누적* — 1.11 → 1.20 → 1.38 → 1.5+ 로 매 step 점점 큼.
- v 는 *β_2 = 0.999* 로 *거의 정체* — 0.30 근처 머묾.
- update = m / √v → m 만 커지고 √v 그대로 → **update 가 점점 spike**.
- 어느 시점 update 가 비정상적으로 커서 cap 다시 씌우기 *전에* rasterizer 의 tile-count arithmetic 을 overflow → cuda crash.

→ 즉 cap 이 value 만 막고 *m, v 는 폭주하도록 방치* 한 구조가 *m / √v lag 차이* 를 통해 spike 생성. *증상을 막으려던 cap 이 같은 증상을 만들어내는* 메커니즘이 이것.

### 3.3 같은 crash 로 이어지는 두 경로

```mermaid
flowchart TD
    Spawn[spawn-only 설계<br/>ADC 부재] --> Drift[raw_scaling 발산 압력]
    Drift --> Overflow["exp(raw_scaling) overflow"]
    Overflow --> Crash[cudaErrorIllegalAddress<br/>at iter≥20]

    Drift -. clamp 도입 .-> Cap["raw_scaling.data.clamp_(max=3)"]
    Cap --> ValOnly[value 만 잘림]
    ValOnly --> StateAsIs[exp_avg / exp_avg_sq 그대로]
    StateAsIs --> Desync[다음 step desync 누적]
    Desync --> Crash

    style Crash fill:#fee2e2,stroke:#dc2626
    style Cap fill:#fef3c7,stroke:#f59e0b
```

- `param.data.clamp_()` 는 value 만 잘라내고 Adam 의 1·2 차 momentum (`exp_avg`, `exp_avg_sq`) 은 그대로 둠.
- 다음 iter 의 Adam step 이 cap 위쪽으로 갈 것을 가정한 통계로 갱신을 시도 → value 와 state 의 desync 누적.
- 누적된 desync 가 어느 시점 단일 update 를 비정상적으로 큰 값으로 만들고, 결과적으로 rasterizer 가 깨짐.
- 즉 *증상을 막으려던 cap 이 동일한 증상을 만들어내는* 역설 — 그림에서 두 경로가 같은 Crash 노드로 모임.

### 3.2 Adam state 정합성 — 본 base 의 표준 패턴

`scene/optimizers.py:121-144` 의 `SparseGaussianAdam.add_and_prune()` 가 올바른 패턴:

```python
param["val"]        = cat(param["val"][mask],        new)
param["exp_avg"]    = cat(param["exp_avg"][mask],    zeros)
param["exp_avg_sq"] = cat(param["exp_avg_sq"][mask], zeros)
```

| 항목 | 잘못된 패턴 (도입된 clamp) | 올바른 패턴 (`add_and_prune`) |
|---|:---:|:---:|
| `param["val"]` | 변경 ✓ | 변경 ✓ |
| `param["exp_avg"]` | 그대로 (변경 X) | 변경 ✓ |
| `param["exp_avg_sq"]` | 그대로 (변경 X) | 변경 ✓ |
| Adam 의 다음 step 일관성 | 깨짐 → desync 누적 | 유지 |

- value + exp_avg + exp_avg_sq 를 같은 mask 로 동시 처리하는 표준 패턴.
- 본 base 안 5 군데 (`add_new_gaussians` 등) 에서 사용됨.
- 도입된 clamp 는 이 패턴을 따르지 않고 value 만 잘라낸 것이 핵심 결함.

---

## 4. 구조적 원인

더 근본적으로는 현재 구현에 원본 3DGS 의 split / clone / prune 기반 ADC 가 없음. 따라서 일부 Gaussian 이 커지는 압력 자체는 여전히 존재함.

### 4.1 동작 비교 — 원본 3DGS vs on-the-fly NVS

| 동작 | 원본 3DGS (Kerbl 2023) | on-the-fly NVS (본 base) |
|---|---|---|
| 새 Gaussian 추가 | `densify_and_prune()` (every N iter, 보통 100) | `add_new_gaussians()` (keyframe 추가 시점만) |
| 큰 Gaussian → 작은 여러 개 분해 | **split** (gradient 큰 Gaussian 의 큰 축으로 둘로 나눔) | **없음** |
| 작은 Gaussian 복제 | **clone** (gradient 크고 size 작은 Gaussian 복제 후 약간 이동) | **없음** |
| Pruning | 매 N iter (opacity < threshold 또는 size > screen 비율) | spawn 시점만 (`opacity > 0.05` AND `screen_size < 0.5W`) |
| raw_scaling 발산 시 동작 | split 이 자동 분해 → scaling 자연 감소 | 분해 없음 → scaling 발산 누적 |

### 4.2 Iteration 흐름 비교

| 시점 | 원본 3DGS | on-the-fly NVS |
|---|---|---|
| spawn / 초기화 | COLMAP point cloud + densify init | keyframe 추가 시 `add_new_gaussians()` |
| iter 1 ~ (N−1) | photometric optimization | photometric optimization |
| iter N (densify trigger) | split / clone / prune 으로 Gaussian 집합 갱신 | 분해 메커니즘 부재 — 집합 그대로 |
| iter (N+1) ~ | 갱신된 집합으로 학습 (큰 Gaussian 분해된 상태) | 발산 압력이 누적된 채 학습 |
| 누적 결과 | scaling 분포 자연 유지 | raw_scaling 일부 unbounded |

- 원본 3DGS 는 *큰 Gaussian* 이 발생하면 split 으로 자동 분해 → `exp(raw_scaling)` 가 일정 한도 이하로 자연 유지됨.
- on-the-fly NVS 는 분해 메커니즘이 없어 큰 Gaussian 영역의 raw_scaling 이 photometric loss 압력에 따라 unbounded 로 누적. 

- 이 차이는 현재 구현에서 raw_scaling 이 제어되지 않고 증가할 수 있는 구조적 배경 원인으로 볼 수 있음.