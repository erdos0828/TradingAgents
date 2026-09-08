# 智投工作台 Dashboard TODO

> 新 Dashboard 页面路径：`/dashboard`  
> 当前分支：`ui-redesign`  
> 规则：本页面开发期间不新增/修改后端接口，缺失数据先用示例数据填充。

## 已使用真实接口

| 区块 | 已用接口 | 说明 |
|------|----------|------|
| （暂无） | — | 当前所有区块均使用示例数据 |

## 示例数据待替换清单

| 区块 | 当前数据来源 | 建议后续接入接口/数据 | 优先级 |
|------|--------------|----------------------|--------|
| 顶部指数条 | `sampleData.indices` 示例数据 | 上证指数/深证成指/创业板指（A股）；道琼斯/纳斯达克/标普500（美股）。可接入数据源聚合层或外部行情接口。 | 高 |
| 持仓全局看板 | `sampleData.portfolio` + `sampleData.holdings` 示例数据 | `data/portfolio_holdings.json` 持仓文件 + 实时行情（yfinance/Alpha Vantage）计算总市值与盈亏。 | 高 |
| 个股速览与决策舱 | `sampleData.stockDetail` + `sampleData.holdings` 示例数据 | 选中个股的 OHLCV 数据（`sqlite_cache`）+ 当前价/涨跌幅。 | 高 |
| K 线图 | `generateSampleCandles()` 随机示例数据 | 选中个股的 OHLCV 历史数据（`sqlite_cache` / `tradingagents.dataflows.stockstats_utils.load_ohlcv`）。 | 高 |
| 动态信号流 | `sampleData.signals` 示例数据 | 从 `reports/<ticker>/<date>/complete_report.md` 或 PM decision 中提取最新交易信号；也可由分析管线实时生成。 | 中 |
| 情绪分析 | `sampleData.sentiment` 示例数据 | 新闻/社交情绪得分（`get_news`、`get_social` 等）聚合为恐惧/贪婪指数。 | 中 |
| 分析师观点 | `sampleData.analyst` 示例数据 | 综合市场/新闻/基本面分析师的多空投票比例。 | 中 |
| 财务摘要 | `sampleData.financial` 示例数据 | `get_fundamentals` / `get_income_statement` / `get_balance_sheet` 返回的 PE、PB、ROE、毛利率等。 | 中 |
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
