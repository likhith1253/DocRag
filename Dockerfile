FROM python:3.12.5-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DOCRAG__DEVICE=cpu \
    DOCRAG__EMBEDDING__DEVICE=cpu \
    DOCRAG__QDRANT_PATH=/data/qdrant \
    DOCRAG__REGISTRY_PATH=/data/registry.json \
    DOCRAG__METADATA_STORE_PATH=/data/metadata_store.json \
    DOCRAG__REPOSITORY_DATA_DIR=/data/repositories \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY . .
RUN uv sync --locked --no-dev

EXPOSE 9001
VOLUME ["/data"]
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "9001"]
