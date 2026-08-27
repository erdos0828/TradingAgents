# mcp-yfinance

A standalone MCP (Model Context Protocol) server that exposes [yfinance](https://github.com/ranaroussi/yfinance) market data as MCP tools.

## Tools

- `get_stock_price(ticker)` - latest OHLCV + change
- `get_stock_history(ticker, period, interval, start, end)` - historical OHLCV
- `get_stock_info(ticker)` - company/quote metadata
- `get_financials(ticker, statement)` - income / balance / cash statements
- `get_recommendations(ticker)` - recent analyst recommendations
- `search_tickers(query)` - ticker search

## Run locally

```bash
cd mcp-yfinance
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./start.sh 8080
```

The server exposes:

- `GET http://localhost:8080/sse` - SSE stream
- `POST http://localhost:8080/messages/` - JSON-RPC messages
- `GET http://localhost:8080/` - health / info page

## Run with Docker

```bash
cd mcp-yfinance
docker build -t mcp-yfinance .
docker run -p 8080:8080 mcp-yfinance
```

## Deploy to ECS

1. Copy the `mcp-yfinance/` folder to the ECS instance.
2. Install dependencies and start with `nohup` / `systemd` / `docker`:

```bash
cd /path/to/mcp-yfinance
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
nohup ./start.sh 8080 > mcp-yfinance.log 2>&1 &
```

3. Configure the ECS security group to allow inbound TCP traffic on the chosen port.

## Connect as an MCP client

Use the HTTP/SSE transport with endpoint `http://<ecs-ip>:8080/sse`.
