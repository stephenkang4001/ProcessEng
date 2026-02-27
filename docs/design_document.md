# 설계 문서 — Process Mining Application

**버전**: 1.0.0
**작성일**: 2026-02-28
**기술 스택**: Python 3.9+ / Streamlit / PM4Py / Plotly / Graphviz

---

## 1. 프로젝트 개요

### 1.1 목적

CSV/Excel 형태의 이벤트 로그로부터 프로세스 모델을 자동으로 발견(Process Discovery)하고,
비즈니스 담당자 및 프로세스 분석가가 직관적으로 결과를 분석할 수 있는 웹 애플리케이션입니다.

### 1.2 핵심 기능 (v1.0)

| 기능 | 설명 |
|------|------|
| 데이터 업로드 | CSV, Excel(xlsx/xls) 파일 지원. 인코딩 자동 감지 |
| 컬럼 자동 매핑 | 키워드 + 타입 + 통계 기반으로 Case ID / Activity / Timestamp 자동 추론 |
| Process Discovery | Alpha Miner / Heuristics Miner / Inductive Miner 선택 실행 |
| 인터랙티브 시각화 | DFG / Petri Net / BPMN — pan, zoom, 초기화 지원 |
| 프로세스 통계 | 활동별 빈도, 케이스 소요시간 분포, 바리언트 분석 |

### 1.3 향후 확장 계획

- **Conformance Checking**: 발견된 모델과 실제 로그의 적합도 측정
- **Performance Analysis**: 병목 구간, 대기시간, 처리 시간 분석
- **Filter & Drill-down**: 기간/활동/담당자별 필터링
- **대규모 데이터 지원**: 청크 처리, 샘플링 전략
- **DB 연결**: PostgreSQL, MySQL, SAP 직접 연동

---

## 2. 시스템 아키텍처

### 2.1 레이어 구조

```
┌─────────────────────────────────────────────────────────┐
│                  Presentation Layer                      │
│             app/main.py  (Streamlit UI)                  │
│  Sidebar: 입력/설정    Main: 결과/시각화/통계              │
└───────────────────────┬─────────────────────────────────┘
                        │ session_state
┌───────────────────────▼─────────────────────────────────┐
│                  Application Layer                       │
│  core/loader.py       ─ 파일 로딩, 인코딩 처리            │
│  core/column_mapper.py ─ 컬럼 자동 추론                  │
│  core/miner.py        ─ Discovery 알고리즘 실행           │
│  core/stats.py        ─ 통계 계산                        │
│  core/visualizer.py   ─ SVG/HTML 렌더링                  │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                  External Libraries                      │
│  PM4Py  ─ Discovery 알고리즘, Petri Net, BPMN             │
│  Graphviz ─ 프로세스 모델 SVG 렌더링                       │
│  Plotly ─ 통계 차트 (bar, histogram, pie)                 │
│  Pandas ─ 데이터 처리, 통계 계산                           │
└─────────────────────────────────────────────────────────┘
```

### 2.2 디렉토리 구조

```
ProcessEng/
├── app/
│   ├── main.py                  # Streamlit 단일 페이지 앱
│   └── core/
│       ├── __init__.py
│       ├── loader.py            # CSV/Excel 로딩
│       ├── column_mapper.py     # 컬럼 자동 추론
│       ├── miner.py             # PM4Py 알고리즘 래퍼
│       ├── stats.py             # 통계 계산
│       └── visualizer.py        # SVG/HTML 시각화
├── docs/
│   ├── design_document.md       # 이 문서
│   ├── user_manual.md           # 사용자 메뉴얼
│   ├── installation_manual.md   # 설치 메뉴얼
│   ├── process_discovery_algorithms.md
│   ├── column_mapping_design.md
│   └── sample_data_guide.md
├── sample_data/
│   ├── purchase_process.csv     # 한국어 구매 프로세스 샘플
│   ├── purchase_process.xlsx    # 동일, Excel 형식
│   ├── running_example.csv      # PM4Py 표준 영문 샘플
│   └── generate_samples.py      # 샘플 데이터 재생성 스크립트
├── .venv/                       # 가상 환경
└── requirements.txt
```

---

## 3. 모듈 상세 설계

### 3.1 core/loader.py

**역할**: 파일 입출력

| 함수 | 입력 | 출력 | 설명 |
|------|------|------|------|
| `load_csv(file_obj)` | UploadedFile | DataFrame | 인코딩 자동 감지 (utf-8-sig → cp949 → euc-kr 순) |
| `load_excel(file_obj, sheet_name)` | UploadedFile, str? | (DataFrame, list[str]) | 시트 목록 반환 |
| `load_sample(sample_type)` | "purchase"\|"running_example" | DataFrame | 내장 샘플 로딩 |

**인코딩 시도 순서**: `utf-8-sig` → `utf-8` → `cp949` → `euc-kr` → `latin-1`

---

### 3.2 core/column_mapper.py

**역할**: 컬럼 자동 추론

#### 데이터 클래스

