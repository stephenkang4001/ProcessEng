# Process Discovery 알고리즘 레퍼런스

Process Discovery는 이벤트 로그(Event Log)로부터 자동으로 프로세스 모델을 생성하는 기법입니다.
이 문서는 본 애플리케이션에서 지원하는 3가지 핵심 알고리즘의 이론적 배경과 특성을 정리합니다.

---

## 공통 개념: Event Log와 Directly-Follows Graph

모든 알고리즘은 **이벤트 로그**를 입력으로 사용합니다.

```
Event Log = 다수의 Trace(케이스) 집합
Trace     = 순서가 있는 Event(활동) 시퀀스

예시:
  Case-001: [구매요청 → 승인 → 발주 → 입고]
  Case-002: [구매요청 → 반려 → 재요청 → 승인 → 발주 → 입고]
  Case-003: [구매요청 → 승인 → 발주 → 입고]
```

### Directly-Follows Relation (직접 선행 관계)

Activity `A` 다음에 `B`가 직접 등장하면 `A → B` 관계가 성립합니다.

```
DFG(A, B) = A 다음에 B가 등장한 횟수
```

이 관계의 **빈도(frequency)** 와 **성능(performance)** 을 시각화한 것이 **Directly-Follows Graph(DFG)** 입니다.

---

## 1. Alpha Miner

### 논문

