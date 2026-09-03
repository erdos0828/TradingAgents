# TradingAgents CLI 使用说明

TradingAgents 提供命令行工具 `tradingagents`，用于执行单标的研究分析、启动持仓汇总 Web 服务，以及批量分析整个持仓组合。

## 安装与入口

项目使用 `pyproject.toml` 配置了可执行脚本：

```toml
[project.scripts]
tradingagents = "cli.main:app"
```

安装后会在虚拟环境的 `bin` 目录生成 `tradingagents` 脚本：

```bash
# 开发模式安装（推荐）
pip install -e .

# 验证
which tradingagents
tradingagents --help
```

如果脚本未生成或版本不一致，可强制重新安装：

```bash
pip install -e . --force-reinstall --no-deps
```

> 下文用 `<project-root>` 表示项目根目录，`<venv>` 表示虚拟环境目录（通常为 `<project-root>/.venv`）。部署时请替换为实际路径。

## 命令一览

```
Usage: tradingagents [OPTIONS] COMMAND [ARGS]...

TradingAgents CLI: Multi-Agents LLM Financial Trading Framework

Options:
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell.
  --help                Show this message and exit.

Commands:
  analyze              Analyze a single ticker.
  serve                Start the portfolio summary web server.
  analyze-portfolio    Batch analyze all stocks in portfolio holdings.
```

---

## `tradingagents analyze`：单标的研究分析

`analyze` 是核心分析命令。不带参数时会进入交互式向导；带足够参数时可完全非交互运行，适合 cronjob 定时任务。

### 参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--ticker` | `-t` | 标的代码，如 `SPY`、`0700.HK`、`BTC-USD` | 交互式输入 |
| `--date` | `-d` | 分析日期 `YYYY-MM-DD` | 今天 |
| `--asset-type` | `-a` | 资产类型：`stock` 或 `crypto` | 自动检测 |
| `--analysts` | | 分析师组合，逗号分隔：`market,social,news,fundamentals` | 交互式选择 |
| `--auto-save` | | 分析完成后自动保存报告，不弹确认 | `False` |
| `--headless` | | 静默模式，不显示欢迎页/进度 UI/公告 | `False` |
| `--dingtalk` | | 分析完成后发送钉钉通知 | `False` |
| `--checkpoint` / `--no-checkpoint` | | 是否启用断点续跑 | 读取 `TRADINGAGENTS_CHECKPOINT_ENABLED` |
| `--clear-checkpoints` | | 运行前清空所有断点 | `False` |

### 交互式运行

```bash
tradingagents analyze
```

按向导依次输入：标的、日期、输出语言、分析师、研究深度、LLM 提供商、思考模型等。

### 非交互式运行（适合自动化）

```bash
tradingagents analyze \
  --ticker AAPL \
  --date 2026-08-21 \
  --analysts market,news,fundamentals \
  --auto-save \
  --headless
```

启用钉钉通知：

```bash
tradingagents analyze \
  --ticker AAPL \
  --date 2026-08-21 \
  --analysts market,news,fundamentals \
  --auto-save \
  --headless \
  --dingtalk
```

> 如果未将 `<venv>/bin` 加入 `PATH`，请使用 `<venv>/bin/tradingagents` 的绝对路径调用。

> 钉钉通知需要配置 `DINGTALK_WEBHOOK_URL` 和 `DINGTALK_WEBHOOK_SECRET`。

### 输出目录

报告默认保存到：

```
reports/{ticker}/{date}_{time}/
```

例如：

```
reports/AAPL/2026-08-21_095050/
```

同一天的多次分析会按时间戳分目录，不会覆盖。

---

## `tradingagents serve`：启动持仓汇总 Web 服务

启动一个 Flask 服务，动态生成持仓汇总页面，并内嵌个股研究报告浏览器。

### 参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--host` | `-h` | 绑定地址 | `127.0.0.1` |
| `--port` | `-p` | 绑定端口 | `5000` |
| `--holdings` | | 持仓 JSON 文件路径 | `data/portfolio_holdings.json` |
| `--reports-dir` | | 报告根目录 | `reports` |
| `--cache-dir` | | OHLCV 缓存目录 | `cache` |
| `--report-server-url` | | 个股报告链接基地址 | `/reports` |

### 示例

```bash
# 默认端口 5000
tradingagents serve

# 指定端口
tradingagents serve --port 8080

# 自定义持仓文件
tradingagents serve --holdings data/my_holdings.json
```

服务启动后：

- 持仓汇总页面：`http://127.0.0.1:5000/`
- 个股报告浏览器：`http://127.0.0.1:5000/reports`

按 `Ctrl+C` 停止服务。

---

## `tradingagents analyze-portfolio`：批量分析持仓

读取 `data/portfolio_holdings.json`，对其中每只标的依次调用 `tradingagents analyze`。

### 参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--date` | `-d` | 分析日期 `YYYY-MM-DD` | 今天 |
| `--analysts` | `-a` | 分析师组合 | `market,news,fundamentals` |
| `--no-dingtalk` | | 禁用钉钉通知 | `False` |
| `--dry-run` | | 只打印将要执行的命令 | `False` |
| `--holdings` | | 持仓 JSON 文件路径 | `data/portfolio_holdings.json` |
| `--skip` | | 逗号分隔的跳过 ticker 列表 | 无 |
| `--market` | `-m` | 市场筛选：`all`、`a-share`、`us` | `all` |

