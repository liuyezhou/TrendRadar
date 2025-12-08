# Dockerfile.mcp
FROM python:3.12-slim

WORKDIR /TrendRadar

COPY config/ config/
COPY mcp_server/ mcp_server/
COPY vllm_server/agent.py .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "agent.py"]