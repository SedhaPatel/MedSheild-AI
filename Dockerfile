# Single-container image: FastAPI backend + built React UI on one port.
# Defaults to production mode, so MEDSHIELD_SECRET_PEPPER and MEDSHIELD_JWT_SECRET_KEY must be set
# (the app refuses to start with development secrets). See DEPLOYMENT.md.

# Stage 1: Build the React/Vite/Cornerstone3D UI
FROM node:22-slim AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python 3.11-slim CPU-PyTorch Runtime
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    HOME=/home/medshield \
    TORCH_HOME=/app/weights \
    MEDSHIELD_ENVIRONMENT=production \
    MEDSHIELD_SERVE_FRONTEND=true \
    MEDSHIELD_REQUIRE_MTLS=false \
    MEDSHIELD_STORAGE_PATH=/app/storage/encrypted_studies \
    MEDSHIELD_FRONTEND_DIST_DIR=/app/frontend/dist

WORKDIR /app

# Install OS libraries required by OpenCV and CPU PyTorch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch & TorchVision before other dependencies to avoid multi-GB CUDA wheels
COPY requirements-prod.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision && \
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-prod.txt

# Copy backend application, pre-packaged clinical DICOM/PNG test samples, and built SPA dist
COPY medshield/ ./medshield/
COPY test_samples/ ./test_samples/
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Install medshield-ai package without re-resolving pinned/CPU dependencies
RUN pip install --no-cache-dir --no-deps .

# Bake the pre-trained DenseNet-121 weights (~28 MB) into the image: no download on every cold
# start, and the build fails here if the model cannot load. Dev settings are fine for this step.
RUN MEDSHIELD_ENVIRONMENT=development python -c "\
from medshield.ml.model import TorchXRayVisionClassifier as M; \
m = M(); assert m.is_real_weights, 'pre-trained weights failed to load'; print('model weights ready')"

# Non-root user with UID 1000 (required by Hugging Face Spaces; harmless elsewhere)
RUN groupadd --gid 1000 medshield && \
    useradd --uid 1000 --gid medshield --create-home --shell /bin/bash medshield && \
    mkdir -p /app/storage/encrypted_studies /app/weights && \
    chown -R medshield:medshield /app /home/medshield && \
    chmod -R 775 /app/storage /app/weights

USER medshield

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=5).read()" || exit 1

# Single worker required because worklist, session cache, and LocalKMSProvider keys are stored in memory
CMD ["sh", "-c", "exec uvicorn medshield.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
