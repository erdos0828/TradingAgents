# 智投工作台 Dashboard TODO

> 新 Dashboard 页面路径：`/dashboard`  
> 当前分支：`ui-redesign`  
> 规则：本页面开发期间不新增/修改后端接口，缺失数据先用示例数据填充。

## 已使用真实接口

| 区块 | 已用接口 | 说明 |
|------|----------|------|
| 持仓全局看板 | `GET /api/dashboard/portfolio` | 由 `data/portfolio_holdings.json` + SQLite OHLCV 缓存计算：总市值、当日盈亏/涨跌幅、个股价与涨跌、持仓权重（`portfolio_summary_server._build_dashboard_portfolio`）。前端在 `dashboard/context.jsx` 中 fetch，失败时回退示例数据。 |
| 个股速览与决策舱 / K 线图 | `GET /tv/config` `/tv/time` `/tv/symbols` `/tv/history` `/tv/marks`（UDF 协议）+ `/tv_lib/<path>` 静态资源 | 图表引擎已替换为 TradingView **charting_library 完整版**（与 chanlun-pro 同款，v31，静态库拷贝于 `cli/static/tv/`），前端 `StockDetailPanel` 用 `TradingView.widget` + `UDFCompatibleDatafeed('/tv')` 渲染：主图/副图 pane 分离（可拖拽、有间距）、内置指标库（MA/BOLL/MACD/KDJ/RSI 等）、画图工具、crosshair data window，蜡烛颜色 overrides 为中国惯例红涨绿跌，深色主题、中文、Asia/Shanghai 时区。K 线由 UDF 后端从 SQLite OHLCV 缓存返回（`_tv_history`，W/M 由 pandas resample 聚合，时间戳 UTC 零点秒）；买卖点经 `/tv/marks`（B/S 标记 + 悬停 tooltip）；成本线用 `chart.createShape(horizontal_line)` 橙色虚线（随 symbol 切换重画）；切持仓用 `widget.setSymbol()`。顶部持仓指标条（市值/现价成本/当日盈亏/持仓盈亏）随选中持仓联动。旧 lightweight-charts 及自制 MA/MACD/KDJ/RSI 计算已移除。注意：`cli/static/tv/`（约 26MB）为闭源免费授权库资源，随 git 提交以便部署同步。 |
| 近 15 个交易日静态回测快照 | `GET /api/dashboard/matrix?date=YYYY-MM-DD` | 复用汇总页逻辑：`_get_recent_signals`（PM 五档评级 Buy/Overweight/Hold/Underweight/Sell）+ `_get_signal_outcomes`（T+1/+2/+3/+7/至今日涨跌与累计）。窗口自动过滤周六/周日（15 个自然日 → 11 个工作日列）；`date` 参数指定基准日（默认今天），响应含 `availableDates`（reports 中可用日期）供顶栏日期下拉联动。每个 cell 附 `reportDir`（当日最新报告目录名，`_report_dirs_by_date`），前端点击有报告的结点在新标签页打开 `/reports#ticker=<ticker>&date=<reportDir>` 报告详情页。`PerformanceMatrix` 渲染五档评级方块（B/OW/H/UW/S）+ 底部 3 格实际涨跌色条（红涨绿跌），悬停 tooltip 显示完整涨跌明细，失败回退示例数据。 |
| 情绪分析 / 分析师观点 / 财务摘要 | `GET /api/dashboard/analysis/<ticker>` | 取该股最新报告快照（`_build_dashboard_analysis`）：情绪 = 市场分析师/基本面/新闻/交易员/组合经理五档评级换算 rank（Buy=+2 ~ Sell=-2）平均后映射 0-10 恐惧贪婪分 + 角色徽章；分析师观点 = SQLite `tradingview_ta` 投票（买入/卖出/中性 → 多空占比 + 综合评级）；财务摘要 = fundamentals.md 正则提取 PE(TTM/前向)/市净率/ROE/毛利率（LLM 文本容错提取，缺失显示 —）。前端随选中持仓联动拉取，`BottomCards` 渲染，失败回退示例数据。 |

## 示例数据待替换清单

| 区块 | 当前数据来源 | 建议后续接入接口/数据 | 优先级 |
|------|--------------|----------------------|--------|
| 顶部指数条 | `sampleData.indices` 示例数据 | 上证指数/深证成指/创业板指（A股）；道琼斯/纳斯达克/标普500（美股）。可接入数据源聚合层或外部行情接口。 | 高 |
| 持仓全局看板 | ~~示例数据~~ 已接入 `GET /api/dashboard/portfolio`（见上表） | — | 已完成 |
| 个股速览与决策舱 | ~~示例数据~~ 已接入 `GET /api/dashboard/stock/<ticker>`（见上表） | — | 已完成 |
| K 线图 | ~~`generateSampleCandles()`~~ 已接入真实 OHLCV（见上表） | — | 已完成 |
| 动态信号流 | `sampleData.signals` 示例数据 | 从 `reports/<ticker>/<date>/complete_report.md` 或 PM decision 中提取最新交易信号；也可由分析管线实时生成。 | 中 |
| 情绪分析 | ~~示例数据~~ 已接入 `GET /api/dashboard/analysis/<ticker>`（见上表） | — | 已完成 |
| 分析师观点 | ~~示例数据~~ 已接入 `GET /api/dashboard/analysis/<ticker>`（见上表） | — | 已完成 |
| 财务摘要 | ~~示例数据~~ 已接入 `GET /api/dashboard/analysis/<ticker>`（见上表） | — | 已完成 |
| 买入/卖出按钮 | 仅 UI 展示，无实际操作 | 后续可接入模拟/真实交易接口，或跳转至 `tradingagents analyze` 生成新报告。 | 低 |

## 原报告页面保留内容

- 新 Dashboard 为独立页面，原 `/` 持仓汇总页与 `/reports` 报告详情页保持不变。
- 原报告中有的区块（如分析师详细报告、多空研究、风险辩论、交易执行记录等）当前 Dashboard 未包含，后续按需添加。

## 已接入但尚未使用的真实接口

以下接口已存在于 `portfolio_summary_server.py`，后续可逐步接入 Dashboard：

- `GET /api/reports`：报告目录树
- `GET /api/report/<ticker>/<date_time>/__files__`：某次报告文件列表
- `GET /api/report/<ticker>/<date_time>/<path>`：报告 Markdown 文件内容
- `GET /api/ta/<ticker>/<date>`：TradingView 技术指标缓存
