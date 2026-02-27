"""
샘플 데이터 생성 스크립트
실행: python sample_data/generate_samples.py
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)


# ──────────────────────────────────────────────
# A안: 구매 프로세스 샘플 데이터
# ──────────────────────────────────────────────

def generate_purchase_process(n_cases: int = 150) -> pd.DataFrame:
    """
    구매 프로세스 이벤트 로그 생성

    프로세스 정의:
    ┌─ 정상 경로 (60%) ────────────────────────────────────────────┐
    │  구매요청 → 견적요청 → 견적검토 → 승인 → 발주 → 입고검수 → 대금지급  │
    └──────────────────────────────────────────────────────────────┘
    ┌─ 반려 후 재요청 경로 (20%) ──────────────────────────────────┐
    │  구매요청 → 견적요청 → 견적검토 → 반려 → 재요청               │
    │           → 견적검토 → 승인 → 발주 → 입고검수 → 대금지급      │
    └──────────────────────────────────────────────────────────────┘
    ┌─ 긴급 발주 경로 (15%) ──────────────────────────────────────┐
    │  구매요청 → 승인 → 발주 → 입고검수 → 대금지급                 │
    └──────────────────────────────────────────────────────────────┘
    ┌─ 미완료 케이스 (5%) ────────────────────────────────────────┐
    │  구매요청 → 견적요청 (중단)                                   │
    └──────────────────────────────────────────────────────────────┘
    """

    ACTIVITIES = {
        "구매요청":  {"role": ["구매담당", "현업담당자"],       "duration_hours": (0.5, 2)},
        "견적요청":  {"role": ["구매담당"],                   "duration_hours": (1, 8)},
        "견적검토":  {"role": ["구매담당", "구매팀장"],         "duration_hours": (2, 24)},
        "승인":      {"role": ["구매팀장", "재무팀장"],         "duration_hours": (1, 48)},
        "반려":      {"role": ["구매팀장", "재무팀장"],         "duration_hours": (1, 4)},
        "재요청":    {"role": ["구매담당"],                   "duration_hours": (2, 16)},
        "발주":      {"role": ["구매담당", "ERP시스템"],        "duration_hours": (0.5, 4)},
        "입고검수":  {"role": ["창고담당", "품질담당"],         "duration_hours": (4, 72)},
        "대금지급":  {"role": ["재무담당", "ERP시스템"],        "duration_hours": (24, 168)},
    }

    VARIANTS = [
        # (variant_name, activities, weight)
        ("정상경로",
         ["구매요청", "견적요청", "견적검토", "승인", "발주", "입고검수", "대금지급"],
         0.60),
        ("반려후재요청",
         ["구매요청", "견적요청", "견적검토", "반려", "재요청", "견적검토", "승인", "발주", "입고검수", "대금지급"],
         0.20),
        ("긴급발주",
         ["구매요청", "승인", "발주", "입고검수", "대금지급"],
         0.15),
        ("미완료",
         ["구매요청", "견적요청"],
         0.05),
    ]

    AMOUNTS = [50000, 120000, 300000, 750000, 1500000, 3000000, 8000000]
    DEPARTMENTS = ["IT팀", "영업팀", "생산팀", "연구소", "총무팀"]

    records = []
    base_date = datetime(2024, 1, 1, 9, 0, 0)

    for i in range(n_cases):
        case_id = f"PO-2024-{i+1:04d}"

        # 케이스 시작 시각 (2024년 내 랜덤 분포)
        case_start = base_date + timedelta(
            days=random.randint(0, 300),
            hours=random.randint(8, 17),
            minutes=random.randint(0, 59)
        )

        # 바리언트 선택
        variant = random.choices(
            [v[1] for v in VARIANTS],
            weights=[v[2] for v in VARIANTS]
        )[0]

        amount = random.choice(AMOUNTS) * random.uniform(0.8, 1.5)
        department = random.choice(DEPARTMENTS)

        current_time = case_start
        for activity in variant:
            info = ACTIVITIES[activity]
            resource = random.choice(info["role"])
            duration_h = random.uniform(*info["duration_hours"])

            records.append({
                "주문번호":      case_id,
                "활동명":        activity,
                "시작시각":      current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "담당자":        resource,
                "부서":          department,
                "금액":          round(amount, -3),
            })
            current_time += timedelta(hours=duration_h)

    df = pd.DataFrame(records)
    return df


# ──────────────────────────────────────────────
# B안: PM4Py Running Example 재현 (영문)
# ──────────────────────────────────────────────

def generate_running_example(n_cases: int = 100) -> pd.DataFrame:
    """
    PM4Py 공식 Running Example 기반 이벤트 로그
    출처: van der Aalst (2016), "Process Mining: Data Science in Action"
          Chapter 2, Running Example - Order Management

    프로세스:
      register order → check credit → ... → ship goods → receive payment → archive
    """

    VARIANTS = [
        (["register order", "check credit", "retrieve product",
          "confirm order", "ship goods", "receive payment", "archive order"], 0.40),
        (["register order", "check credit", "contact customer",
          "retrieve product", "confirm order", "ship goods", "receive payment", "archive order"], 0.20),
        (["register order", "check credit", "reject order"], 0.15),
        (["register order", "retrieve product", "confirm order",
          "ship goods", "receive payment", "archive order"], 0.15),
        (["register order", "check credit", "retrieve product",
          "confirm order", "ship goods", "archive order"], 0.10),
    ]

    RESOURCES = {
        "register order":   ["Sara", "Pete"],
        "check credit":     ["Mike", "Ellen"],
        "retrieve product": ["Pete", "Sue"],
        "confirm order":    ["Sara", "Mike"],
        "contact customer": ["Ellen", "Pete"],
        "reject order":     ["Mike", "Ellen"],
        "ship goods":       ["Sue", "Pete"],
        "receive payment":  ["Mike", "Sara"],
        "archive order":    ["System"],
    }

    records = []
    base_date = datetime(2023, 1, 1, 8, 0, 0)

    for i in range(n_cases):
        case_id = f"case_{i+1}"
        case_start = base_date + timedelta(
            days=random.randint(0, 180),
            hours=random.randint(0, 8)
        )

        variant = random.choices(
            [v[0] for v in VARIANTS],
            weights=[v[1] for v in VARIANTS]
        )[0]

        current_time = case_start
        for activity in variant:
            resource = random.choice(RESOURCES.get(activity, ["System"]))
            duration_h = random.uniform(0.5, 12)

            records.append({
                "case:concept:name": case_id,
                "concept:name":      activity,
                "time:timestamp":    current_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "org:resource":      resource,
            })
            current_time += timedelta(hours=duration_h)

    df = pd.DataFrame(records)
    return df


# ──────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import os

    output_dir = os.path.dirname(os.path.abspath(__file__))

    # A안: 구매 프로세스
    df_purchase = generate_purchase_process(n_cases=150)
    csv_path = os.path.join(output_dir, "purchase_process.csv")
    excel_path = os.path.join(output_dir, "purchase_process.xlsx")
    df_purchase.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df_purchase.to_excel(excel_path, index=False)
    print(f"[A안] 구매 프로세스 생성 완료: {len(df_purchase)}개 이벤트, {df_purchase['주문번호'].nunique()}개 케이스")
    print(f"  → {csv_path}")
    print(f"  → {excel_path}")

    # B안: Running Example
    df_running = generate_running_example(n_cases=100)
    csv_path2 = os.path.join(output_dir, "running_example.csv")
    df_running.to_csv(csv_path2, index=False, encoding="utf-8")
    print(f"\n[B안] Running Example 생성 완료: {len(df_running)}개 이벤트, {df_running['case:concept:name'].nunique()}개 케이스")
    print(f"  → {csv_path2}")

    # 미리보기
    print("\n─── A안 미리보기 (상위 5행) ───")
    print(df_purchase.head().to_string())
    print("\n─── B안 미리보기 (상위 5행) ───")
    print(df_running.head().to_string())
