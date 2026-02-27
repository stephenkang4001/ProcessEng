# Performance 계산 알고리즘 설계 문서

**버전**: 1.1.0
**작성일**: 2026-02-28

---

## 1. 개념 정의

Process Mining에서 "성능(Performance)"은 프로세스의 **시간적 특성**을 분석하는 것입니다.
단일 타임스탬프만 있는 경우와 이중 타임스탬프가 있는 경우에 따라 계산 방식이 달라집니다.

### 1.1 시간 개념 분류

```
이전 활동(A)                현재 활동(B)
├──────────────┤  대기시간  ├──────────────┤
A_start       A_end         B_start       B_end

명칭 정의:
  Service Time (A) = A_end - A_start          ← 활동 자체 처리 시간
  Waiting Time (A→B) = B_start - A_end        ← A 종료 후 B 시작까지 대기
  Inter-Event Time (A→B) = B_ts - A_ts        ← 타임스탬프 간 간격 (단일 ts일 때)
  Sojourn Time (A) = A_end - A_start          ← = Service Time (PM4Py 정의)
  Cycle Time (케이스) = 마지막 end - 첫 start  ← 케이스 전체 소요 시간
```

| 개념 | 정의 | 단일 ts | 이중 ts |
|------|------|---------|---------|
| **Service Time** | 활동 자체 처리 시간 | ❌ 불가 | ✅ end - start |
| **Inter-Event Time** | 타임스탬프 간격 | ✅ 근사치 | ✅ 정확 |
| **Waiting Time** | 활동 간 대기 시간 | ❌ 불가 | ✅ B_start - A_end |
| **Cycle Time** | 케이스 전체 소요 | ✅ 근사치 | ✅ 정확 |

---

## 2. 단일 타임스탬프 기반 성능 계산 (Inter-Event Time 방식)

### 2.1 핵심 아이디어

이벤트 로그에 타임스탬프가 하나만 있을 경우,
**연속된 두 이벤트 사이의 시간 간격**을 성능 지표로 사용합니다.
이것이 PM4Py의 Performance DFG에서 사용하는 표준 방식입니다.

```
Arc Performance(A → B) = mean( timestamp(B_i) - timestamp(A_i) )
                          for all consecutive (A, B) pairs in all cases
```

### 2.2 알고리즘

```
INPUT:  Event Log L = {케이스 c₁, c₂, ..., cₙ}
        각 케이스 cᵢ = [(activity, timestamp), ...]  (시간 순 정렬)

OUTPUT: arc_perf = {(src_activity, tgt_activity): mean_duration_seconds}

ALGORITHM:
  arc_durations = defaultdict(list)

  for each case c in L:
      events = sort_by_timestamp(c)
      for i in range(1, len(events)):
          A = events[i-1]
          B = events[i]
          duration = timestamp(B) - timestamp(A)   ← 초(seconds) 단위
          if duration >= 0:                        ← 음수 제외 (데이터 오류)
              arc_durations[(activity(A), activity(B))].append(duration)

  arc_perf = {}
  for arc, durations in arc_durations.items():
      arc_perf[arc] = {
          "mean":   mean(durations),
          "median": median(durations),
          "min":    min(durations),
          "max":    max(durations),
      }

  return arc_perf
```

### 2.3 노드 성능 (Activity-level Performance)

노드(활동) 자체의 성능은 **해당 활동에서 출발하는 모든 arc의 평균**으로 근사합니다.

```
Node Performance(A) = mean( Arc Performance(A → Bᵢ) )
                      for all outgoing arcs of A
```

이는 "활동 A가 완료된 후 다음 단계로 넘어가기까지 걸린 평균 시간"을 의미합니다.

### 2.4 해석상 주의사항

```
⚠️  단일 타임스탬프의 경우 계산된 시간은
    "활동 처리 시간 + 다음 활동까지의 대기 시간"의 합계입니다.
    즉, Service Time이 아닌 Inter-Event Time(근사 Sojourn Time)입니다.

예시:
  A_ts = 09:00,  B_ts = 11:00  →  Inter-Event Time = 2시간
  실제:  A 처리 30분 + 대기 90분  →  Service Time = 30분
  단일 ts로는 30분과 90분을 분리할 수 없음
```

---

## 3. 이중 타임스탬프 기반 성능 계산 (Lifecycle 방식)

### 3.1 XES lifecycle:transition 표준

XES 표준에서는 `lifecycle:transition` 속성으로 활동의 상태를 구분합니다.

