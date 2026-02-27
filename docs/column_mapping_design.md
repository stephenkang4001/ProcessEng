# 컬럼 매핑 설계 문서

## 개요

CSV/Excel 파일을 업로드하면, Process Mining에 필요한 3개의 필수 필드를
자동으로 추론하고 사용자가 수정할 수 있는 UI를 제공합니다.

```
필수 필드
├── Case ID    → 프로세스 인스턴스 식별자 (e.g., 주문번호, 환자ID)
├── Activity   → 수행된 활동명 (e.g., "승인", "발주")
└── Timestamp  → 활동 발생 시각 (e.g., "2024-01-15 09:30:00")

선택 필드 (분석 고도화에 활용)
├── Resource   → 담당자/시스템 (org mining, 역할 분석)
├── Cost       → 비용 (성능 분석)
└── 기타 속성   → 필터링, 분석용 컨텍스트
```

---

## 자동 추론 알고리즘

### 전체 흐름

```
CSV/Excel 로드
      │
      ▼
┌─────────────────────────────────┐
│  Phase 1: 컬럼 후보 수집         │
│  - 모든 컬럼명, 데이터 타입 추출  │
│  - 샘플 값(최대 50개) 수집        │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│  Phase 2: 스코어링               │
│  - 키워드 스코어                  │
│  - 데이터 타입 스코어             │
│  - 통계적 특성 스코어             │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│  Phase 3: 후보 선택              │
│  - 필드별 최고 점수 컬럼 선택      │
│  - 충돌(같은 컬럼에 복수 매핑) 해결│
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│  Phase 4: 사용자 확인 UI         │
│  - 추론 결과 + 신뢰도 표시        │
│  - 드롭다운으로 수정 허용          │
└─────────────────────────────────┘
```

---

## Phase 1: 컬럼 후보 수집

파일 로드 후 각 컬럼에 대해 다음 정보를 수집합니다.

```python
ColumnProfile:
  name          : str        # 컬럼명 원문
  name_lower    : str        # 소문자 변환 (키워드 매칭용)
  dtype         : str        # pandas dtype (object, int64, float64, datetime64 등)
  null_ratio    : float      # 결측값 비율 (0~1)
  unique_count  : int        # 고유값 개수
  unique_ratio  : float      # 고유값 비율 = unique_count / total_rows
  sample_values : list[any]  # 최대 50개 샘플 값
  is_parseable_datetime : bool  # datetime 파싱 시도 결과
```

---

## Phase 2: 스코어링

각 컬럼에 대해 Case ID / Activity / Timestamp 역할의 점수를 0~100으로 계산합니다.

### 2-1. 키워드 스코어 (Keyword Score)

컬럼명을 소문자로 변환 후 키워드 사전과 매칭합니다.

```python
KEYWORD_DICT = {
    "case_id": {
        "exact":   ["caseid", "case_id", "traceid", "trace_id",
                    "instanceid", "process_id", "order_id"],
        "partial": ["case", "trace", "instance", "order", "id",
                    "key", "no", "num", "number", "code"],
        "score":   {"exact": 80, "partial": 40}
    },
    "activity": {
        "exact":   ["activity", "activityname", "activity_name",
                    "task", "event", "action", "step",
                    "concept:name", "eventname"],
        "partial": ["act", "task", "event", "action", "step",
                    "name", "type", "kind"],
        "score":   {"exact": 80, "partial": 40}
    },
    "timestamp": {
        "exact":   ["timestamp", "time", "datetime", "date",
                    "time:timestamp", "starttime", "start_time",
                    "endtime", "end_time", "completetime"],
        "partial": ["time", "date", "dt", "ts", "at", "when",
                    "start", "end", "complete", "created"],
        "score":   {"exact": 80, "partial": 40}
    }
}
```

### 2-2. 데이터 타입 스코어 (Type Score)

pandas가 인식한 dtype을 기반으로 점수를 부여합니다.

```
Timestamp 역할:
  datetime64[*]      → +60점  (이미 datetime으로 파싱됨)
  is_parseable_datetime == True → +50점  (파싱 가능한 문자열)
  object / string    → +0점
  int / float        → -20점  (타임스탬프가 숫자형은 드묾, UNIX epoch 제외)

Case ID 역할:
  object / string    → +20점
  int64              → +25점  (정수 ID가 흔함)
  float64            → -10점  (float ID는 드묾)

Activity 역할:
  object / string    → +30점
  int / float        → -20점  (활동명이 숫자인 경우는 드묾)
```

### 2-3. 통계적 특성 스코어 (Statistics Score)

