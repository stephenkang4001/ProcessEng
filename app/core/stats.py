"""
프로세스 통계 모듈
이벤트 로그(DataFrame)로부터 비즈니스 분석에 유용한 통계를 계산합니다.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def compute_overview(
    df: pd.DataFrame,
    case_col: str,
    activity_col: str,
    timestamp_col: str,
) -> dict:
    """
    프로세스 개요 지표를 계산합니다.

    Returns
    -------
    {
        "n_cases":          int,
        "n_events":         int,
        "n_activities":     int,
        "start_date":       str,
        "end_date":         str,
        "avg_case_duration_hours": float,
        "median_case_duration_hours": float,
        "avg_events_per_case": float,
    }
    """
    ts = pd.to_datetime(df[timestamp_col], errors="coerce")

    # 케이스별 시작/종료 시각
    case_times = (
        df.assign(_ts=ts)
        .groupby(case_col)["_ts"]
        .agg(["min", "max"])
    )
    case_durations_h = (case_times["max"] - case_times["min"]).dt.total_seconds() / 3600
    events_per_case = df.groupby(case_col).size()

    return {
        "n_cases":           int(df[case_col].nunique()),
        "n_events":          int(len(df)),
        "n_activities":      int(df[activity_col].nunique()),
        "start_date":        ts.min().strftime("%Y-%m-%d") if pd.notna(ts.min()) else "-",
        "end_date":          ts.max().strftime("%Y-%m-%d") if pd.notna(ts.max()) else "-",
        "avg_case_duration_hours":    round(float(case_durations_h.mean()), 1),
        "median_case_duration_hours": round(float(case_durations_h.median()), 1),
        "avg_events_per_case":        round(float(events_per_case.mean()), 1),
    }


def compute_activity_stats(
    df: pd.DataFrame,
    case_col: str,
    activity_col: str,
    timestamp_col: str,
) -> pd.DataFrame:
    """
    활동별 통계를 계산합니다.

    Returns
    -------
    DataFrame with columns:
        activity, frequency, case_coverage_pct, avg_duration_hours
    """
    ts = pd.to_datetime(df[timestamp_col], errors="coerce")
    n_cases = df[case_col].nunique()

    # 활동 빈도 & 케이스 커버리지
    freq = df.groupby(activity_col).size().rename("frequency")
    coverage = (
        df.groupby(activity_col)[case_col]
        .nunique()
        .rename("case_coverage_pct")
        .apply(lambda x: round(x / n_cases * 100, 1))
    )

    # 활동별 평균 소요 시간 (같은 케이스 내 다음 이벤트와의 시간 차)
    work = df.assign(_ts=ts).sort_values([case_col, "_ts"])
    work["_next_ts"] = work.groupby(case_col)["_ts"].shift(-1)
    work["_duration_h"] = (work["_next_ts"] - work["_ts"]).dt.total_seconds() / 3600
    avg_duration = (
        work[work["_duration_h"] >= 0]
        .groupby(activity_col)["_duration_h"]
        .mean()
        .round(1)
        .rename("avg_duration_hours")
    )

    result = (
        pd.concat([freq, coverage, avg_duration], axis=1)
        .reset_index()
        .rename(columns={activity_col: "activity"})
        .sort_values("frequency", ascending=False)
        .fillna({"avg_duration_hours": 0.0})
    )
    return result


def compute_variants(
    df: pd.DataFrame,
    case_col: str,
    activity_col: str,
    timestamp_col: str,
    top_n: int = 10,
) -> pd.DataFrame:
    """
    프로세스 바리언트(경로) 통계를 계산합니다.

    Returns
    -------
    DataFrame with columns:
        variant, frequency, coverage_pct, avg_duration_hours
    """
    ts = pd.to_datetime(df[timestamp_col], errors="coerce")

    # 케이스별 활동 시퀀스
    sequences = (
        df.assign(_ts=ts)
        .sort_values([case_col, "_ts"])
        .groupby(case_col)[activity_col]
        .apply(lambda s: " → ".join(s.astype(str).tolist()))
        .rename("variant")
        .reset_index()
    )

    # 케이스별 소요 시간
    case_durations = (
        df.assign(_ts=ts)
        .groupby(case_col)["_ts"]
        .agg(lambda s: (s.max() - s.min()).total_seconds() / 3600)
        .rename("duration_h")
        .reset_index()
    )

    merged = sequences.merge(case_durations, on=case_col)

    # 바리언트별 집계
    total_cases = merged[case_col].nunique()
    variant_stats = (
        merged.groupby("variant")
        .agg(
            frequency=(case_col, "count"),
            avg_duration_hours=("duration_h", "mean"),
        )
        .reset_index()
    )
    variant_stats["coverage_pct"] = (
        variant_stats["frequency"] / total_cases * 100
    ).round(1)
    variant_stats["avg_duration_hours"] = variant_stats["avg_duration_hours"].round(1)

    return (
        variant_stats
        .sort_values("frequency", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def compute_case_duration_distribution(
    df: pd.DataFrame,
    case_col: str,
    timestamp_col: str,
) -> pd.Series:
    """케이스 소요 시간 분포를 반환합니다 (시간 단위)."""
    ts = pd.to_datetime(df[timestamp_col], errors="coerce")
    case_durations = (
        df.assign(_ts=ts)
        .groupby(case_col)["_ts"]
        .agg(lambda s: (s.max() - s.min()).total_seconds() / 3600)
    )
    return case_durations.dropna()
