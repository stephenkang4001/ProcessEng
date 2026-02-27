"""
Process Discovery 알고리즘 모듈
PM4Py를 래핑하여 Alpha, Heuristics, Inductive Miner를 제공합니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd
import pm4py


# ─── 결과 데이터 클래스 ──────────────────────────────────────────────────────
@dataclass
class MinerResult:
    algorithm: str                       # "alpha" | "heuristics" | "inductive"
    net: Any                             # PetriNet 객체
    initial_marking: Any                 # Marking
    final_marking: Any                   # Marking
    dfg: dict                            # {(src, tgt): frequency}
    start_activities: dict               # {activity: frequency}
    end_activities: dict                 # {activity: frequency}
    event_log: Any                       # PM4Py EventLog
    parameters: dict = field(default_factory=dict)
    bpmn_model: Optional[Any] = None     # Inductive Miner 시에만 직접 생성


# ─── 이벤트 로그 변환 ─────────────────────────────────────────────────────────
def build_event_log(
    df: pd.DataFrame,
    case_col: str,
    activity_col: str,
    timestamp_col: str,
    resource_col: Optional[str] = None,
) -> Any:
    """
    pandas DataFrame을 PM4Py EventLog로 변환합니다.

    Parameters
    ----------
    df           : 원본 DataFrame
    case_col     : Case ID 컬럼명
    activity_col : Activity 컬럼명
    timestamp_col: Timestamp 컬럼명
    resource_col : Resource 컬럼명 (선택)
    """
    work = df.copy()

    # 표준 컬럼명으로 매핑
    rename_map = {
        case_col:      "case:concept:name",
        activity_col:  "concept:name",
        timestamp_col: "time:timestamp",
    }
    if resource_col:
        rename_map[resource_col] = "org:resource"

    work = work.rename(columns=rename_map)

    # 타임스탬프 파싱
    work["time:timestamp"] = pd.to_datetime(
        work["time:timestamp"], errors="coerce", utc=False
    )

    # 결측 타임스탬프 행 제거
    work = work.dropna(subset=["time:timestamp"])

    # PM4Py 형식 변환
    work = pm4py.format_dataframe(
        work,
        case_id="case:concept:name",
        activity_key="concept:name",
        timestamp_key="time:timestamp",
    )

    # 케이스 내 시간순 정렬
    work = work.sort_values(["case:concept:name", "time:timestamp"])

    return pm4py.convert_to_event_log(work)


# ─── 알고리즘 클래스 ──────────────────────────────────────────────────────────
class ProcessMiner:
    """Process Discovery 알고리즘 실행기."""

    def run(
        self,
        event_log: Any,
        algorithm: str,
        params: dict,
    ) -> MinerResult:
        """
        알고리즘을 실행하고 결과를 반환합니다.

        Parameters
        ----------
        event_log : PM4Py EventLog
        algorithm : "alpha" | "heuristics" | "inductive"
        params    : 알고리즘별 파라미터 딕셔너리
        """
        dfg, start_acts, end_acts = pm4py.discover_dfg(event_log)

        if algorithm == "alpha":
            net, im, fm = self._run_alpha(event_log)
        elif algorithm == "heuristics":
            net, im, fm = self._run_heuristics(event_log, params)
        elif algorithm == "inductive":
            net, im, fm = self._run_inductive(event_log, params)
        else:
            raise ValueError(f"지원하지 않는 알고리즘: {algorithm}")

        # BPMN 모델 생성 (Inductive Miner는 직접 생성, 나머지는 Petri Net 변환)
        try:
            if algorithm == "inductive":
                noise = params.get("noise_threshold", 0.0)
                bpmn_model = pm4py.discover_bpmn_inductive(
                    event_log, noise_threshold=noise
                )
            else:
                bpmn_model = pm4py.convert_to_bpmn(net, im, fm)
        except Exception:
            bpmn_model = None

        return MinerResult(
            algorithm=algorithm,
            net=net,
            initial_marking=im,
            final_marking=fm,
            dfg=dfg,
            start_activities=start_acts,
            end_activities=end_acts,
            event_log=event_log,
            parameters=params,
            bpmn_model=bpmn_model,
        )

    # ─── 개별 알고리즘 ─────────────────────────────────────────────────────────
    def _run_alpha(self, event_log: Any):
        """Alpha Miner 실행."""
        return pm4py.discover_petri_net_alpha(event_log)

    def _run_heuristics(self, event_log: Any, params: dict):
        """Heuristics Miner 실행."""
        return pm4py.discover_petri_net_heuristics(
            event_log,
            dependency_threshold=params.get("dependency_threshold", 0.5),
            and_threshold=params.get("and_threshold", 0.65),
            loop_two_threshold=params.get("loop_two_threshold", 0.5),
        )

    def _run_inductive(self, event_log: Any, params: dict):
        """Inductive Miner (IMf) 실행."""
        return pm4py.discover_petri_net_inductive(
            event_log,
            noise_threshold=params.get("noise_threshold", 0.0),
        )
