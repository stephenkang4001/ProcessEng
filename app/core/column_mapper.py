"""
컬럼 자동 추론 모듈
CSV/Excel 컬럼을 Process Mining 필수 필드(Case ID / Activity / Timestamp)에
키워드 + 타입 + 통계 기반으로 자동 매핑합니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# ─── 키워드 사전 ────────────────────────────────────────────────────────────
KEYWORDS: dict[str, dict[str, set]] = {
    "case_id": {
        "exact": {
            "caseid", "case_id", "traceid", "trace_id", "instanceid",
            "process_id", "orderid", "order_id",
        },
        "partial": {
            "case", "trace", "instance", "order", "id", "key",
            "no", "num", "number", "code",
            "번호", "코드", "주문", "케이스", "건", "식별",
        },
    },
    "activity": {
        "exact": {
            "activity", "activityname", "activity_name", "task",
            "event", "action", "step", "concept:name", "eventname",
            "taskname", "conceptname",
        },
        "partial": {
            "act", "task", "event", "action", "step", "name", "type",
            "활동", "작업", "이벤트", "업무", "단계", "활동명", "작업명",
        },
    },
    "timestamp": {
        "exact": {
            "timestamp", "time", "datetime", "date", "time:timestamp",
            "starttime", "start_time", "endtime", "end_time",
            "completetime", "complete_time", "createdat", "eventtime",
        },
        "partial": {
            "time", "date", "dt", "ts", "at", "when",
            "start", "end", "complete", "created",
            "시각", "시간", "일시", "날짜", "일자", "타임",
        },
    },
    "resource": {
        "exact": {
            "resource", "org:resource", "user", "performer",
            "assignee", "operator", "employee",
        },
        "partial": {
            "resource", "user", "person", "agent", "role",
            "담당자", "사용자", "수행자", "작업자", "담당", "직원",
        },
    },
}

_CONFIDENCE_TABLE = [
    (80, "high",   "🟢 높음"),
    (50, "medium", "🟡 보통"),
    (30, "low",    "🟠 낮음"),
    ( 0, "failed", "🔴 실패"),
]


# ─── 데이터 클래스 ───────────────────────────────────────────────────────────
@dataclass
class ColumnProfile:
    name: str
    dtype: str
    null_ratio: float
    unique_count: int
    unique_ratio: float
    sample_values: list
    is_parseable_datetime: bool
    avg_str_length: float = 0.0


@dataclass
class MappingResult:
    field: str                                    # "case_id" | "activity" | ...
    column: Optional[str]                         # 매핑된 컬럼명 (없으면 None)
    score: float                                  # 0~100
    confidence_level: str                         # "high" | "medium" | "low" | "failed"
    confidence_label: str                         # "🟢 높음" 등
    alternatives: list[tuple[str, float]] = field(default_factory=list)


# ─── 내부 헬퍼 ──────────────────────────────────────────────────────────────
def _try_parse_datetime(series: pd.Series, sample_size: int = 50) -> float:
    """datetime 파싱 성공률을 반환 (0~1)."""
    sample = series.dropna().head(sample_size)
    if len(sample) == 0:
        return 0.0
    try:
        parsed = pd.to_datetime(sample, errors="coerce")
        return float(parsed.notna().sum()) / len(sample)
    except Exception:
        return 0.0


def _profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    """모든 컬럼의 프로필을 생성합니다."""
    total = max(len(df), 1)
    profiles = []

    for col in df.columns:
        series = df[col]
        null_ratio = float(series.isna().sum()) / total
        unique_count = int(series.nunique())
        unique_ratio = unique_count / total
        sample_vals = series.dropna().head(50).tolist()
        is_dt = _try_parse_datetime(series) >= 0.85

        avg_len = 0.0
        if series.dtype == object:
            lengths = series.dropna().astype(str).str.len()
            avg_len = float(lengths.mean()) if len(lengths) > 0 else 0.0

        profiles.append(ColumnProfile(
            name=col,
            dtype=str(series.dtype),
            null_ratio=null_ratio,
            unique_count=unique_count,
            unique_ratio=unique_ratio,
            sample_values=sample_vals,
            is_parseable_datetime=is_dt,
            avg_str_length=avg_len,
        ))
    return profiles


def _keyword_score(col_name: str, role: str) -> float:
    """키워드 매칭 스코어 (0~80)."""
    normalized = col_name.lower().replace(" ", "").replace("_", "").replace(":", "")
    kw = KEYWORDS.get(role, {})

    exact_set = {k.replace("_", "").replace(":", "") for k in kw.get("exact", set())}
    if normalized in exact_set:
        return 80.0

    for kw_part in kw.get("partial", set()):
        if kw_part.lower() in normalized:
            return 40.0

    return 0.0


def _type_score(profile: ColumnProfile, role: str) -> float:
    """데이터 타입 기반 스코어."""
    dtype = profile.dtype

    if role == "timestamp":
        if "datetime" in dtype:
            return 60.0
        if profile.is_parseable_datetime:
            return 50.0
        if ("int" in dtype or "float" in dtype) and profile.sample_values:
            if any(1e9 < v < 2e9 for v in profile.sample_values
                   if isinstance(v, (int, float))):
                return 30.0  # UNIX timestamp 가능성
        return -20.0 if ("int" in dtype or "float" in dtype) else 0.0

    elif role == "case_id":
        if "int" in dtype:
            return 25.0
        if dtype == "object":
            return 20.0
        if "float" in dtype:
            return -10.0

    elif role == "activity":
        if dtype == "object":
            return 30.0
        if "int" in dtype or "float" in dtype:
            return -20.0

    elif role == "resource":
        if dtype == "object":
            return 25.0

    return 0.0


def _stats_score(profile: ColumnProfile, role: str) -> float:
    """통계적 특성 기반 스코어."""
    ur = profile.unique_ratio
    nr = profile.null_ratio
    score = 0.0

    if role == "case_id":
        # 이벤트 로그에서 case_id의 unique_ratio는 이벤트 수 / 케이스 수에 따라 다양
        # 예: 케이스당 7이벤트 → ur≈0.14, 케이스당 2이벤트 → ur≈0.5
        if ur >= 0.5:
            score += 40.0
        elif ur >= 0.05:   # 일반 이벤트 로그의 전형적 범위
            score += 28.0
        elif ur >= 0.01:
            score += 8.0
        else:
            score -= 20.0
        score += 10.0 if nr == 0.0 else (5.0 if nr <= 0.05 else -20.0)

    elif role == "activity":
        if 0.001 <= ur <= 0.1:
            score += 40.0
        elif ur <= 0.3:
            score += 20.0
        elif ur > 0.3:
            score -= 10.0
        if 2.0 <= profile.avg_str_length <= 30.0:
            score += 15.0

    elif role == "timestamp":
        if profile.is_parseable_datetime:
            score += 50.0
        score += 10.0 if nr <= 0.05 else -10.0

    elif role == "resource":
        if 0.001 <= ur <= 0.2:
            score += 30.0
        elif ur <= 0.5:
            score += 10.0
        else:
            score -= 10.0

    return score


def _score_column(profile: ColumnProfile, role: str) -> float:
    """컬럼의 특정 역할 점수를 계산합니다 (0~100)."""
    kw = _keyword_score(profile.name, role)
    ty = _type_score(profile, role)
    st = _stats_score(profile, role)
    return max(0.0, min(100.0, kw * 0.35 + ty * 0.35 + st * 0.30))


def _get_confidence(score: float) -> tuple[str, str]:
    for threshold, level, label in _CONFIDENCE_TABLE:
        if score >= threshold:
            return level, label
    return "failed", "🔴 실패"


# ─── 메인 클래스 ─────────────────────────────────────────────────────────────
class ColumnMapper:
    """DataFrame 컬럼을 Process Mining 필드에 자동 매핑합니다."""

    REQUIRED_FIELDS = ["case_id", "activity", "timestamp"]
    OPTIONAL_FIELDS = ["resource"]
    ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

    def map(self, df: pd.DataFrame) -> list[MappingResult]:
        """컬럼 매핑을 수행하고 결과를 반환합니다."""
        profiles = _profile_columns(df)

        score_matrix = {
            f: {p.name: _score_column(p, f) for p in profiles}
            for f in self.ALL_FIELDS
        }

        assigned = self._resolve_conflicts(score_matrix)

        results = []
        for f in self.ALL_FIELDS:
            col = assigned.get(f)
            score = score_matrix[f].get(col, 0.0) if col else 0.0
            level, label = _get_confidence(score)
            alts = sorted(
                [(c, s) for c, s in score_matrix[f].items() if c != col],
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            results.append(MappingResult(
                field=f,
                column=col,
                score=score,
                confidence_level=level,
                confidence_label=label,
                alternatives=alts,
            ))
        return results

    def _resolve_conflicts(
        self, score_matrix: dict[str, dict[str, float]]
    ) -> dict[str, Optional[str]]:
        """중복 없이 각 필드에 컬럼을 할당합니다."""
        assigned: dict[str, Optional[str]] = {}
        used: set[str] = set()

        # 가장 자신 있는 필드부터 처리 (greedy)
        fields_sorted = sorted(
            self.ALL_FIELDS,
            key=lambda f: max(score_matrix[f].values()) if score_matrix[f] else 0,
            reverse=True,
        )

        for f in fields_sorted:
            candidates = sorted(
                [(c, s) for c, s in score_matrix[f].items() if c not in used],
                key=lambda x: x[1],
                reverse=True,
            )
            if candidates and candidates[0][1] >= 20.0:
                best = candidates[0][0]
                assigned[f] = best
                used.add(best)
            else:
                assigned[f] = None

        return assigned

    def validate(
        self, df: pd.DataFrame, mapping: dict[str, Optional[str]]
    ) -> list[dict]:
        """
        매핑 결과를 검증합니다.

        Returns
        -------
        list of {"level": "error" | "warning", "message": str}
        """
        msgs = []
        total = max(len(df), 1)

        for f in self.REQUIRED_FIELDS:
            col = mapping.get(f)
            if not col or col not in df.columns:
                msgs.append({"level": "error",
                             "message": f"필수 필드 '{f}'가 매핑되지 않았습니다."})
                continue

            series = df[col]
            null_ratio = series.isna().sum() / total

            if f == "case_id" and null_ratio > 0:
                msgs.append({"level": "error",
                             "message": f"Case ID 컬럼 '{col}'에 결측값이 있습니다."})

            elif f == "activity":
                if null_ratio > 0:
                    msgs.append({"level": "error",
                                 "message": f"Activity 컬럼 '{col}'에 결측값이 있습니다."})
                if series.nunique() < 2:
                    msgs.append({"level": "warning",
                                 "message": "Activity 종류가 1개뿐입니다. 분석 결과가 제한적일 수 있습니다."})

            elif f == "timestamp":
                if null_ratio > 0.05:
                    msgs.append({"level": "warning",
                                 "message": f"Timestamp 컬럼 '{col}'에 결측값이 {null_ratio*100:.1f}% 있습니다."})
                try:
                    pd.to_datetime(series.dropna().head(10), errors="raise")
                except Exception:
                    msgs.append({"level": "error",
                                 "message": f"Timestamp 컬럼 '{col}'의 날짜 형식을 인식할 수 없습니다."})

        case_col = mapping.get("case_id")
        if case_col and case_col in df.columns and df[case_col].nunique() < 2:
            msgs.append({"level": "error",
                         "message": "케이스 수가 1개입니다. 최소 2개 이상 필요합니다."})

        if total < 10:
            msgs.append({"level": "warning",
                         "message": f"이벤트 수가 {total}개로 매우 적습니다. 분석 결과가 제한적일 수 있습니다."})

        return msgs