컬럼의 고유값 비율(unique_ratio)과 결측값 비율을 분석합니다.

#### Case ID 통계 스코어

```
unique_ratio 기준:
  0.8 이상 → +40점  (대부분 고유 → 인스턴스 ID 특성)
  0.5~0.8  → +20점
  0.2~0.5  → +0점
  0.2 미만 → -20점  (너무 중복이 많음)

null_ratio 기준:
  0.0      → +10점  (결측 없음)
  0.0~0.05 → +5점
  0.05 이상 → -20점 (Case ID에 결측은 치명적)
```

#### Activity 통계 스코어

```
unique_ratio 기준:
  0.001~0.1  → +40점  (소수의 고유 활동명이 반복 → 활동 특성)
  0.1~0.3    → +20점
  0.3 이상   → -10점  (너무 다양 → 활동명보다는 Case ID 성격)
  0.001 미만 → +10점  (활동이 1~2개뿐인 단순 프로세스도 가능)

평균 문자열 길이 (활동명은 보통 2~30자):
  2~30자     → +15점
  그 외       → +0점
```

#### Timestamp 통계 스코어

```
is_parseable_datetime == True:
  파싱 성공률 0.9 이상  → +50점
  파싱 성공률 0.5~0.9  → +25점
  파싱 성공률 0.5 미만  → +0점

null_ratio 기준:
  0.0~0.05   → +10점
  0.05 이상  → -10점
```

### 2-4. 최종 스코어 합산

```python
total_score(column, role) = (
    keyword_score(column, role)   * 0.35  +  # 키워드가 가장 강력한 신호
    type_score(column, role)      * 0.35  +  # 타입도 매우 중요
    statistics_score(column, role)* 0.30     # 통계적 특성 보완
)

# 정규화: 0~100 범위로 클리핑
total_score = max(0, min(100, total_score))
```

---

## Phase 3: 후보 선택 및 충돌 해결

### 기본 선택

각 역할에 대해 가장 높은 점수의 컬럼을 1차 후보로 선택합니다.

```python
candidate = {
    "case_id":   argmax(scores["case_id"]),
    "activity":  argmax(scores["activity"]),
    "timestamp": argmax(scores["timestamp"])
}
```

### 충돌 해결 (같은 컬럼이 두 역할에 선택된 경우)

```
충돌 예시:
  case_id   → 컬럼 A (score: 75)
  activity  → 컬럼 A (score: 60)  ← 충돌!

해결 절차:
  1. 충돌한 컬럼에서 더 높은 점수의 역할이 해당 컬럼을 유지
  2. 낮은 점수의 역할은 다음 순위 컬럼으로 대체
  3. 대체 후에도 충돌이면 반복 (최대 컬럼 수만큼)
  4. 적절한 후보 없으면 해당 역할은 "미지정" 상태로 사용자에게 위임
```

### 신뢰도(Confidence) 분류

최종 선택된 점수를 신뢰도 등급으로 변환합니다.

```
점수 80 이상  → 🟢 높음 (High)   - 자동 매핑, 사용자 확인 권장
점수 50~79   → 🟡 보통 (Medium) - 자동 매핑, 사용자 확인 필요
점수 30~49   → 🟠 낮음 (Low)    - 경고 표시, 사용자 수정 권장
점수 30 미만 → 🔴 실패 (Failed) - 미지정, 사용자 직접 선택 필요
```

---

## Phase 4: 사용자 확인 UI

### UI 구성

```
┌────────────────────────────────────────────────────────────────┐
│  📋 컬럼 매핑 설정                                               │
│                                                                │
│  업로드된 컬럼: [case_id] [activity_name] [start_time] [user]   │
│                                                                │
│  ┌──────────────┬──────────────────┬──────────────┐           │
│  │  필드        │  추론된 컬럼      │  신뢰도       │           │
│  ├──────────────┼──────────────────┼──────────────┤           │
│  │  Case ID *   │  [case_id    ▼]  │  🟢 높음 92  │           │
│  │  Activity *  │  [activity.. ▼]  │  🟢 높음 88  │           │
│  │  Timestamp * │  [start_time ▼]  │  🟡 보통 65  │           │
│  │  Resource    │  [user       ▼]  │  🟡 보통 55  │           │
│  └──────────────┴──────────────────┴──────────────┘           │
│                                                                │
│  * 필수 필드                                                    │
│                                                                │
│  ⚠️  Timestamp 컬럼의 신뢰도가 보통입니다. 확인해주세요.          │
│                                                                │
│  [미리보기 (상위 5행)]                                           │
│  case_id │ activity_name │ start_time          │ user         │
│  C001    │ 구매요청       │ 2024-01-10 09:00:00 │ 홍길동       │
│  C001    │ 승인           │ 2024-01-11 14:30:00 │ 김팀장       │
│                                                                │
│              [← 다시 업로드]    [분석 시작 →]                    │
└────────────────────────────────────────────────────────────────┘
```

