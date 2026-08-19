"""Streamlit Web UI for TradingAgents.

Run with:
    streamlit run streamlit_app.py

The page has:
- A sidebar with analysis inputs (ticker, date, analysts, language).
- A main area with a "Start Analysis" button.
- Real-time progress (agent completion + last message) and a final
  Markdown report broken down by section.

This UI is deliberately thin: it delegates all orchestration to
``TradingAgentsGraph.propagate()`` and only renders the final state.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path

import streamlit as st

# Ensure the repo root is importable even when launched as
# `streamlit run streamlit_app.py` from elsewhere.
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402
from tradingagents.reporting import write_report_tree  # noqa: E402


# --------------------------------------------------------------------------- #
# Page setup                                                                  #
# --------------------------------------------------------------------------- #

st.set_page_config(
    page_title="TradingAgents Web",
    page_icon="📈",
    layout="wide",
)

st.title("📈 TradingAgents")
st.caption("Multi-Agent LLM 金融交易研究框架 · Web UI")


# --------------------------------------------------------------------------- #
# Sidebar inputs                                                              #
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.header("输入")

    ticker = st.text_input(
        "股票代码",
        value="AAPL",
        help="Yahoo Finance 代码：AAPL、600519.SS（上交所）、000404.SZ（深交所）、0700.HK、BTC-USD",
    )

    trade_date = st.date_input(
        "分析日期",
        value=_dt.date.today(),
    )

    asset_type = st.selectbox(
        "资产类型",
        options=["stock", "crypto"],
        index=0,
    )

    st.divider()
    st.subheader("分析师团队")
    selected_analysts = st.multiselect(
        "选择参与的分析师",
        options=["market", "social", "news", "fundamentals"],
        default=["market", "social", "news", "fundamentals"],
        help="至少选一个；市场分析师是基础配置。",
    )

    st.divider()
    st.subheader("流式输出")
    detail_level = st.radio(
        "详细程度",
        options=["简要", "详细", "完整"],
        index=1,
        help="简要=仅节点完成 | 详细=工具调用+参数+结果 | 完整=含 LLM 推理",
        horizontal=True,
    )

    st.divider()
    st.subheader("环境信息")
    st.write(f"**LLM 提供方**: `{DEFAULT_CONFIG.get('llm_provider', '(未设置)')}`")
    st.write(f"**Deep 模型**: `{DEFAULT_CONFIG.get('deep_think_llm', '(未设置)')}`")
    st.write(f"**Quick 模型**: `{DEFAULT_CONFIG.get('quick_think_llm', '(未设置)')}`")
    st.write(f"**输出语言**: `{DEFAULT_CONFIG.get('output_language', '(未设置)')}`")


# --------------------------------------------------------------------------- #
# Main area                                                                   #
# --------------------------------------------------------------------------- #

col1, col2 = st.columns([3, 1])
with col1:
    start = st.button(
        "🚀 开始分析",
        type="primary",
        use_container_width=True,
        disabled=not selected_analysts,
    )

if start:
    if not selected_analysts:
        st.error("请至少选择一名分析师。")
        st.stop()

    ticker_str = (ticker or "").strip()
    if not ticker_str:
        st.error("请输入股票代码。")
        st.stop()

    date_str = trade_date.strftime("%Y-%m-%d")

    try:
        ta = TradingAgentsGraph(
            selected_analysts=tuple(selected_analysts),
            debug=False,
            config=DEFAULT_CONFIG.copy(),
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"初始化失败：{e}")
        st.stop()

    # Build the initial state ourselves so we can use graph.stream() and
    # display each agent as it completes (propagate() hides the stream).
    past_context = ta.memory_log.get_past_context(ticker_str)
    instrument_context = ta.resolve_instrument_context(ticker_str, asset_type)
    init_state = ta.propagator.create_initial_state(
        ticker_str,
        date_str,
        asset_type=asset_type,
        past_context=past_context,
        instrument_context=instrument_context,
    )
    graph_args = ta.propagator.get_graph_args()
    # "updates" yields {node_name: state_delta} per node execution — gives us
    # real node names ("Market Analyst", "tools_market") and only the *new*
    # messages.  The default "values" yields full state snapshots whose keys
    # are field names (messages, company_of_interest…) — useless for progress.
    graph_args["stream_mode"] = "updates"

    # -- helpers to extract tool-call info from LangChain messages --
    import json as _json
    from langchain_core.messages import ToolMessage as _ToolMessage

    def _extract_tool_calls(msgs):
        """Yield (tool_name, args_str) from AI messages with tool_calls."""
        for msg in msgs:
            tcs = getattr(msg, "tool_calls", None)
            if not tcs:
                continue
            for tc in tcs:
                name = tc.get("name", "?")
                try:
                    args_s = _json.dumps(tc.get("args", {}), ensure_ascii=False)
                    if len(args_s) > 500:
                        args_s = args_s[:500] + "…"
                except Exception:
                    args_s = str(tc.get("args", ""))
                yield name, args_s

    def _extract_tool_results(msgs):
        """Yield (tool_name, content_preview) from ToolMessages."""
        for msg in msgs:
            if isinstance(msg, _ToolMessage):
                name = getattr(msg, "name", None) or "tool"
                content = getattr(msg, "content", "")
                if isinstance(content, list):
                    content = " ".join(str(c) for c in content)
                preview = (content or "")[:800]
                if len(content or "") > 800:
                    preview += "…"
                yield name, preview

    def _extract_ai_text(msgs):
        """Yield non-empty AI text (reasoning / summary) without tool_calls."""
        for msg in msgs:
            tcs = getattr(msg, "tool_calls", None)
            content = getattr(msg, "content", "")
            if not tcs and content and isinstance(content, str) and content.strip():
                text = content.strip()
                if len(text) > 600:
                    text = text[:600] + "…"
                yield text

    # -- node display names --
    _NODE_ICONS = {
        "Market Analyst": "📊", "Sentiment Analyst": "💬",
        "News Analyst": "📰", "Fundamentals Analyst": "💼",
        "Bull Researcher": "🐂", "Bear Researcher": "🐻",
        "Research Manager": "👨‍🔬", "Trader": "👨‍💰",
        "Aggressive Analyst": "⚡", "Conservative Analyst": "🛡️",
        "Neutral Analyst": "⚖️", "Portfolio Manager": "👑",
    }

    def _node_label(name: str) -> str:
        if name.startswith("tools_"):
            return f"🔧 {name}"
        if name.startswith("Msg Clear"):
            return f"🧹 {name}"
        icon = _NODE_ICONS.get(name, "")
        return f"{icon} {name}" if icon else name

    progress = st.status(
        f"正在分析 {ticker_str} @ {date_str} …",
        state="running",
        expanded=True,
    )
    final_state: dict = dict(init_state)  # seed with initial state so fields
                                          # like company_of_interest / trade_date
                                          # are present even though no node
                                          # modifies them (updates mode only
                                          # yields node-modified fields).
    last_msg_sig = None  # dedup trailing message across agent→tool→agent loop
    trace_log: list[str] = []  # collect execution trace for the trace tab

    def _trace(line: str) -> None:
        """Write a line both to the live progress area and to trace_log."""
        trace_log.append(line)
        st.write(line)

    try:
        with progress:
            _trace("🚀 开始跑 Agent 图…")
            for chunk in ta.graph.stream(init_state, **graph_args):
                # updates mode: {node_name: state_delta_dict}
                for node_name, node_state in chunk.items():
                    if node_name == "__end__":
                        continue

                    label = _node_label(node_name)
                    is_tool_node = node_name.startswith("tools_")

                    if is_tool_node:
                        _trace(f"  ⚙️ **{label}** 执行中…")
                    else:
                        _trace(f"✅ **{label}**")

                    if not isinstance(node_state, dict):
                        continue
                    msgs = node_state.get("messages", [])
                    if not msgs:
                        continue

                    # Dedup: agent→tool→agent loop repeats trailing message.
                    tail = msgs[-1]
                    sig = (type(tail).__name__, getattr(tail, "content", None))
                    if sig == last_msg_sig:
                        continue
                    last_msg_sig = sig

                    # -- detailed: tool calls (agent) + results (tool node) --
                    if detail_level in ("详细", "完整"):
                        for tool_name, args_s in _extract_tool_calls(msgs):
                            _trace(f"  🔧 `{tool_name}({args_s})`")
                        for tool_name, preview in _extract_tool_results(msgs):
                            _trace(f"  📋 `{tool_name}` → {preview}")

                    # -- full: AI reasoning text --
                    if detail_level == "完整":
                        for text in _extract_ai_text(msgs):
                            _trace(f"  💭 {text}")

                # Merge node deltas into a flat state (mimics MessagesState
                # add_messages reducer for "messages"; last-write-wins for
                # every other field).
                for _nn, _ns in chunk.items():
                    if _nn == "__end__" or not isinstance(_ns, dict):
                        continue
                    for key, val in _ns.items():
                        if key == "messages":
                            existing = final_state.get("messages", [])
                            final_state["messages"] = list(existing) + list(val)
                        else:
                            final_state[key] = val
    except Exception as e:  # noqa: BLE001
        progress.update(label=f"分析失败：{ticker_str}", state="error")
        st.exception(e)
        st.stop()

    progress.update(label=f"分析完成：{ticker_str}", state="complete")

    # Persist to memory log + on-disk state, like propagate() does.
    # propagate() sets self.ticker internally; since we bypassed it for
    # streaming, we must set it manually before _log_state (which uses
    # self.ticker for the output directory path).
    try:
        ta.ticker = ticker_str
        ta.curr_state = final_state
        ta._log_state(date_str, final_state)
        ta.memory_log.store_decision(
            ticker=ticker_str,
            trade_date=date_str,
            final_trade_decision=final_state.get("final_trade_decision", ""),
        )
    except Exception as e:  # noqa: BLE001
        st.warning(f"记忆 / 落盘写入失败：{e}")

    decision = ta.process_signal(
        final_state.get("final_trade_decision", "")
    )

    # ------------------------------------------------------------------ #
    # Render results                                                      #
    # ------------------------------------------------------------------ #

    st.success(f"最终决策：{decision}")

    tabs = st.tabs(
        [
            "📊 市场报告",
            "💬 情绪报告",
            "📰 新闻报告",
            "💼 基本面报告",
            "🧭 投资计划",
            "👨‍💼 交易员计划",
            "📝 最终决策",
            "🔍 执行过程",
        ]
    )

    def _render(md: str | None, empty_hint: str) -> None:
        if md:
            st.markdown(md)
        else:
            st.info(empty_hint)

    with tabs[0]:
        _render(final_state.get("market_report"), "未选择 Market Analyst 或无数据。")
    with tabs[1]:
        _render(final_state.get("sentiment_report"), "未选择 Sentiment Analyst。")
    with tabs[2]:
        _render(final_state.get("news_report"), "未选择 News Analyst。")
    with tabs[3]:
        _render(final_state.get("fundamentals_report"), "未选择 Fundamentals Analyst。")
    with tabs[4]:
        _render(final_state.get("investment_plan"), "（无投资计划）")
    with tabs[5]:
        _render(final_state.get("trader_investment_plan"), "（无交易员计划）")
    with tabs[6]:
        _render(final_state.get("final_trade_decision"), "（无最终决策）")
    with tabs[7]:
        if trace_log:
            for line in trace_log:
                st.markdown(line)
        else:
            st.info("（无执行记录）")

    # Persist the markdown report tree under the project's reports/ dir,
    # matching the CLI's default save location so both interfaces write
    # to the same place.
    timestamp = _dt.datetime.now().strftime("%H%M%S")
    save_path = (
        Path.cwd()
        / "reports"
        / ticker_str
        / f"{date_str}_{timestamp}"
    )
    try:
        report_root = write_report_tree(final_state, ticker_str, save_path)
        st.info(f"Markdown 报告已保存至：`{report_root}`")
    except Exception as e:  # noqa: BLE001
        st.warning(f"报告保存失败：{e}")

    # ------------------------------------------------------------------ #
    # Persist tool-call log (messages history → JSON)                       #
    # ------------------------------------------------------------------ #
    try:
        from langchain_core.messages import (
            AIMessage as _AI,
            HumanMessage as _HM,
            ToolMessage as _TM,
            SystemMessage as _SM,
        )

        def _serialize_msg(msg) -> dict:
            """Convert a LangChain message to a JSON-friendly dict."""
            entry: dict = {"type": type(msg).__name__}
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                entry["content"] = [
                    c if isinstance(c, (str, dict)) else str(c)
                    for c in content
                ]
            else:
                entry["content"] = str(content) if content else ""

            # Tool calls (AIMessage with tool_calls)
            tcs = getattr(msg, "tool_calls", None)
            if tcs:
                entry["tool_calls"] = [
                    {"name": tc.get("name", "?"), "args": tc.get("args", {})}
                    for tc in tcs
                ]

            # Tool result metadata (ToolMessage)
            if isinstance(msg, _TM):
                entry["tool_name"] = getattr(msg, "name", None)
                entry["tool_call_id"] = getattr(msg, "tool_call_id", None)

            # Token usage (AIMessage.usage_metadata)
            usage = getattr(msg, "usage_metadata", None)
            if usage:
                entry["usage"] = dict(usage)

            return entry

        msgs = final_state.get("messages", [])
        if msgs:
            log_entries = [_serialize_msg(m) for m in msgs]
            log_path = save_path / "tool_calls_log.json"
            save_path.mkdir(parents=True, exist_ok=True)
            import json as _json_log
            log_path.write_text(
                _json_log.dumps(log_entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            st.info(f"工具调用日志已保存至：`{log_path}`")
    except Exception as e:  # noqa: BLE001
        st.warning(f"工具调用日志保存失败：{e}")

else:
    st.info(
        "👈 在左侧边栏填好股票代码与日期，然后点击 **开始分析**。\n\n"
        "提示：\n"
        "- 上交所代码用 `.SS`（不是 `.SH`），例如 `600006.SS`。\n"
        "- 深交所用 `.SZ`，港股用 `.HK`，加密货币用 `BTC-USD`。\n"
        "- LLM / 语言 / 研究深度等都在 `.env` 里通过 `TRADINGAGENTS_*` 配置，"
        "本 UI 自动读取。"
    )
