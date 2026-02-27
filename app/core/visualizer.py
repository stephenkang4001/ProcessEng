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