```python
@dataclass
class ColumnProfile:
    name: str                    # 컬럼명
    dtype: str                   # pandas dtype
    null_ratio: float            # 결측값 비율 (0~1)
    unique_count: int            # 고유값 수
    unique_ratio: float          # 고유값 비율
    sample_values: list          # 샘플 값 50개
    is_parseable_datetime: bool  # datetime 파싱 가능 여부
    avg_str_length: float        # 평균 문자열 길이

@dataclass
class MappingResult:
    field: str              # "case_id" | "activity" | "timestamp" | "resource"
    column: Optional[str]   # 매핑된 컬럼명
    score: float            # 0~100
    confidence_level: str   # "high" | "medium" | "low" | "failed"
    confidence_label: str   # "🟢 높음" 등
    alternatives: list      # 대안 후보 [(column, score), ...]
```

#### 스코어링 공식

```
total_score = keyword_score × 0.35
            + type_score    × 0.35
            + stats_score   × 0.30

keyword_score: exact match → 80점, partial match → 40점
type_score   : dtype 기반 (datetime → 60점, parseable_datetime → 50점 등)
stats_score  : unique_ratio, null_ratio, avg_str_length 기반

신뢰도 등급:
  80+ → 🟢 높음 (high)
  50+ → 🟡 보통 (medium)
  30+ → 🟠 낮음 (low)
   0+ → 🔴 실패 (failed)
```

#### 충돌 해결

같은 컬럼이 여러 필드에 할당되는 경우, 점수 내림차순 Greedy 방식으로 해결합니다.

---

### 3.3 core/miner.py

**역할**: Process Discovery 알고리즘 실행

#### MinerResult

```python
@dataclass
class MinerResult:
    algorithm: str       # 실행된 알고리즘 이름
    net: Any             # PM4Py PetriNet
    initial_marking: Any # PM4Py Marking
    final_marking: Any   # PM4Py Marking
    dfg: dict            # {(src, tgt): frequency}
    start_activities: dict
    end_activities: dict
    event_log: Any       # PM4Py EventLog
    parameters: dict     # 실행 파라미터
    bpmn_model: Any      # BPMN 모델 (None 가능)
```

#### build_event_log()

사용자가 매핑한 컬럼을 PM4Py 표준 컬럼명으로 변환합니다.

```
사용자 컬럼명 → PM4Py 표준
  case_col      → "case:concept:name"
  activity_col  → "concept:name"
  timestamp_col → "time:timestamp"
  resource_col  → "org:resource"  (선택)
```

#### 알고리즘 파라미터

| 알고리즘 | 파라미터 | 기본값 | 범위 |
|----------|----------|--------|------|
| Heuristics | dependency_threshold | 0.5 | 0.0~1.0 |
| Heuristics | and_threshold | 0.65 | 0.0~1.0 |
| Inductive (IMf) | noise_threshold | 0.0 | 0.0~0.5 |

---

### 3.4 core/visualizer.py

**역할**: 프로세스 모델 SVG 렌더링 + HTML pan/zoom 래핑

#### 렌더링 파이프라인

```
MinerResult
    │
    ▼
PM4Py 시각화 모듈
  (dfg_visualizer / pn_visualizer / bpmn_visualizer)
    │
    ▼ graphviz.pipe(format='svg')
SVG 문자열
    │
    ▼ _wrap_svg()
HTML (pan + zoom + touch 지원)
    │
    ▼ st.components.v1.html()
Streamlit 화면
```

#### 인터랙션 기능

| 동작 | 방법 |
|------|------|
| 이동(Pan) | 마우스 드래그 / 터치 드래그 |
| 확대/축소 | 마우스 휠 / 핀치 줌 |
| 확대 버튼 | ＋ 버튼 (×1.25) |
| 축소 버튼 | － 버튼 (×0.8) |
| 초기화 | ↺ 버튼 (scale=1, pan=0) |
| 맞춤 | ⊡ 버튼 (뷰포트에 맞게 자동 스케일) |

---

### 3.5 core/stats.py

**역할**: 프로세스 통계 계산 (pandas 기반, PM4Py 불필요)

| 함수 | 반환 | 설명 |
|------|------|------|
| `compute_overview()` | dict | 케이스 수, 이벤트 수, 활동 수, 기간 |
| `compute_activity_stats()` | DataFrame | 활동별 빈도, 커버리지, 평균 소요 시간 |
| `compute_variants()` | DataFrame | 상위 N개 바리언트, 빈도, 커버리지 |
| `compute_case_duration_distribution()` | Series | 케이스별 소요 시간 분포 |

---

### 3.6 app/main.py

**역할**: Streamlit 단일 페이지 UI 조합

#### UI 레이아웃

