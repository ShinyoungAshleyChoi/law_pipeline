# Application Dockerfile for Blue-Green Deployment
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    mysql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy UV configuration files
COPY deployment/pyproject.toml ./
COPY deployment/uv.lock ./ 2>/dev/null || echo "No uv.lock found, will be created"

# Install Python dependencies with UV
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application source
COPY src/ ./src/
COPY config/ ./config/
COPY deployment/app_entrypoint.sh ./entrypoint.sh

# Make entrypoint executable
RUN chmod +x ./entrypoint.sh

# Create logs directory
RUN mkdir -p /app/logs

# Create non-root user and set permissions
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
ENTRYPOINT ["./entrypoint.sh"]
