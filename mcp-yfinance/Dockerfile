FROM python:3.12-slim

WORKDIR /app

# Install build tools in case pandas/numpy need compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

EXPOSE 8080

CMD ["python", "-m", "mcp_yfinance.server", "--host", "0.0.0.0", "--port", "8080"]
