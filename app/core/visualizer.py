"""
시각화 모듈
DFG / Petri Net / BPMN을 인터랙티브 HTML(SVG + pan/zoom)로 렌더링합니다.
graphviz 시스템 바이너리가 설치되어 있어야 합니다.
"""
from __future__ import annotations

import tempfile
import os
from typing import Any

# ─── SVG Pan/Zoom HTML 템플릿 ────────────────────────────────────────────────
_SVG_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #f8f9fa; overflow: hidden; }}
  #outer {{
    position: relative;
    width: 100%;
    height: {height}px;
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    overflow: hidden;
    cursor: grab;
    user-select: none;
  }}
  #outer:active {{ cursor: grabbing; }}
  #wrapper {{
    position: absolute;
    top: 0; left: 0;
    transform-origin: 0 0;
    width: 100%;
    height: 100%;
  }}
  #wrapper svg {{
    width: 100%;
    height: 100%;
    max-width: none;
    display: block;
  }}
  #controls {{
    position: absolute;
    bottom: 12px;
    right: 12px;
    display: flex;
    gap: 6px;
    z-index: 10;
  }}
  .ctrl-btn {{
    padding: 5px 10px;
    border: 1px solid #adb5bd;
    border-radius: 5px;
    background: rgba(255,255,255,0.92);
    cursor: pointer;
    font-size: 13px;
    color: #495057;
    box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  }}
  .ctrl-btn:hover {{ background: #e9ecef; }}
  #zoom-label {{
    position: absolute;
    bottom: 12px;
    left: 12px;
    font-size: 11px;
    color: #868e96;
    background: rgba(255,255,255,0.8);
    padding: 3px 7px;
    border-radius: 4px;
  }}
</style>
</head>
<body>
<div id="outer">
  <div id="wrapper">{svg_content}</div>
  <div id="zoom-label" id="zlbl">100%</div>
  <div id="controls">
    <button class="ctrl-btn" onclick="zoomIn()">＋</button>
    <button class="ctrl-btn" onclick="zoomOut()">－</button>
    <button class="ctrl-btn" onclick="resetView()">↺ 초기화</button>
    <button class="ctrl-btn" onclick="fitView()">⊡ 맞춤</button>
  </div>
