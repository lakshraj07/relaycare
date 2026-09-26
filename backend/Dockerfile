# Unravel API: the ADK agents + FastAPI server, for Cloud Run.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# git is needed at build time to pip-install the Fivetran MCP server (a git
# dependency); the installed console script is then spawned at runtime so the
# live app drives the real MCP without git/uvx at request time.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run sets $PORT (default 8080). uvicorn binds it on all interfaces.
CMD exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}
