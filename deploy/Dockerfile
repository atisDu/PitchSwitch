# Pitchlist backend: the REST API (and, from B15, the MCP server) in one image.
# Build from the repo root:  docker build -f deploy/Dockerfile -t pitchlist-backend .
# Keys come from the environment at run time (docker run --env-file .env); none are in the image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Same layout as the repo: backend/ next to contracts/ (the install maps contracts in from ../).
COPY contracts ./contracts
COPY backend ./backend
RUN pip install -e ./backend

# Run as a normal user; /app/.cache is the local fallback cache when MONGODB_URI is not set.
RUN useradd --create-home --uid 10001 pitchlist \
    && mkdir -p /app/.cache \
    && chown -R pitchlist /app/.cache
USER pitchlist

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