### 타임스탬프 형식 처리

다양한 타임스탬프 형식을 자동으로 파싱합니다.

```python
TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S",      # 2024-01-15 09:30:00
    "%Y-%m-%dT%H:%M:%S",      # 2024-01-15T09:30:00  (ISO 8601)
    "%Y-%m-%dT%H:%M:%S%z",    # 2024-01-15T09:30:00+09:00
    "%Y/%m/%d %H:%M:%S",      # 2024/01/15 09:30:00
    "%d/%m/%Y %H:%M:%S",      # 15/01/2024 09:30:00
    "%m/%d/%Y %H:%M:%S",      # 01/15/2024 09:30:00
    "%Y-%m-%d",                # 2024-01-15 (날짜만)
    "%Y/%m/%d",                # 2024/01/15
    "%d.%m.%Y %H:%M:%S",      # 15.01.2024 09:30:00
    "unix_seconds",            # 1705290600 (UNIX timestamp)
    "unix_milliseconds",       # 1705290600000
]
```

파싱 전략:
1. `pandas.to_datetime(infer_datetime_format=True)` 먼저 시도
2. 실패 시 위 포맷 목록을 순서대로 시도
3. 파싱 성공률이 90% 이상이면 해당 포맷 채택
4. 모두 실패 시 사용자에게 직접 포맷 입력 요청

---

## 유효성 검사 (Validation)

매핑 확정 후 분석 시작 전에 다음을 검사합니다.

```
1. 필수 필드 완전성
   - Case ID, Activity, Timestamp 모두 매핑되었는가?

2. 결측값 검사
   - Case ID: 결측 허용 안 함 (0%)
   - Activity: 결측 허용 안 함 (0%)
   - Timestamp: 5% 이내 결측 허용 (경고 표시)

3. 데이터 타입 검사
   - Timestamp: datetime으로 변환 가능한가?
   - Case ID: 문자열 또는 정수인가?
   - Activity: 문자열인가?

4. 최소 데이터 요건
   - 전체 이벤트 수: 10개 이상
   - 고유 Case 수: 2개 이상
   - 고유 Activity 수: 2개 이상

5. 시간 정합성
   - 같은 Case 내 이벤트가 시간 순서대로 정렬 가능한가?
   - 미래 날짜 이벤트가 과도하게 많지는 않은가? (경고)
```

---

## 구현 코드 구조

```python
# core/column_mapper.py

@dataclass
class ColumnProfile:
    name: str
    dtype: str
    null_ratio: float
    unique_count: int
    unique_ratio: float
    sample_values: list
    is_parseable_datetime: bool
    avg_str_length: float

@dataclass
class MappingResult:
    field: str            # "case_id" | "activity" | "timestamp" | "resource"
    column: str | None    # 추론된 컬럼명
    score: float          # 0~100
    confidence: str       # "high" | "medium" | "low" | "failed"
    alternatives: list[tuple[str, float]]  # 다른 후보 컬럼들

class ColumnMapper:
    def profile_columns(df: pd.DataFrame) -> list[ColumnProfile]
    def score_column(profile: ColumnProfile, role: str) -> float
    def resolve_conflicts(candidates: dict) -> dict
    def map(df: pd.DataFrame) -> list[MappingResult]
    def validate(df: pd.DataFrame, mapping: dict) -> list[str]  # 에러/경고 메시지
```

---

## 엣지 케이스 처리

| 상황 | 처리 방법 |
|------|-----------|
| 컬럼이 3개 미만 | 경고: "Process Mining에는 최소 3개 컬럼이 필요합니다" |
| 모든 컬럼 점수가 낮음 | 빨간 경고 + 모든 필드를 수동 선택 요청 |
| 타임스탬프 파싱 실패 | 포맷 직접 입력 텍스트 필드 제공 |
| 동일 컬럼명 중복 | 자동으로 `_1`, `_2` suffix 추가 후 처리 |
| 인코딩 문제 (한글 등) | `utf-8`, `cp949`, `euc-kr` 순서로 자동 시도 |
| Excel 시트 다중 | 시트 선택 드롭다운 제공 |

---

*최종 수정: 2026-02-28*
