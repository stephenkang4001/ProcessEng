# 샘플 데이터 가이드

## 개요

Process Mining 앱 개발 및 테스트를 위해 두 가지 샘플 데이터셋을 제공합니다.

| 데이터셋 | 파일 | 케이스 수 | 이벤트 수 | 언어 | 특징 |
|----------|------|-----------|-----------|------|------|
| A안: 구매 프로세스 | `purchase_process.csv` / `.xlsx` | 150 | ~1,050 | 한국어 | 실무형, 컬럼명 비표준 |
| B안: Running Example | `running_example.csv` | 100 | ~620 | 영어 | PM4Py 표준, 컬럼명 표준 |

---

## A안: 구매 프로세스 (purchase_process)

### 목적

- 한국어 환경의 실무 데이터를 모사
- **컬럼 자동 추론** 기능 테스트 (비표준 컬럼명 사용)
- 여러 바리언트가 포함된 현실적인 프로세스 학습

### 컬럼 구성

| 컬럼명 | Process Mining 역할 | 타입 | 예시 |
|--------|---------------------|------|------|
| `주문번호` | **Case ID** | string | PO-2024-0001 |
| `활동명` | **Activity** | string | 구매요청, 승인, 발주 |
| `시작시각` | **Timestamp** | datetime | 2024-02-27 17:47:00 |
| `담당자` | Resource (선택) | string | 구매담당, 구매팀장 |
| `부서` | 속성 (선택) | string | IT팀, 영업팀 |
| `금액` | 속성 (선택) | float | 108000.0 |

> 컬럼명이 `주문번호`, `활동명`, `시작시각`처럼 비표준이므로
> **자동 추론 알고리즘**이 올바르게 매핑하는지 검증할 수 있습니다.

### 프로세스 구조

```
[구매요청] ──┬──→ [견적요청] → [견적검토] ──┬──→ [승인] → [발주] → [입고검수] → [대금지급]
            │                              └──→ [반려] → [재요청] ──┐
            │                                                       └→ (견적검토로 돌아감)
            └──→ [승인] → [발주] → [입고검수] → [대금지급]  ← 긴급 발주
```

### 바리언트 분포

| 바리언트 | 비율 | 케이스 수 (150건 기준) |
|----------|------|-----------------------|
| 정상경로 (견적 → 승인 → 발주) | 60% | ~90 |
| 반려 후 재요청 | 20% | ~30 |
| 긴급 발주 (견적 생략) | 15% | ~22 |
| 미완료 (중단) | 5% | ~8 |

### 담당자 (Resource) 목록

| 활동 | 담당자 후보 |
|------|------------|
| 구매요청 | 구매담당, 현업담당자 |
| 견적요청 | 구매담당 |
| 견적검토 | 구매담당, 구매팀장 |
| 승인 | 구매팀장, 재무팀장 |
| 반려 | 구매팀장, 재무팀장 |
| 발주 | 구매담당, ERP시스템 |
| 입고검수 | 창고담당, 품질담당 |
| 대금지급 | 재무담당, ERP시스템 |

### 자동 추론 기대 결과

```
주문번호  → Case ID   (신뢰도: 높음)  ← unique_ratio 높음, "번호" 키워드
활동명    → Activity  (신뢰도: 높음)  ← unique_ratio 낮음, "활동" 키워드
시작시각  → Timestamp (신뢰도: 높음)  ← datetime 파싱 성공, "시각" 키워드
담당자    → Resource  (신뢰도: 중간)  ← "담당" 키워드
```

---

## B안: Running Example (running_example)

### 목적

- Process Mining 학술 문헌에서 사용하는 **표준 예제** 재현
- PM4Py의 표준 컬럼명(`concept:name`, `time:timestamp`)을 사용하여 **호환성 테스트**
- 알고리즘 결과를 논문/강의 자료와 비교 검증

### 출처

> van der Aalst, W.M.P. (2016).
> *Process Mining: Data Science in Action* (2nd ed.), Springer.
> Chapter 2: Running Example (Order Management Process)

### 컬럼 구성

| 컬럼명 | Process Mining 역할 | 타입 | 예시 |
|--------|---------------------|------|------|
| `case:concept:name` | **Case ID** | string | case_1, case_2 |
| `concept:name` | **Activity** | string | register order, ship goods |
| `time:timestamp` | **Timestamp** | datetime (ISO 8601) | 2023-06-28T13:00:00 |
| `org:resource` | Resource (선택) | string | Sara, Mike, Pete |

> PM4Py XES 표준 컬럼명을 그대로 사용하므로
> **자동 추론**이 매우 높은 신뢰도로 매핑됩니다.

### 프로세스 구조

```
[register order] → [check credit] ──┬──→ [retrieve product] → [confirm order]
                                    │              → [ship goods] ──┬──→ [receive payment] → [archive order]
                                    │                               └──→ [archive order]
                                    ├──→ [contact customer] → [retrieve product] → ...
                                    └──→ [reject order]
```

### 바리언트 분포

| 바리언트 | 비율 |
|----------|------|
| 정상 완료 경로 | 40% |
| 고객 연락 후 처리 | 20% |
| 주문 거절 | 15% |
| 신용 확인 생략 (내부 주문) | 15% |
| 대금 수령 없이 완료 | 10% |

### 담당자 (Resource)

| 이름 | 역할 |
|------|------|
| Sara | 주문 등록, 주문 확인 |
| Pete | 제품 회수, 배송 |
| Mike | 신용 확인, 대금 수령 |
| Ellen | 신용 확인, 고객 연락 |
| Sue | 제품 회수, 배송 |
| System | 주문 아카이브 |

---

## 샘플 데이터 재생성 방법

```bash
# .venv 활성화 후 실행
.venv/bin/python3 sample_data/generate_samples.py
```

또는 `n_cases` 파라미터를 조정하여 더 많은 데이터 생성:

```python
# generate_samples.py 내 수정
df_purchase = generate_purchase_process(n_cases=500)   # 500개 케이스
df_running  = generate_running_example(n_cases=300)    # 300개 케이스
```

---

## 알고리즘별 테스트 권장 조합

| 테스트 목적 | 데이터셋 | 알고리즘 | 시각화 |
|------------|----------|----------|--------|
| 기본 동작 확인 | Running Example | Inductive Miner | DFG |
| 한국어 데이터 처리 | 구매 프로세스 | Heuristics Miner | BPMN |
| 알고리즘 비교 | 둘 다 | 3개 알고리즘 모두 | Petri Net |
| 노이즈 처리 확인 | 구매 프로세스 | Alpha vs Heuristics | Petri Net |
| 컬럼 자동추론 | 구매 프로세스 | 무관 | 무관 |

---

*최종 수정: 2026-02-28*