</div>
<script>
(function() {{
  const outer   = document.getElementById('outer');
  const wrapper = document.getElementById('wrapper');
  const zlbl    = document.getElementById('zoom-label');

  let scale = 1, panX = 0, panY = 0;
  let drag  = false, sx = 0, sy = 0, spx = 0, spy = 0;

  function apply() {{
    wrapper.style.transform = `translate(${{panX}}px,${{panY}}px) scale(${{scale}})`;
    zlbl.textContent = Math.round(scale * 100) + '%';
  }}

  /* ── 드래그 pan ── */
  outer.addEventListener('mousedown', e => {{
    if (e.button !== 0) return;
    drag = true; sx = e.clientX; sy = e.clientY; spx = panX; spy = panY;
    e.preventDefault();
  }});
  document.addEventListener('mousemove', e => {{
    if (!drag) return;
    panX = spx + (e.clientX - sx);
    panY = spy + (e.clientY - sy);
    apply();
  }});
  document.addEventListener('mouseup', () => {{ drag = false; }});

  /* ── 휠 zoom ── */
  outer.addEventListener('wheel', e => {{
    e.preventDefault();
    const rect = outer.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    const ns = Math.min(Math.max(scale * factor, 0.05), 15);
    panX = mx - (mx - panX) * (ns / scale);
    panY = my - (my - panY) * (ns / scale);
    scale = ns;
    apply();
  }}, {{ passive: false }});

  /* ── 터치 지원 ── */
  let tDist = null;
  outer.addEventListener('touchstart', e => {{
    if (e.touches.length === 1) {{
      drag = true; sx = e.touches[0].clientX; sy = e.touches[0].clientY;
      spx = panX; spy = panY;
    }} else if (e.touches.length === 2) {{
      tDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX,
                         e.touches[0].clientY - e.touches[1].clientY);
    }}
    e.preventDefault();
  }}, {{ passive: false }});
  outer.addEventListener('touchmove', e => {{
    if (e.touches.length === 1 && drag) {{
      panX = spx + (e.touches[0].clientX - sx);
      panY = spy + (e.touches[0].clientY - sy);
      apply();
    }} else if (e.touches.length === 2 && tDist) {{
      const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX,
                           e.touches[0].clientY - e.touches[1].clientY);
      scale = Math.min(Math.max(scale * d / tDist, 0.05), 15);
      tDist = d;
      apply();
    }}
    e.preventDefault();
  }}, {{ passive: false }});
  outer.addEventListener('touchend', () => {{ drag = false; tDist = null; }});

  /* ── 버튼 ── */
  window.zoomIn   = () => {{ scale = Math.min(scale * 1.25, 15);   apply(); }};
  window.zoomOut  = () => {{ scale = Math.max(scale * 0.80, 0.05); apply(); }};
  window.resetView = () => {{ scale = 1; panX = 0; panY = 0; apply(); }};
  window.fitView  = () => {{
    const svg = wrapper.querySelector('svg');
    if (!svg) return;
    const sw = svg.getBoundingClientRect().width  || outer.clientWidth;
    const sh = svg.getBoundingClientRect().height || outer.clientHeight;
    const scaleX = outer.clientWidth  / sw;
    const scaleY = outer.clientHeight / sh;
    scale = Math.min(scaleX, scaleY) * 0.92;
    panX = (outer.clientWidth  - sw * scale) / 2;
    panY = (outer.clientHeight - sh * scale) / 2;
    apply();
  }};

  apply();
}})();
</script>
</body>
</html>"""


def _wrap_svg(svg_content: str, height: int = 620) -> str:
    """SVG 문자열을 pan/zoom 가능한 HTML로 감쌉니다."""
    # SVG 태그에 고정 크기 제거 (뷰포트에 맞춤)
    import re
    svg_content = re.sub(r'<svg\s', '<svg preserveAspectRatio="xMidYMid meet" ', svg_content, count=1)
    return _SVG_TEMPLATE.format(svg_content=svg_content, height=height)


def _model_to_svg(gviz) -> str:
    """graphviz Source 객체를 SVG 문자열로 변환합니다."""
    try:
        svg_bytes = gviz.pipe(format="svg")
        return svg_bytes.decode("utf-8")
    except Exception as e:
        raise RuntimeError(
            f"SVG 렌더링 실패: {e}\n"
            "graphviz가 설치되어 있는지 확인하세요: brew install graphviz"
        )


# ─── DFG 결합 시각화 헬퍼 함수 ───────────────────────────────────────────────
def _freq_color(freq: int, max_freq: int) -> str:
    """빈도 기반 파란색 그라데이션 색상 반환 (hex 문자열)."""
    if max_freq == 0:
        return "#D6EAF8"
    t = freq / max_freq
    if t < 0.25:
        return "#D6EAF8"   # 매우 연한 파랑
    elif t < 0.50:
        return "#7FB3D3"   # 연한 파랑
    elif t < 0.75:
        return "#2E86C1"   # 중간 파랑
    else:
        return "#1A5276"   # 진한 남색


def _perf_color(t: float) -> str:
    """
    성능 정규화 값 (0.0=빠름, 1.0=느림) → hex 색상.
    green(#27AE60) → yellow(#F1C40F) → red(#E74C3C)
    """
    t = max(0.0, min(1.0, t))
    if t <= 0.5:
        t2 = t * 2.0
        r = int(39  + (241 - 39)  * t2)
        g = int(174 + (196 - 174) * t2)
        b = int(96  + (15  - 96)  * t2)
    else:
        t2 = (t - 0.5) * 2.0
        r = int(241 + (231 - 241) * t2)
        g = int(196 + (76  - 196) * t2)
        b = int(15  + (60  - 15)  * t2)
    return f"#{r:02X}{g:02X}{b:02X}"


def _is_dark(hex_color: str) -> bool:
    """색상이 어두운지 판별하여 폰트 색상(흰/검)을 결정합니다."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance < 130


def _fmt_dur(seconds: float) -> str:
    """초 단위 시간을 가독성 있는 형식으로 변환합니다."""
    if seconds < 60:
        return f"{seconds:.0f}초"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}분"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}시간"
    else:
        return f"{seconds / 86400:.1f}일"


