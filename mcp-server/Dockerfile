FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY leave_mcp ./leave_mcp

ENV PORT=8080
EXPOSE 8080

# Streamable HTTP MCP server. All data is SIMULATED.
CMD ["python", "-m", "uvicorn", "leave_mcp.server:app", "--host", "0.0.0.0", "--port", "8080"]
