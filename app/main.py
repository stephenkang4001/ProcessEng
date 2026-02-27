"""
Process Mining App — 메인 진입점
단일 페이지 Streamlit 애플리케이션입니다.
실행: streamlit run app/main.py
"""
import os
import sys

# core/ 패키지 임포트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.column_mapper import ColumnMapper
from core.loader import load_csv, load_excel, load_sample
from core.miner import ProcessMiner, build_event_log
from core.stats import (
    compute_activity_stats,
    compute_case_duration_distribution,
    compute_overview,
    compute_variants,
)
from core.visualizer import ProcessVisualizer

# ─── 페이지 설정 ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Process Mining",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 세션 상태 초기화 ─────────────────────────────────────────────────────────
_DEFAULTS = {
    "df_raw":        None,   # 업로드된 원본 DataFrame
    "df_sheets":     [],     # Excel 시트 목록
    "mapping":       {},     # {field: column_name}
    "mapping_results": [],   # MappingResult 목록
    "event_log":     None,   # PM4Py EventLog
    "miner_result":  None,   # MinerResult
    "run_triggered": False,  # 분석 실행 여부
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ════════════════════════════════════════════════════════════════════════════
#  헬퍼 함수
# ════════════════════════════════════════════════════════════════════════════
def _reset_analysis():
    """데이터 변경 시 분석 결과를 초기화합니다."""
    st.session_state["event_log"]    = None
    st.session_state["miner_result"] = None
    st.session_state["run_triggered"] = False


def _load_and_infer(df: pd.DataFrame):
    """DataFrame을 받아 컬럼 매핑을 추론하고 세션에 저장합니다."""
    st.session_state["df_raw"] = df
    _reset_analysis()
    mapper = ColumnMapper()
    results = mapper.map(df)
    st.session_state["mapping_results"] = results
    st.session_state["mapping"] = {r.field: r.column for r in results}


# ════════════════════════════════════════════════════════════════════════════
#  사이드바
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("⚙️ Process Mining")
    st.caption("Process Discovery · Visualization")
    st.divider()

    # ── 1. 데이터 소스 ────────────────────────────────────────────────────
    st.subheader("📂 데이터 소스")
    data_source = st.radio(
        "데이터 선택",
        ["샘플: 구매 프로세스 (KR)", "샘플: Running Example (EN)", "파일 업로드"],
        label_visibility="collapsed",
    )

    if data_source == "샘플: 구매 프로세스 (KR)":
        if st.button("샘플 불러오기", use_container_width=True):
            with st.spinner("샘플 데이터 로딩 중..."):
                _load_and_infer(load_sample("purchase"))
            st.success("구매 프로세스 샘플 로드 완료")

    elif data_source == "샘플: Running Example (EN)":
        if st.button("샘플 불러오기", use_container_width=True):
            with st.spinner("샘플 데이터 로딩 중..."):
                _load_and_infer(load_sample("running_example"))
            st.success("Running Example 샘플 로드 완료")

    else:
        uploaded = st.file_uploader(
            "CSV 또는 Excel 파일 업로드",
            type=["csv", "xlsx", "xls"],
            label_visibility="collapsed",
        )
        if uploaded:
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            if ext == "csv":
                df_new = load_csv(uploaded)
                _load_and_infer(df_new)
            else:
                df_new, sheets = load_excel(uploaded)
                st.session_state["df_sheets"] = sheets
                if len(sheets) > 1:
                    sel_sheet = st.selectbox("시트 선택", sheets)
                    df_new, _ = load_excel(uploaded, sheet_name=sel_sheet)
                _load_and_infer(df_new)
            st.success(f"파일 로드 완료: {uploaded.name}")

    # ── 2. 컬럼 매핑 ─────────────────────────────────────────────────────
    df: pd.DataFrame | None = st.session_state["df_raw"]
    if df is not None:
        st.divider()
        st.subheader("🔧 컬럼 매핑")

        columns_with_none = ["(없음)"] + list(df.columns)
        results = st.session_state.get("mapping_results", [])
        field_labels = {
            "case_id":   "Case ID *",
            "activity":  "Activity *",
            "timestamp": "Timestamp *",
            "resource":  "Resource",
        }

        new_mapping = {}
        for r in results:
            label = field_labels.get(r.field, r.field)
            options = list(df.columns)
            none_options = ["(없음)"] + options

            current = r.column if r.column in options else None
            default_idx = (options.index(current) + 1) if current else 0

            col_a, col_b = st.columns([3, 1])
            with col_a:
                sel = st.selectbox(
                    label,
                    none_options,
                    index=default_idx,
                    key=f"map_{r.field}",
                )
            with col_b:
                st.write("")
                st.write("")
                st.caption(r.confidence_label if sel != "(없음)" else "—")

            new_mapping[r.field] = sel if sel != "(없음)" else None

        st.session_state["mapping"] = new_mapping

        # 유효성 검사 메시지
        mapper = ColumnMapper()
        msgs = mapper.validate(df, new_mapping)
        for m in msgs:
            if m["level"] == "error":
                st.error(m["message"], icon="🚫")
            else:
                st.warning(m["message"], icon="⚠️")

    # ── 3. 알고리즘 선택 ────────────────────────────────────────────────
    if df is not None:
        st.divider()
        st.subheader("⚙️ 알고리즘")

        algorithm = st.radio(
            "Discovery 알고리즘",
            ["Alpha Miner", "Heuristics Miner", "Inductive Miner"],
            index=2,
            label_visibility="collapsed",
        )

        algo_params = {}
        if algorithm == "Heuristics Miner":
            algo_params["dependency_threshold"] = st.slider(
                "Dependency Threshold",
                0.0, 1.0, 0.5, 0.05,
                help="의존도 임계값: 높을수록 모델이 단순해집니다 (기본: 0.5)",
            )
            algo_params["and_threshold"] = st.slider(
                "AND Threshold",
                0.0, 1.0, 0.65, 0.05,
                help="AND 분기 판별 임계값 (기본: 0.65)",
            )
        elif algorithm == "Inductive Miner":
            algo_params["noise_threshold"] = st.slider(
                "Noise Threshold (IMf)",
                0.0, 0.5, 0.0, 0.05,
                help="노이즈 필터 비율: 0이면 모든 케이스 반영, 높을수록 드문 경로 제거 (기본: 0.0)",
            )

        algo_info = {
            "Alpha Miner":     "📖 관계 패턴 기반. 노이즈에 취약하나 학습용으로 적합.",
            "Heuristics Miner": "📖 빈도 통계 기반. 실무 노이즈 데이터에 강함.",
            "Inductive Miner": "📖 재귀 분할 기반. Fitness 100% 보장, 실무 권장.",
        }
        st.caption(algo_info[algorithm])

        # ── 4. 시각화 타입 ──────────────────────────────────────────────
        st.divider()
        st.subheader("📊 시각화")

        viz_type = st.radio(
            "모델 유형",
            ["DFG", "Petri Net", "BPMN"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if viz_type == "DFG":
            dfg_mode = st.radio(
                "표시 기준",
                ["빈도 (Frequency)", "성능 (Performance)"],
                horizontal=True,
                label_visibility="collapsed",
            )
        else:
            dfg_mode = "빈도 (Frequency)"

        # ── 5. 실행 버튼 ─────────────────────────────────────────────────
        st.divider()
        has_required = all(
            st.session_state["mapping"].get(f) for f in ["case_id", "activity", "timestamp"]
        )
        has_errors = any(m["level"] == "error" for m in msgs) if df is not None else True

        run_btn = st.button(
            "▶ 분석 실행",
            use_container_width=True,
            type="primary",
            disabled=(not has_required or has_errors),
        )

        if not has_required:
            st.caption("⬆ 필수 컬럼(Case ID, Activity, Timestamp)을 매핑해주세요.")


# ════════════════════════════════════════════════════════════════════════════
#  분석 실행 로직
# ════════════════════════════════════════════════════════════════════════════
if "run_btn" in dir() and run_btn:
    mapping = st.session_state["mapping"]
    with st.spinner("분석 실행 중..."):
        try:
            event_log = build_event_log(
                df=st.session_state["df_raw"],
                case_col=mapping["case_id"],
                activity_col=mapping["activity"],
                timestamp_col=mapping["timestamp"],
                resource_col=mapping.get("resource"),
            )
            st.session_state["event_log"] = event_log

            algo_key = {
                "Alpha Miner":     "alpha",
                "Heuristics Miner": "heuristics",
                "Inductive Miner": "inductive",
            }[algorithm]

            miner = ProcessMiner()
            result = miner.run(event_log, algo_key, algo_params)
            st.session_state["miner_result"] = result
            st.session_state["run_triggered"] = True
        except Exception as e:
            st.error(f"분석 중 오류가 발생했습니다: {e}")
            st.session_state["run_triggered"] = False


# ════════════════════════════════════════════════════════════════════════════
#  메인 영역
# ════════════════════════════════════════════════════════════════════════════
miner_result = st.session_state.get("miner_result")
df_raw: pd.DataFrame | None = st.session_state.get("df_raw")

if not st.session_state.get("run_triggered") or miner_result is None:
    # ── 랜딩 화면 ─────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;">
      <div style="font-size:56px;margin-bottom:16px;">⚙️</div>
      <h1 style="font-size:2rem;font-weight:700;margin-bottom:8px;">Process Mining</h1>
      <p style="color:#6c757d;font-size:1.1rem;max-width:520px;margin:0 auto 32px;">
        이벤트 로그에서 프로세스 모델을 자동으로 발견하고 분석합니다.
      </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**1️⃣ 데이터 업로드**\n\n좌측 사이드바에서 샘플 데이터를 선택하거나 CSV/Excel 파일을 업로드하세요.")
    with col2:
        st.info("**2️⃣ 컬럼 매핑**\n\nCase ID, Activity, Timestamp 컬럼이 자동으로 추론됩니다. 필요시 수정하세요.")
    with col3:
        st.info("**3️⃣ 알고리즘 선택 후 실행**\n\n원하는 Discovery 알고리즘과 시각화 방식을 선택하고 분석을 실행하세요.")

    if df_raw is not None:
        st.divider()
        st.subheader("📋 데이터 미리보기")
        st.dataframe(df_raw.head(10), use_container_width=True)
        st.caption(f"총 {len(df_raw):,}행 × {len(df_raw.columns)}열")

else:
    # ── 분석 결과 화면 ────────────────────────────────────────────────────
    mapping  = st.session_state["mapping"]
    case_col = mapping["case_id"]
    act_col  = mapping["activity"]
    ts_col   = mapping["timestamp"]

    # 4가지 핵심 지표
    overview = compute_overview(df_raw, case_col, act_col, ts_col)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📦 케이스 수",   f"{overview['n_cases']:,}")
    m2.metric("⚡ 이벤트 수",   f"{overview['n_events']:,}")
    m3.metric("🔷 활동 종류",   f"{overview['n_activities']:,}")
    m4.metric("⏱ 평균 소요",
              f"{overview['avg_case_duration_hours']:.1f}h",
              help="케이스 시작~종료 평균 시간")

    st.caption(
        f"데이터 기간: {overview['start_date']} ~ {overview['end_date']} · "
        f"알고리즘: **{miner_result.algorithm.title()}** · "
        f"시각화: **{viz_type if 'viz_type' in dir() else 'DFG'}**"
    )
    st.divider()

    # 프로세스 모델 시각화
    viz_label = viz_type if "viz_type" in dir() else "DFG"
    st.subheader(f"🗺️ 프로세스 모델 — {viz_label}")

    visualizer = ProcessVisualizer()
    mode = "performance" if "성능" in (dfg_mode if "dfg_mode" in dir() else "") else "frequency"

    with st.spinner("시각화 렌더링 중..."):
        if viz_label == "DFG":
            html_content = visualizer.render_dfg(
                miner_result.dfg,
                miner_result.start_activities,
                miner_result.end_activities,
                miner_result.event_log,
                mode=mode,
            )
        elif viz_label == "Petri Net":
            html_content = visualizer.render_petri_net(
                miner_result.net,
                miner_result.initial_marking,
                miner_result.final_marking,
            )
        else:  # BPMN
            if miner_result.bpmn_model is None:
                st.warning("BPMN 모델 생성에 실패했습니다. Inductive Miner를 사용하면 품질이 향상됩니다.")
                html_content = ProcessVisualizer._error_html(
                    "BPMN 변환 실패. Inductive Miner를 선택해주세요."
                )
            else:
                html_content = visualizer.render_bpmn(miner_result.bpmn_model)

    st.components.v1.html(html_content, height=640, scrolling=False)
    st.caption("🖱️ 드래그로 이동 · 스크롤로 확대/축소 · 버튼으로 초기화")

    # ── 통계 섹션 ──────────────────────────────────────────────────────────
    st.divider()

    tab1, tab2, tab3 = st.tabs(["📈 활동별 통계", "🔀 프로세스 바리언트", "📋 이벤트 로그"])

    with tab1:
        act_stats = compute_activity_stats(df_raw, case_col, act_col, ts_col)

        col_chart, col_table = st.columns([3, 2])
        with col_chart:
            fig = px.bar(
                act_stats,
                x="frequency",
                y="activity",
                orientation="h",
                color="frequency",
                color_continuous_scale="Blues",
                labels={"frequency": "빈도", "activity": "활동"},
                title="활동별 발생 빈도",
            )
            fig.update_layout(
                height=max(300, len(act_stats) * 32),
                showlegend=False,
                coloraxis_showscale=False,
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_table:
            st.dataframe(
                act_stats.rename(columns={
                    "activity": "활동",
                    "frequency": "빈도",
                    "case_coverage_pct": "케이스 커버리지(%)",
                    "avg_duration_hours": "평균 소요(h)",
                }),
                use_container_width=True,
                hide_index=True,
            )

        # 케이스 소요 시간 분포
        durations = compute_case_duration_distribution(df_raw, case_col, ts_col)
        if len(durations) > 0:
            fig2 = px.histogram(
                durations,
                nbins=30,
                labels={"value": "소요 시간(h)", "count": "케이스 수"},
                title="케이스 소요 시간 분포",
                color_discrete_sequence=["#4C78A8"],
            )
            fig2.update_layout(margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        variants_df = compute_variants(df_raw, case_col, act_col, ts_col, top_n=10)
        st.dataframe(
            variants_df.rename(columns={
                "variant": "프로세스 경로",
                "frequency": "케이스 수",
                "coverage_pct": "커버리지(%)",
                "avg_duration_hours": "평균 소요(h)",
            }),
            use_container_width=True,
            hide_index=True,
        )
        # 바리언트 커버리지 파이 차트
        top5 = variants_df.head(5).copy()
        others_freq = variants_df.iloc[5:]["frequency"].sum() if len(variants_df) > 5 else 0
        if others_freq > 0:
            top5 = pd.concat([
                top5,
                pd.DataFrame([{"variant": "기타", "frequency": others_freq}])
            ], ignore_index=True)

        fig3 = px.pie(
            top5,
            values="frequency",
            names="variant",
            title="상위 5 바리언트 분포",
            hole=0.35,
        )
        fig3.update_traces(textposition="inside", textinfo="percent+label")
        fig3.update_layout(
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig3, use_container_width=True)

    with tab3:
        st.dataframe(
            df_raw,
            use_container_width=True,
            height=400,
        )
        st.caption(f"총 {len(df_raw):,}행 · {len(df_raw.columns)}개 컬럼")