# ─── 공개 API ────────────────────────────────────────────────────────────────
class ProcessVisualizer:
    """Process Mining 모델을 인터랙티브 HTML로 렌더링합니다."""

    def render_dfg(
        self,
        dfg: dict,
        start_activities: dict,
        end_activities: dict,
        event_log: Any,
        mode: str = "frequency",
        height: int = 620,
    ) -> str:
        """
        DFG(Directly-Follows Graph)를 HTML로 렌더링합니다.

        Parameters
        ----------
        mode : "frequency" | "performance"
        """
        from pm4py.visualization.dfg import visualizer as dfg_vis

        if mode == "performance":
            variant = dfg_vis.Variants.PERFORMANCE
        else:
            variant = dfg_vis.Variants.FREQUENCY

        parameters = {
            "start_activities": start_activities,
            "end_activities": end_activities,
        }

        try:
            gviz = dfg_vis.apply(dfg, log=event_log, variant=variant,
                                 parameters=parameters)
            svg = _model_to_svg(gviz)
            return _wrap_svg(svg, height=height)
        except Exception as e:
            return self._error_html(str(e), height)

    def render_dfg_combined(
        self,
        dfg: dict,
        performance_dfg: dict,
        start_activities: dict,
        end_activities: dict,
        activities_count: dict,
        height: int = 640,
    ) -> str:
        """
        빈도(Frequency) + 성능(Performance)을 결합한 DFG를 한 화면에 렌더링합니다.

        시각적 인코딩
        ----------
        · 노드 색상 : 빈도 기반 파란색 그라데이션 (연파랑 → 진남색)
        · 엣지 두께 : 빈도 비례 (1 ~ 6 px)
        · 엣지 색상 : 성능 기반 초록 → 노랑 → 빨강 그라데이션
        · 레이블    : 빈도(N회) + 평균 Inter-Event Time (arc 단위)

        Parameters
        ----------
        dfg              : {(src, tgt): frequency}
        performance_dfg  : {(src, tgt): mean_duration_seconds}
        start_activities : {activity: frequency}
        end_activities   : {activity: frequency}
        activities_count : {activity: event_count}
        """
        try:
            import graphviz

            # ── 정규화 기준값 계산 ──────────────────────────────────────────
            freq_vals = list(dfg.values())
            max_freq  = max(freq_vals) if freq_vals else 1
            min_freq  = min(freq_vals) if freq_vals else 0

            perf_vals = list(performance_dfg.values())
            max_perf  = max(perf_vals) if perf_vals else 1
            min_perf  = min(perf_vals) if perf_vals else 0

            act_max = max(activities_count.values()) if activities_count else 1

            # ── Digraph 생성 ────────────────────────────────────────────────
            dot = graphviz.Digraph(
                "combined_dfg",
                graph_attr={
                    "bgcolor": "white",
                    "rankdir": "LR",
                    "fontname": "Helvetica,Arial,sans-serif",
                    "pad": "0.5",
                    "nodesep": "0.55",
                    "ranksep": "0.9",
                },
                node_attr={"fontname": "Helvetica,Arial,sans-serif"},
                edge_attr={"fontname": "Helvetica,Arial,sans-serif"},
            )

            # ── Start 노드 ──────────────────────────────────────────────────
            dot.node(
                "__start__",
                label="●",
                shape="circle",
                style="filled",
                fillcolor="#27AE60",
                fontcolor="white",
                fontsize="14",
                width="0.5",
                height="0.5",
                fixedsize="true",
            )

            # ── End 노드 ────────────────────────────────────────────────────
            dot.node(
                "__end__",
                label="■",
                shape="doublecircle",
                style="filled",
                fillcolor="#E74C3C",
                fontcolor="white",
                fontsize="12",
                width="0.5",
                height="0.5",
                fixedsize="true",
            )

            # ── 활동 노드 ───────────────────────────────────────────────────
            all_acts: set = set(activities_count.keys())
            for src, tgt in dfg:
                all_acts.add(src)
                all_acts.add(tgt)

            for act in all_acts:
                freq = activities_count.get(act, 0)

                # 해당 활동 outgoing arc 성능 평균
                out_perfs = [
                    performance_dfg[(s, t)]
                    for (s, t) in performance_dfg
                    if s == act
                ]
                avg_perf = sum(out_perfs) / len(out_perfs) if out_perfs else None

                fill   = _freq_color(freq, act_max)
                fcolor = "white" if _is_dark(fill) else "#2C3E50"

                if avg_perf is not None:
                    lbl = f"{act}\n{freq:,}회 | {_fmt_dur(avg_perf)}"
                else:
                    lbl = f"{act}\n{freq:,}회"

                dot.node(
                    act,
                    label=lbl,
                    shape="box",
                    style="filled,rounded",
                    fillcolor=fill,
                    fontcolor=fcolor,
                    fontsize="10",
                    margin="0.15,0.1",
                )

            # ── Start → 시작 활동 ───────────────────────────────────────────
            for act, cnt in start_activities.items():
                dot.edge(
                    "__start__", act,
                    label=str(cnt),
                    penwidth="1.5",
                    color="#27AE60",
                    fontsize="9",
                    fontcolor="#27AE60",
                )

            # ── 종료 활동 → End ─────────────────────────────────────────────
            for act, cnt in end_activities.items():
                dot.edge(
                    act, "__end__",
                    label=str(cnt),
                    penwidth="1.5",
                    color="#E74C3C",
                    fontsize="9",
                    fontcolor="#E74C3C",
                )

            # ── DFG 아크 ────────────────────────────────────────────────────
            for (src, tgt), freq in dfg.items():
                perf = performance_dfg.get((src, tgt))

                # 엣지 두께 (1 ~ 6 px)
                if max_freq > min_freq:
                    nf = (freq - min_freq) / (max_freq - min_freq)
                else:
                    nf = 0.5
                penwidth = 1.0 + nf * 5.0

                # 엣지 색상 (성능 기반)
                if perf is not None and max_perf > min_perf:
                    np_ = (perf - min_perf) / (max_perf - min_perf)
                    ecolor = _perf_color(np_)
                elif perf is not None:
                    ecolor = _perf_color(0.5)
                else:
                    ecolor = "#95A5A6"

                # 레이블 (빈도 + 성능)
                if perf is not None:
                    lbl = f"{freq:,}\n{_fmt_dur(perf)}"
                else:
                    lbl = f"{freq:,}"

                dot.edge(
                    src, tgt,
                    label=lbl,
                    penwidth=f"{penwidth:.1f}",
                    color=ecolor,
                    fontsize="9",
                    fontcolor="#555555",
                )

            svg = _model_to_svg(dot)
            return _wrap_svg(svg, height=height)

        except Exception as e:
            return self._error_html(str(e), height)

    def render_petri_net(
        self,
        net: Any,
        im: Any,
        fm: Any,
        height: int = 620,
    ) -> str:
        """Petri Net을 HTML로 렌더링합니다."""
        from pm4py.visualization.petri_net import visualizer as pn_vis

        try:
            gviz = pn_vis.apply(net, im, fm)
            svg = _model_to_svg(gviz)
            return _wrap_svg(svg, height=height)
        except Exception as e:
            return self._error_html(str(e), height)

    def render_bpmn(
        self,
        bpmn_model: Any,
        height: int = 620,
    ) -> str:
        """BPMN 다이어그램을 HTML로 렌더링합니다."""
        from pm4py.visualization.bpmn import visualizer as bpmn_vis

        try:
            gviz = bpmn_vis.apply(bpmn_model)
            svg = _model_to_svg(gviz)
            return _wrap_svg(svg, height=height)
        except Exception as e:
            return self._error_html(str(e), height)

    @staticmethod
    def _error_html(message: str, height: int = 620) -> str:
        """에러 메시지를 HTML로 반환합니다."""
        return f"""
        <div style="height:{height}px;display:flex;align-items:center;
                    justify-content:center;border:1px solid #f5c6cb;
                    border-radius:8px;background:#fff5f5;padding:24px;">
          <div style="text-align:center;color:#721c24;">
            <div style="font-size:32px;margin-bottom:12px;">⚠️</div>
            <div style="font-weight:600;margin-bottom:8px;">시각화 오류</div>
            <div style="font-size:13px;color:#856404;background:#fff3cd;
                        padding:8px 12px;border-radius:4px;max-width:500px;">
              {message}
            </div>
          </div>
        </div>"""