### 示例

```bash
# 默认批量分析所有持仓
tradingagents analyze-portfolio

# 指定日期并跳过部分标的
tradingagents analyze-portfolio --date 2026-08-21 --skip TSLA,AAPL

# 只预览将要执行的命令
tradingagents analyze-portfolio --dry-run

# 关闭钉钉通知
tradingagents analyze-portfolio --no-dingtalk

# 只分析 A 股
tradingagents analyze-portfolio --market a-share

# 只分析美股
tradingagents analyze-portfolio --market us
```

### 持仓文件格式

`data/portfolio_holdings.json` 示例：

```json
{
  "holdings": [
    {
      "ticker": "AAPL",
      "quantity": 204,
      "cost_price": 228.463
    },
    {
      "ticker": "TSLA",
      "quantity": 196,
      "cost_price": 426.008
    }
  ]
}
```

字段说明：

- `ticker`：标的代码（必填）
- `quantity`：持有数量（必填）
- `cost_price`：成本价（必填）

---

## 环境变量

以下环境变量可通过 `.env` 文件或 shell 设置，CLI 会读取并跳过对应交互步骤：

| 环境变量 | 说明 |
|----------|------|
| `TRADINGAGENTS_LLM_PROVIDER` | LLM 提供商，如 `openai`、`anthropic`、`google` 等 |
| `TRADINGAGENTS_QUICK_THINK_LLM` | 浅层思考模型 |
| `TRADINGAGENTS_DEEP_THINK_LLM` | 深度思考模型 |
| `TRADINGAGENTS_LLM_BACKEND_URL` | 后端 API 地址 |
| `TRADINGAGENTS_MAX_DEBATE_ROUNDS` | 研究辩论轮数 |
| `TRADINGAGENTS_MAX_RISK_ROUNDS` | 风险讨论轮数 |
| `TRADINGAGENTS_OUTPUT_LANGUAGE` | 报告输出语言，如 `zh`、`en` |
| `TRADINGAGENTS_CHECKPOINT_ENABLED` | 是否启用断点续跑 |
| `DINGTALK_WEBHOOK_URL` | 钉钉机器人 Webhook 地址 |
| `DINGTALK_WEBHOOK_SECRET` | 钉钉机器人签名密钥 |
| `TRADINGAGENTS_HOME` | 项目根目录，影响 `reports/`、`cache/` 等路径 |

### 关于 `TRADINGAGENTS_HOME`

CLI 通过 `TRADINGAGENTS_HOME` 解析数据路径；如果未设置，则回退到当前工作目录（`cwd`）。因此：

- 报告保存位置：`${TRADINGAGENTS_HOME}/reports` 或 `${cwd}/reports`
- cache 位置：`${TRADINGAGENTS_HOME}/cache` 或 `${cwd}/cache`

部署到其它机器时，建议显式设置 `TRADINGAGENTS_HOME`，而不是依赖 `cd` 到项目目录：

```bash
export TRADINGAGENTS_HOME=/path/to/TradingAgents
tradingagents analyze --ticker AAPL --auto-save --headless
```

---

## cronjob 定时任务示例

每天收盘后自动批量分析持仓并发送钉钉通知：

```cron
# 每天 16:30 运行
30 16 * * 1-5 \
  TRADINGAGENTS_HOME=<project-root> <venv>/bin/tradingagents \
  analyze-portfolio --auto-save --headless --date $(date +\%Y-\%m-\%d) >> \
  <log-dir>/analyze-portfolio.log 2>&1
```

> 注意：cron 中 `%` 需要转义为 `\%`。

如果只分析单标的：

```cron
0 9 * * 1-5 \
  TRADINGAGENTS_HOME=<project-root> <venv>/bin/tradingagents \
  analyze --ticker SPY --date $(date +\%Y-\%m-\%d) \
  --analysts market,news --auto-save --headless >> \
  <log-dir>/spy.log 2>&1
```

部署时请替换：
- `<project-root>`：项目所在目录
- `<venv>`：虚拟环境目录（如 `<project-root>/.venv`）
- `<log-dir>`：日志输出目录，按实际部署环境填写（如 `/var/log/tradingagents`）

---

## 常见问题

### `tradingagents --help` 和 `python -m cli.main --help` 显示不一致

通常是因为 `pip install .` 普通安装后，`site-packages` 中残留了旧版 `cli` 包。解决：

```bash
<venv>/bin/pip install -e . --force-reinstall --no-deps
```

或在已激活虚拟环境时直接：

```bash
pip install -e . --force-reinstall --no-deps
```

### 交互式提示仍然出现

检查是否提供了所有必要参数。`analyze` 命令非交互运行至少需要：

- `--ticker`
- `--date`
- `--analysts`
- `--auto-save`
- `--headless`

同时建议设置环境变量：

- `TRADINGAGENTS_LLM_PROVIDER`
- `TRADINGAGENTS_QUICK_THINK_LLM`
- `TRADINGAGENTS_DEEP_THINK_LLM`
