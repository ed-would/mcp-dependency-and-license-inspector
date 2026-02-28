# Dependency & License Inspector MCP — production image.
# Target: ≤ 500 MB. Run with --memory=2048m --cpus=2 when needed.
# Multi-stage: only runtime deps in final image; no dev deps, no tests.

# -----------------------------------------------------------------------------
# Builder: install runtime deps and package (no pytest, no dev tools)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
COPY setup.py ./
COPY src ./src

# Install runtime deps and package into /install; no cache in layer
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --target /install -r requirements.txt \
    && pip install --no-cache-dir --no-deps --target /install . \
    && rm -rf /root/.cache/pip

# -----------------------------------------------------------------------------
# Runtime: minimal image, no pip (no cache), no dev dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* /root/.cache

WORKDIR /app

COPY --from=builder /install /usr/local
COPY demo_project /app/demo_project

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/usr/local
ENV DEMO_MODE=false

EXPOSE 8000

ENTRYPOINT ["python", "-m", "mcp_dependency_inspector.entrypoint"]
CMD ["serve"]
