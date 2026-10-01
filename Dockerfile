# ==============================================================================
# Base Stage — Python 3.10 Slim
# ==============================================================================
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# Set working directory inside container
WORKDIR /app

# Install system dependencies required for compilation, git, and scipy/scikit-learn C-libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libgomp1 \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependency files
COPY requirements.txt setup.py ./

# Install python dependencies and hackdata package
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    pip install -e .

# Copy application source code and bundled assets
COPY app.py ./
COPY hackdata/ ./hackdata/
COPY api/ ./api/
COPY frontend/ ./frontend/
COPY data_assets/ ./data_assets/
COPY data_schema/ ./data_schema/
COPY scripts/ ./scripts/

# Create runtime directories required by paths.py (Artifacts, logs, cache)
RUN mkdir -p Artifacts/temp Artifacts/saved logs cache

# Create a non-root user for security best practices
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose server port
EXPOSE 8000

# Container healthcheck using FastAPI GET /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Uvicorn server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