```
┌─ 사이드바 ──────────────┐   ┌─ 메인 영역 ─────────────────────────┐
│                         │   │                                     │
│ 📂 데이터 소스           │   │ (분석 전) 랜딩 화면                   │
│   ○ 샘플: 구매 프로세스  │   │   → 사용 방법 3단계 안내              │
│   ○ 샘플: Running Ex.  │   │   → 데이터 미리보기                   │
│   ○ 파일 업로드          │   │                                     │
│                         │   │ (분석 후) 결과 화면                   │
│ 🔧 컬럼 매핑             │   │   [케이스] [이벤트] [활동] [평균소요]  │
│   Case ID:  [드롭다운] ● │   │                                     │
│   Activity: [드롭다운] ● │   │   🗺️ 프로세스 모델 (인터랙티브)        │
│   Timestamp:[드롭다운] ● │   │   [DFG / Petri Net / BPMN 탭]       │
│   Resource: [드롭다운]   │   │                                     │
│                         │   │   📈 활동별 통계 탭                   │
│ ⚙️ 알고리즘              │   │   🔀 바리언트 탭                     │
│   ○ Alpha Miner         │   │   📋 이벤트 로그 탭                   │
│   ○ Heuristics Miner   │   │                                     │
│   ● Inductive Miner    │   │                                     │
│   [파라미터 슬라이더]    │   │                                     │
│                         │   │                                     │
│ 📊 시각화                │   │                                     │
│   ○ DFG ○ Petri ○ BPMN │   │                                     │
│                         │   │                                     │
│ [▶ 분석 실행]           │   │                                     │
└─────────────────────────┘   └─────────────────────────────────────┘
```

#### 세션 상태 관리

| 키 | 타입 | 설명 |
|----|------|------|
| `df_raw` | DataFrame | 업로드된 원본 데이터 |
| `df_sheets` | list[str] | Excel 시트 목록 |
| `mapping` | dict | {field: column_name} |
| `mapping_results` | list[MappingResult] | 추론 결과 (신뢰도 포함) |
| `event_log` | EventLog | PM4Py 이벤트 로그 |
| `miner_result` | MinerResult | 분석 결과 |
| `run_triggered` | bool | 분석 실행 여부 |

---

## 4. 데이터 흐름

```
[파일 업로드 / 샘플 선택]
         │
         ▼ load_csv() / load_excel() / load_sample()
    [DataFrame (raw)]
         │
         ▼ ColumnMapper.map()
    [MappingResult 목록]  ←── 사용자 수동 수정 가능
         │
         ▼ build_event_log()
    [PM4Py EventLog]
         │
         ▼ ProcessMiner.run()
    [MinerResult]
         │
    ┌────┴────────────────┐
    │                     │
    ▼                     ▼
[ProcessVisualizer]   [stats.py 함수들]
DFG / Petri Net / BPMN  overview / activities / variants
    │                     │
    ▼                     ▼
[st.components.html]  [st.plotly_chart]
```

---

## 5. 의존 라이브러리

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| streamlit | ≥1.32 | UI 프레임워크 |
| pm4py | ≥2.7 | Process Mining 알고리즘 |
| pandas | ≥2.0 | 데이터 처리 |
| openpyxl | ≥3.1 | Excel 읽기 |
| plotly | ≥5.18 | 통계 차트 |
| graphviz (Python) | ≥0.20 | PM4Py 시각화 래퍼 |
| graphviz (System) | ≥2.50 | SVG 렌더링 바이너리 |
| networkx | ≥3.0 | PM4Py 내부 의존성 |
| numpy | ≥1.24 | 수치 계산 |

---

## 6. 확장 포인트

### 분석 기능 확장

```python
# core/conformance.py (예정)
def check_conformance(event_log, net, im, fm) -> ConformanceResult:
    """Conformance Checking: fitness, precision 계산"""
    ...

# core/enhancer.py (예정)
def enhance_with_performance(net, im, fm, event_log) -> EnhancedNet:
    """Performance Enhancement: 대기시간, 처리시간 오버레이"""
    ...
```

### 대규모 데이터 확장

```python
# core/sampler.py (예정)
def sample_event_log(df, strategy="random", n=10000) -> pd.DataFrame:
    """대용량 로그에서 대표 샘플 추출"""
    ...
```

### DB 연결 확장

```python
# core/connector.py (예정)
class DatabaseConnector:
    def connect(self, connection_string: str) -> ...:
        """PostgreSQL / MySQL / SAP HANA 연결"""
        ...
```

---

## 7. 알려진 제한사항

| 항목 | 제한 | 향후 해결 방안 |
|------|------|----------------|
| 데이터 규모 | 메모리 내 처리 (소규모 권장) | 청크 처리, Dask |
| BPMN 품질 | Alpha/Heuristics는 변환 과정에서 품질 저하 가능 | Inductive Miner 권장 |
| 타임스탬프 | UNIX timestamp 자동 감지 미완성 | 향후 개선 |
| 인터랙션 | 노드 클릭 → 세부 정보 표시 미구현 | pyvis 기반 재설계 고려 |
| 그래프 레이아웃 | graphviz dot 레이아웃만 지원 | neato, fdp 등 추가 옵션 |

---

*문서 작성: 2026-02-28*