> van der Aalst, W.M.P., Weijters, T., Maruster, L. (2004).
> **"Workflow Mining: Discovering Process Models from Event Logs."**
> *IEEE Transactions on Knowledge and Data Engineering*, 16(9), 1128–1142.
> DOI: [10.1109/TKDE.2004.47](https://doi.org/10.1109/TKDE.2004.47)

### 개요

Process Mining 분야의 **초기 핵심 알고리즘**으로, 이벤트 로그에서 4가지 관계를 추출하여 Petri Net을 생성합니다.
단순하고 이해하기 쉬워 Process Mining의 개념을 학습하는 데 적합합니다.

### 핵심 관계 정의

이벤트 로그 `L`에서 두 활동 `A`, `B` 간의 관계를 다음과 같이 정의합니다.

| 기호 | 관계 | 설명 |
|------|------|------|
| `A → B` | Directly Follows | A 다음에 B가 직접 등장 |
| `A > B` | Causality | A → B이고 B → A가 아닌 경우 |
| `A # B` | Choice | A → B도, B → A도 없는 경우 (상호 배타) |
| `A ∥ B` | Parallel | A → B이고 B → A인 경우 (병렬 실행) |

### 알고리즘 단계

```
Step 1. 이벤트 로그에서 모든 활동 집합 T_L 추출
Step 2. 시작 활동 집합 T_I, 종료 활동 집합 T_O 추출
Step 3. 각 활동 쌍에 대해 Causality(>) 관계 집합 X_L 계산
Step 4. 관계 집합을 최대화(maximized sets) → Y_L 계산
Step 5. Petri Net 구성:
        - 각 관계 쌍 → Place 생성
        - 시작/종료 Place 추가
        - Arc로 연결
```

### 특징

| 항목 | 내용 |
|------|------|
| 출력 모델 | Petri Net |
| 노이즈 처리 | 불가 (모든 패턴을 그대로 반영) |
| 루프 처리 | 길이 1 루프만 처리 가능 (길이 2 이상 불가) |
| 비순차 관계 | 일부 패턴에서 잘못된 모델 생성 가능 |
| 계산 복잡도 | O(n²) — 활동 수 기준 |
| 완전성 보장 | 없음 |

### 한계점

- **노이즈(Noise)에 취약**: 비정상적인 케이스가 하나라도 있으면 모델이 크게 달라짐
- **불완전한 로그**: 모든 패턴이 로그에 등장했다는 가정 필요
- **복잡한 루프**: 길이 2 이상의 루프(A→B→A)를 처리하지 못함
- **비가시적 활동**: 로그에 없는 숨겨진 활동(Invisible Task) 처리 불가

### 언제 사용하나?

- Process Mining 개념 학습 및 교육 목적
- 노이즈가 없고 단순한 프로세스 분석
- 다른 알고리즘 결과와 비교 기준점으로 활용

---

## 2. Heuristics Miner

### 논문

> Weijters, A.J.M.M., van der Aalst, W.M.P., Alves de Medeiros, A.K. (2006).
> **"Process Mining with the HeuristicsMiner Algorithm."**
> *BETA Working Paper Series*, WP 166, Eindhoven University of Technology.

> Weijters, A.J.M.M., Ribeiro, J.T.S. (2011).
> **"Flexible Heuristics Miner (FHM)."**
> *Proceedings of the IEEE SSCI 2011: CIDM*, 310–317.
> DOI: [10.1109/CIDM.2011.5949453](https://doi.org/10.1109/CIDM.2011.5949453)

### 개요

Alpha Miner의 노이즈 취약성을 극복하기 위해 개발된 알고리즘입니다.
활동 간 **의존도 지수(Dependency Measure)** 와 **빈도 임계값(Threshold)** 을 활용하여
노이즈를 필터링하고 더 현실적인 프로세스 모델을 생성합니다.

### 핵심 개념: Dependency Measure

두 활동 `A`, `B` 간의 의존도를 다음 수식으로 계산합니다.

```
dep(A, B) = (|A → B| - |B → A|) / (|A → B| + |B → A| + 1)

범위: -1 ~ 1
  1에 가까울수록 A 다음에 B가 자주 등장 (강한 의존)
  0에 가까울수록 의존 관계 약함
 -1에 가까울수록 B 다음에 A가 자주 등장
```

### 주요 파라미터 (임계값)

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `dependency_threshold` | 0.5 | 이 값 이상의 의존도만 연결로 인정 |
| `frequency_threshold` | 0 | 최소 발생 횟수 필터 |
| `and_threshold` | 0.65 | AND-split/join 판별 임계값 |
| `loop_two_threshold` | 0.5 | 길이 2 루프 판별 임계값 |

> **실무 팁**: `dependency_threshold`를 높일수록 모델이 단순해지고, 낮출수록 복잡해집니다.

### 알고리즘 단계

```
Step 1. Directly-Follows 빈도 행렬 계산
Step 2. 각 활동 쌍에 대해 Dependency Measure 계산
Step 3. threshold 이상인 관계만 선택 → Dependency Graph 생성
Step 4. AND/XOR 분기 판별 (and_threshold 적용)
Step 5. 길이 1, 2 루프 탐지 및 추가
Step 6. Heuristics Net → Petri Net 변환 (선택)
```

### 특징

| 항목 | 내용 |
|------|------|
| 출력 모델 | Heuristics Net (→ Petri Net 변환 가능) |
| 노이즈 처리 | 가능 (threshold로 조절) |
| 루프 처리 | 길이 1, 2 루프 지원 |
| 사용 편의성 | 파라미터 조정으로 직관적 제어 |
| 실무 활용도 | 높음 |

### 한계점

- **Fitness 보장 없음**: 생성된 모델이 이벤트 로그를 완전히 재현하지 못할 수 있음
- **복잡한 구조**: 비균형 병렬 패턴 처리 어려움
- **파라미터 의존**: 임계값 설정에 따라 결과가 크게 달라짐
- **긴 루프**: 길이 3 이상의 루프 처리 제한

### 언제 사용하나?

- 실제 업무 데이터(노이즈 포함)를 분석할 때
- 핵심 프로세스 흐름을 빠르게 파악하고 싶을 때
- 임계값 조정으로 세부 수준을 조절하고 싶을 때

---

## 3. Inductive Miner

### 논문

> Leemans, S.J.J., Fahland, D., van der Aalst, W.M.P. (2013).
> **"Discovering Block-Structured Process Models from Event Logs - A Constructive Approach."**
> *Proceedings of PETRI NETS 2013*, LNCS 7927, 311–329.
> DOI: [10.1007/978-3-642-38697-8_17](https://doi.org/10.1007/978-3-642-38697-8_17)

> Leemans, S.J.J., Fahland, D., van der Aalst, W.M.P. (2014).
> **"Discovering Block-Structured Process Models from Incomplete Event Logs."**
> *Proceedings of PETRI NETS 2014*, LNCS 8489, 91–110.
> DOI: [10.1007/978-3-319-07734-5_6](https://doi.org/10.1007/978-3-319-07734-5_6)

> Leemans, S.J.J., Fahland, D., van der Aalst, W.M.P. (2014).
> **"Process and Deviation Exploration with Inductive Visual Miner."**
> *BPM Demo Sessions 2014*.

### 개요

현재 가장 널리 사용되는 Process Discovery 알고리즘 중 하나입니다.
**재귀적 분할(Recursive Decomposition)** 방식으로 이벤트 로그를 분석하여
**Process Tree**를 생성하고, 이를 Petri Net 또는 BPMN으로 변환합니다.
**Fitness(재현율) 100%** 를 보장하는 유일한 주요 알고리즘입니다.

### 핵심 개념: Process Tree

Inductive Miner는 Petri Net 대신 **Process Tree**를 중간 표현으로 사용합니다.

```
Process Tree 연산자:

→  (Sequence)   : 순서대로 실행        A → B → C
×  (XOR Choice) : 하나만 선택 실행     A × B (A 또는 B)
∧  (Parallel)   : 동시/임의 순서 실행  A ∧ B (A와 B 병렬)
↺  (Loop)       : 반복 실행            ↺(A, B) (A 실행 후 B를 통해 반복)

예시 Process Tree:
→(
  구매요청,
  ×(승인, 반려),
  ∧(발주, 재고확인),
  입고
)
→ "구매요청 후, 승인 또는 반려 중 하나, 발주와 재고확인을 병렬로, 마지막으로 입고"
```

### 알고리즘 단계 (재귀)

```
Step 1. 이벤트 로그 L에서 DFG 계산
Step 2. 분할 기준(Cut) 탐지:
        - Sequence Cut (→): 두 그룹이 항상 순서 관계
        - XOR Cut (×):      두 그룹이 상호 배타적
        - Parallel Cut (∧): 두 그룹이 독립적으로 발생
        - Loop Cut (↺):     한 그룹이 반복 구조
Step 3. Cut을 기준으로 로그를 부분 로그로 분할
Step 4. 각 부분 로그에 대해 Step 1~3 재귀 반복
Step 5. 재귀가 더 이상 불가능하면 기본 활동 또는 flower model 생성
Step 6. Process Tree → Petri Net / BPMN 변환
```

### Inductive Miner 변형 (Variants)

| 변형 | 설명 | 노이즈 처리 |
|------|------|------------|
| **IM** (기본) | 완전한 이벤트 로그 가정 | 불가 |
| **IMf** (Inductive Miner - infrequent) | 빈도 낮은 경로 제거 (noise_threshold 파라미터) | 가능 |
| **IMd** (Inductive Miner - directly-follows) | DFG 기반, 더 빠름 | 부분적 |

> 실무에서는 **IMf**를 가장 많이 사용합니다. `noise_threshold` (0~1) 조정으로 노이즈 필터링.

### 특징

| 항목 | 내용 |
|------|------|
| 출력 모델 | Process Tree → Petri Net / BPMN |
| **Fitness 보장** | **100% (완전 재현율)** |
| **Soundness 보장** | **있음 (데드락, 무한루프 없는 모델)** |
| 노이즈 처리 | IMf 변형 사용 시 가능 |
| 루프 처리 | 모든 길이의 루프 처리 가능 |
| 계산 복잡도 | O(n³) — 더 복잡하지만 품질 높음 |

### 한계점

- **Over-fitting 가능성**: 노이즈 없는 기본 IM은 드문 경로까지 모두 포함
- **Block-structured 제약**: 비구조적(Non-block-structured) 프로세스는 완벽히 표현 못함
- **계산 비용**: 대규모 로그에서 느릴 수 있음 (IMd로 완화 가능)

### 언제 사용하나?

- **Fitness가 중요한 경우** (규제/컴플라이언스 분석)
- Conformance Checking(적합도 검사) 전 기준 모델 생성
- BPMN 다이어그램으로 결과를 공유해야 할 때
- 모델 품질을 신뢰할 수 있어야 할 때

---

## 알고리즘 비교 요약

| 항목 | Alpha Miner | Heuristics Miner | Inductive Miner |
|------|-------------|-----------------|-----------------|
| **핵심 아이디어** | 관계 패턴 추출 | 의존도 통계 | 재귀 분할 |
| **출력** | Petri Net | Heuristics Net | Process Tree → PN/BPMN |
| **Fitness 보장** | 없음 | 없음 | **있음** |
| **Soundness 보장** | 없음 | 없음 | **있음** |
| **노이즈 처리** | 불가 | 가능 | IMf 변형으로 가능 |
| **루프 지원** | 길이 1만 | 길이 1, 2 | 모든 길이 |
| **파라미터** | 없음 | 3~4개 | 1개 (noise_threshold) |
| **속도** | 빠름 | 빠름 | 보통 |
| **학습 난이도** | 낮음 (교육용) | 중간 | 중간 |
| **실무 활용도** | 낮음 | 높음 | **매우 높음** |

---

## 모델 품질 지표 (4가지 차원)

Process Discovery 알고리즘의 결과물은 다음 4가지 기준으로 평가합니다.

```
┌─────────────────────────────────────────────────────┐
│                    이벤트 로그                        │
│                        ↕                            │
│  [Fitness]          모델이 로그를 얼마나 재현하는가   │
│  [Precision]        모델이 로그에 없는 행동을 허용하지 않는가 │
│  [Generalization]   새로운 케이스를 일반화할 수 있는가 │
│  [Simplicity]       모델이 얼마나 단순한가            │
│                        ↕                            │
│                   프로세스 모델                       │
└─────────────────────────────────────────────────────┘
```

| 지표 | Alpha | Heuristics | Inductive |
|------|-------|------------|-----------|
| Fitness | 낮음 | 중간 | 높음 |
| Precision | 낮음 | 중간 | 중간 |
| Generalization | 낮음 | 중간 | 높음 |
| Simplicity | 높음 | 중간 | 높음 |

---

## 참고 라이브러리

본 애플리케이션은 **PM4Py** 라이브러리를 사용하여 위 알고리즘을 구현합니다.

```python
# PM4Py 알고리즘 사용 예시
import pm4py

# Alpha Miner
net, im, fm = pm4py.discover_petri_net_alpha(event_log)

# Heuristics Miner
net, im, fm = pm4py.discover_petri_net_heuristics(
    event_log,
    dependency_threshold=0.5
)

# Inductive Miner
net, im, fm = pm4py.discover_petri_net_inductive(
    event_log,
    noise_threshold=0.0  # IMf: 0~1 사이 값 설정
)
```

> **PM4Py 공식 문서**: https://pm4py.fit.fraunhofer.de/
> **PM4Py GitHub**: https://github.com/pm4py/pm4py-core

---

*최종 수정: 2026-02-28*