```xml
<event>
  <string key="concept:name"       value="승인"/>
  <date   key="time:timestamp"     value="2024-01-15T14:30:00"/>  ← complete
  <string key="lifecycle:transition" value="complete"/>
</event>
<event>
  <string key="concept:name"       value="승인"/>
  <date   key="time:timestamp"     value="2024-01-15T09:00:00"/>  ← start
  <string key="lifecycle:transition" value="start"/>
</event>
```

### 3.2 이중 타임스탬프 처리 알고리즘

```
IF lifecycle:transition 컬럼 존재:

  1. Start 이벤트와 Complete 이벤트를 같은 활동으로 매핑
  2. Service Time(A) = timestamp(A_complete) - timestamp(A_start)
  3. Waiting Time(A→B) = timestamp(B_start) - timestamp(A_complete)

  PM4Py 구현:
    from pm4py.objects.log.util.interval_lifecycle import to_interval
    interval_log = to_interval(event_log)
    # → 각 이벤트에 start_timestamp, time:timestamp 두 필드 생성
```

---

## 4. PM4Py Performance DFG API

```python
import pm4py
from pm4py.algo.discovery.dfg import algorithm as dfg_algo

# 방법 1: 고수준 API
perf_dfg, start_acts, end_acts = pm4py.discover_performance_dfg(event_log)
# 반환값: {(src, tgt): mean_duration_seconds}

# 방법 2: 저수준 API (집계 방식 선택 가능)
perf_dfg = dfg_algo.apply(
    event_log,
    variant=dfg_algo.Variants.PERFORMANCE,
    parameters={
        dfg_algo.Variants.PERFORMANCE.value.Parameters.AGGREGATION_MEASURE: "mean"
        # 옵션: "mean", "median", "min", "max", "sum"
    }
)
```

---

## 5. 결합 시각화 설계 (Combined DFG)

### 5.1 단일 화면 정보 구성

```
┌─────────────────────────────────┐
│         구매요청                 │  ← 활동명
│     150회  |  avg 1.2h          │  ← 빈도 | 평균 Inter-Event Time
└─────────────────────────────────┘
노드 색상: 빈도 기반 파란색 그라데이션
  (연한 파랑=드묾, 진한 파랑=빈번)
```

```
   120회
    2.3h
───────────▶
엣지 두께: 빈도 비례 (1px ~ 6px)
엣지 색상: 성능 기반 그라데이션
  (초록=빠름, 노랑=보통, 빨강=느림)
엣지 레이블: 빈도 + 평균 Inter-Event Time
```

### 5.2 색상 인코딩 규칙

**노드 (빈도 기반, 파란색 그라데이션)**
```
intensity = frequency / max_frequency

Low  (0.0~0.3): #EBF5FB  ← 연한 하늘색
Mid  (0.3~0.7): #5DADE2  ← 중간 파랑
High (0.7~1.0): #1A5276  ← 진한 남색
```

**엣지 (성능 기반, 3색 그라데이션)**
```
t = (duration - min_duration) / (max_duration - min_duration)

Fast (t=0.0): #27AE60  ← 초록
Mid  (t=0.5): #F39C12  ← 노랑/주황
Slow (t=1.0): #E74C3C  ← 빨강
```

### 5.3 레전드

```
[노드 색상] ■ 낮은 빈도 ──────────── 높은 빈도 ■
[엣지 색상] ■ 빠름(짧은 시간) ──── 느림(긴 시간) ■
[엣지 두께] ─ 낮은 빈도          높은 빈도 ══
```

---

## 6. 논문 및 레퍼런스

### 핵심 논문

> van der Aalst, W.M.P. (2016).
> *Process Mining: Data Science in Action* (2nd ed.), Springer.
> **Chapter 6: Performance Analysis**, pp. 153–195.

> Rogge-Solti, A., Kasneci, G. (2014).
> **"Temporal Performance Profiles: A Novel Representation for Business Process Optimization."**
> *Business Process Management 2014*, LNCS 8659, 3–17.
> DOI: [10.1007/978-3-319-10172-9_1](https://doi.org/10.1007/978-3-319-10172-9_1)

> Adriansyah, A., van Dongen, B., van der Aalst, W.M.P. (2011).
> **"Conformance Checking using Cost-Based Fitness Analysis."**
> *EDOC 2011*.

### PM4Py 관련

> PM4Py 공식 문서 — Performance DFG:
> https://pm4py.fit.fraunhofer.de/documentation#discovery

> XES 표준 (IEEE 1849):
> https://www.xes-standard.org/

---

*최종 수정: 2026-02-28*
