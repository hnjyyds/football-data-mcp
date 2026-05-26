FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FOOTBALL_DATA_MCP_HOST=0.0.0.0
ENV FOOTBALL_DATA_MCP_PORT=8910

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY football_data_mcp ./football_data_mcp
COPY pyproject.toml ./

EXPOSE 8910

CMD ["python", "-m", "football_data_mcp.server"]
