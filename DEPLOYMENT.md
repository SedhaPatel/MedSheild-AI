# MedShield-AI Deployment Architecture Guide

This guide explains **where and how to deploy the MedShield-AI backend and frontend** based strictly on the repository's actual runtime stack, memory footprint, stateful security architecture, and pre-configured deployment manifests.

---

## 1. Observed Tech Stack & Runtime Footprint

### Backend (`medshield/`)
- **Web & ASGI Runtime:** Python 3.11+ (`requires-python >= 3.10`, Docker `python:3.11-slim`), `FastAPI` (`>=0.110.0`), `Uvicorn` (`uvicorn[standard]>=0.28.0`), `python-multipart`, `Pydantic` (`>=2.5.0`) / `pydantic-settings`.
- **Deep Learning & Explainability:** CPU `PyTorch` (`>=2.0.0`), `TorchVision` (`>=0.15.0`), `TorchXRayVision` (`>=1.2.0` — pre-trained `DenseNet-121` `densenet121-res224-all` + `EfficientNet-V2-S` fallback), thread-safe `GradCAM` backward-hook heatmap generation.
- **Pixel PHI Redaction & Vision:** `EasyOCR` (`>=1.7.0`), `OpenCV` (`opencv-python-headless>=4.8.0`), `NumPy`, `SciPy`, `Pillow` (requiring OS libs `libgl1`, `libglib2.0-0`, `libgomp1` in Linux containers).
- **Medical Imaging & Cryptography:** `pydicom` (`>=2.4.0`), `cryptography` (`>=42.0.0`, `AES-256-GCM` `MEDENC01` envelope encryption, `LocalKMSProvider`).
- **Zero-PII Scan Chat Assistant:** `httpx` (`>=0.24.0`) calling Gemini (`gemini-2.5-flash`) or MedGemma (`google/medgemma-1.5-4b-it`), with a deterministic `grounded-local-fallback` synthesizer when API keys are omitted.

### Frontend (`frontend/`)
- **SPA Core:** `React 19` (`^19.3.1`), `TypeScript` (`~7.0.2`), `Vite` (`^8.3.6`), `React Router DOM` (`^7.18.5`), `Zustand` (`^5.1.0`).
- **Medical PACS Viewer:** `Cornerstone3D` (`@cornerstonejs/core`, `@cornerstonejs/tools`, `@cornerstonejs/dicom-image-loader` `^5.17.1`), `dicom-parser`, and WebAssembly transfer-syntax codecs (`codec-openjph`, `codec-openjpeg`, `codec-libjpeg-turbo-8bit`, `codec-charls`, `codec-libjxl`).
- **UI & Styling:** `Tailwind CSS v4` (`@tailwindcss/vite`, `tailwindcss` `^4.3.5`), `Radix UI` primitives (`alert-dialog`, `dialog`, `select`, `slider`, `tabs`, `tooltip`), `lucide-react`, `sonner`.

---

## 2. Deployment Architecture Decision: Split vs. Unified

| Deployment Pattern | Backend Host | Frontend Host | Best For |
| :--- | :--- | :--- | :--- |
| **Option A: Recommended Split Deployment** | Docker PaaS / VM with >= 2–4 GB RAM & persistent disk (**Railway**, **Render**, **Fly.io**, **Cloud Run `min-instances=1`**) | Global Static CDN (**Netlify**, **Vercel**, **Cloudflare Pages**) | Production demos & public web portals: instant global CDN delivery for Cornerstone3D WASM assets + isolated heavy ML container |
| **Option B: Unified Single-Container** | Single Docker container running [`Dockerfile`](Dockerfile) (`MEDSHIELD_SERVE_FRONTEND=true`) | Served directly by FastAPI from `/app/frontend/dist` | Simple single-URL deployments, private hospital intranet VMs, zero-CORS same-origin setups |

### Why Serverless Functions Are NOT Viable for the Backend
Do **not** deploy the FastAPI backend to **Vercel Serverless Functions**, **AWS Lambda (standard zip)**, or **Cloudflare Workers**:
1. **Bundle Size & Native Runtime Limits:** CPU `torch` + `torchvision` + `torchxrayvision` + `opencv-python-headless` + `easyocr` + `scipy` + Linux shared libraries (`libgl1`, `libglib2.0-0`, `libgomp1`) far exceed typical serverless deployment limits (e.g., 250 MB unzipped limits on Vercel/Lambda), and Cloudflare Workers V8 isolates cannot execute Python PyTorch/OpenCV C-extensions.
2. **Memory & Cold-Start Timeouts:** Initializing PyTorch, loading the `DenseNet-121` checkpoint (`~28 MB` `.pt`), running EasyOCR, and executing `GradCAM` gradient backward passes requires **2 GB RAM minimum (4 GB recommended)** and exceeds short serverless request/cold-start timeouts.
3. **Stateful Process & Disk Persistence:** `LocalKMSProvider` holds KEKs and DPDP Sec. 12 revocation state in process RAM, `medshield/api/routes/dashboard.py` holds `_dashboard_worklist` and `_dashboard_session_cache` in memory, and `EncryptedStore` writes atomic `.enc` files to disk. Ephemeral serverless workers would discard keys, worklists, and studies between invocations.

---

## 3. Option A: Recommended Split Deployment

### Step 1 — Deploy the Backend (Docker PaaS / VM)

The repository ships a two-stage [`Dockerfile`](Dockerfile) (`python:3.11-slim` + CPU-only PyTorch wheels from `https://download.pytorch.org/whl/cpu` + `requirements-prod.txt` + `medshield/` + `test_samples/`) along with platform manifests:

- **Railway ([`railway.toml`](railway.toml)):**
  - Uses `builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"`, and `healthcheckPath = "/health"` (`healthcheckTimeout = 180`).
  - Select a service tier with at least **2–4 GB RAM**.
  - Attach a Railway Volume at `/app/storage/encrypted_studies` (and optionally `/app/weights` to cache downloaded model weights across deploys).
- **Render ([`render.yaml`](render.yaml)):**
  - Pre-configured for `runtime: docker`, `plan: standard` (>= 2 GB RAM), `healthCheckPath: /health`, auto-generated `MEDSHIELD_SECRET_PEPPER`, and a 5 GB persistent disk mounted at `/app/storage/encrypted_studies`.
- **Fly.io / Cloud Run (`min-instances=1`) / Self-Hosted VM:**
  - Build from [`Dockerfile`](Dockerfile), expose `$PORT` (default `8000`), probe `GET /health`, allocate **>= 2–4 GB RAM**, and set `min-instances=1` (keep-warm stateful process; note Cloud Run containers have ephemeral local storage across restarts unless backed by a mounted volume/GCS FUSE).

Set these backend environment variables for split deployment (see [`.env.example`](.env.example)):
```ini
MEDSHIELD_ENVIRONMENT=production
MEDSHIELD_SECRET_PEPPER=<unique-32plus-char-random-secret>
MEDSHIELD_STORAGE_PATH=/app/storage/encrypted_studies
MEDSHIELD_REQUIRE_MTLS=false
MEDSHIELD_SERVE_FRONTEND=false
MEDSHIELD_CORS_ORIGINS=https://your-frontend-domain.netlify.app
```

### Step 2 — Deploy the Frontend (Static CDN SPA)

The frontend builds into static HTML/JS/CSS/WASM assets (`frontend/dist`) and routes all API + Cornerstone `wadouri:` DICOM traffic via [`frontend/src/lib/api.ts`](frontend/src/lib/api.ts) (`getApiBaseUrl()`, `resolveApiUrl()`, `resolveAbsoluteApiUrl()`) and [`CornerstoneViewport.tsx`](frontend/src/components/viewer/CornerstoneViewport.tsx):

- **Netlify ([`frontend/netlify.toml`](frontend/netlify.toml)):**
  - Configure **Base directory = `frontend`** in the Netlify UI; `frontend/netlify.toml` sets `command = "npm run build"`, `publish = "dist"`, SPA rewrite `/* -> /index.html` (`status = 200`), immutable caching for `/assets/*`, `no-cache` for `/index.html`, and browser security headers.
- **Vercel ([`frontend/vercel.json`](frontend/vercel.json)):**
  - Set the Vercel project **Root Directory** to `frontend`.
  - Uses `"framework": "vite"`, `"buildCommand": "npm run build"`, `"outputDirectory": "dist"`, rewrite `/(.*) -> /index.html`, immutable `/assets/(.*)` cache headers, and security headers.
- **Cloudflare Pages:**
  - Root directory: `frontend`
  - Build command: `npm run build`
  - Output directory: `dist`

Set this frontend build-time environment variable (see [`frontend/.env.example`](frontend/.env.example)):
```ini
VITE_API_BASE_URL=https://your-backend-service.up.railway.app
```
> **Important:** Because Vite bakes `VITE_API_BASE_URL` into the bundle during `npm run build`, update `VITE_API_BASE_URL` and trigger a frontend rebuild if the backend URL changes. Then ensure the exact frontend origin (scheme + host, no trailing slash) is listed in backend `MEDSHIELD_CORS_ORIGINS`.

---

## 4. Option B: Unified Single-Container Deployment

The [`Dockerfile`](Dockerfile) includes a `node:22-slim` builder stage that compiles `frontend/` into `/app/frontend/dist` inside the Python runtime image with `VITE_API_BASE_URL` unset (relative `/api/*` paths).

To serve the React + Cornerstone3D SPA directly from FastAPI on port `8000` (or `$PORT`):
```ini
MEDSHIELD_ENVIRONMENT=production
MEDSHIELD_SECRET_PEPPER=<unique-32plus-char-random-secret>
MEDSHIELD_SERVE_FRONTEND=true
MEDSHIELD_FRONTEND_DIST_DIR=/app/frontend/dist
MEDSHIELD_REQUIRE_MTLS=false
MEDSHIELD_STORAGE_PATH=/app/storage/encrypted_studies
```

### Routing Behavior (`medshield/api/app.py`)
- When `MEDSHIELD_SERVE_FRONTEND=true` and `/app/frontend/dist/index.html` exists:
  - `/assets/*` serves static Vite bundle chunks & Cornerstone3D WASM decoders.
  - `/`, `/worklist`, `/workstation`, `/security` serve `index.html` for client-side React Router navigation.
  - `/api/*`, `/health`, `/docs`, `/openapi.json`, and `/dashboard` continue to route to FastAPI (unknown `/api/*` paths return JSON `404`).
- When `MEDSHIELD_SERVE_FRONTEND=false` (default):
  - `GET /` redirects to FastAPI's built-in `/dashboard` HTML console (`medshield/api/routes/dashboard.py`), keeping API routes ready for a separate static CDN frontend.

---

## 5. Production Security, Storage & Runtime Constraints

### 1. `--workers 1` Requirement
The container entrypoint intentionally runs:
```bash
uvicorn medshield.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
```
Do **not** scale `--workers > 1` without first externalizing state. Currently:
- `LocalKMSProvider` (`_dashboard_kms` in [`dashboard.py`](medshield/api/routes/dashboard.py) and `_shared_kms` in [`studies.py`](medshield/api/routes/studies.py)) holds Master KEKs and key revocation status in process memory.
- `_dashboard_worklist` and `_dashboard_session_cache` live in process memory.
- Multiple workers would isolate KEK dictionaries per worker process (causing decryption failures / HTTP 410 across requests) and multiply PyTorch + EasyOCR RAM usage.

### 2. Production `MEDSHIELD_SECRET_PEPPER` Guard
In [`medshield/config.py`](medshield/config.py), `Settings.model_post_init()` enforces a non-default salt whenever `MEDSHIELD_ENVIRONMENT=production`:
- If `MEDSHIELD_SECRET_PEPPER` is empty or left at the default `MedShieldDefaultMasterSalt2026-StrictSec!`, startup raises `ValueError`.
- Generate a unique >= 32-character secret before deploying (e.g., `openssl rand -hex 32`), or rely on `generateValue: true` in [`render.yaml`](render.yaml).

### 3. `MEDSHIELD_REQUIRE_MTLS` Behavior (Public Demo vs. Edge Gateway)
In [`medshield/api/middleware/mtls_auth.py`](medshield/api/middleware/mtls_auth.py):
- `MEDSHIELD_REQUIRE_MTLS` defaults to `true` in `Settings`.
- **Always exempt:** `/health`, `/docs`, `/openapi.json`, `/`, `/dashboard`, `/api/chat`, and `/api/v1/dashboard/*`.
- **Unified SPA routes (`MEDSHIELD_SERVE_FRONTEND=true`):** Non-`/api/*` `GET`/`HEAD` requests (such as `/assets/*`, `/workstation`, `/worklist`, `/security`, `/favicon.svg`) bypass the mTLS header check automatically so the SPA loads in browsers even when `MEDSHIELD_REQUIRE_MTLS=true`.
- **Protected clinical B2B routes when `true`:** `/api/v1/studies`, `/api/v1/inference/*`, and `/api/v1/heatmaps/*` enforce `X-Client-Cert-SHA256` matching `allowed_client_cert_fingerprints` (returning HTTP 401 when missing or unauthorized).
- **Recommendation:**
  - Set `MEDSHIELD_REQUIRE_MTLS=false` for public browser demos or open API testing without an mTLS gateway.
  - Set `MEDSHIELD_REQUIRE_MTLS=true` when deployed behind an mTLS-terminating edge proxy (Envoy / AWS ALB / NGINX) forwarding `X-Client-Cert-SHA256` for clinical STOW-RS / inference ingestion (this also works seamlessly alongside unified SPA hosting when `MEDSHIELD_SERVE_FRONTEND=true`).

### 4. Encrypted Storage & Model Weights Volumes
- **Encrypted Studies (`/app/storage/encrypted_studies`):** `Dockerfile` creates `/app/storage/encrypted_studies` owned by non-root user `medshield` (`uid 10001`). Mount a persistent disk here in production. Note that because `LocalKMSProvider` keeps KEKs in RAM, restarting the container clears in-memory KEKs even if `.enc` files remain on disk (a real HSM/Cloud KMS implementation of `KMSProvider` is required for cross-restart study decryption).
- **Model Weights Cache (`/app/weights`):** [`.dockerignore`](.dockerignore) excludes local `weights/` from the image build context. `Dockerfile` sets `TORCH_HOME=/app/weights` and `EASYOCR_MODULE_PATH=/app/weights` with writable permissions. On first model load, `TorchXRayVisionClassifier` checks `/app/weights` for `nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt` and downloads `densenet121-res224-all` if absent (falling back to uninitialized DenseNet / `EfficientNet-V2-S` if offline). Mount a volume at `/app/weights` to avoid re-downloading weights on container replacement.
- **Built-in Demo Cases:** `test_samples/` is copied into `/app/test_samples/` so the 3 pre-packaged chest radiographs (`patient_01_pneumonia`, `patient_02_effusion`, `patient_03_cardiomegaly`) work out of the box.

---

## 6. Environment Variable Reference

### Backend Variables ([`.env.example`](.env.example))

| Variable | Default | Required in Prod | Purpose |
| :--- | :--- | :--- | :--- |
| `MEDSHIELD_ENVIRONMENT` | `development` | Yes (`production`) | Enables production security guards |
| `MEDSHIELD_SECRET_PEPPER` | Dev placeholder | **Yes (unique >=32 chars)** | HMAC-SHA256 salt for DICOM UID pseudonymization (`2.25.*`) & date shifting |
| `MEDSHIELD_CORS_ORIGINS` | Local Vite + FastAPI origins | Yes (for split deploy) | Comma-separated or JSON list of allowed frontend origins |
| `MEDSHIELD_REQUIRE_MTLS` | `true` (`false` in `.env.example`) | Set explicitly | Enforces `X-Client-Cert-SHA256` on `/api/v1/studies`, `/api/v1/inference/*`, etc. |
| `MEDSHIELD_STORAGE_PATH` | `./storage/encrypted_studies` (`/app/storage/encrypted_studies` in Docker) | Recommended | Directory for AES-256-GCM `MEDENC01` `.enc` study files |
| `MEDSHIELD_SERVE_FRONTEND` | `false` | Set `true` only for unified container | Serves built Vite SPA (`frontend/dist`) from FastAPI |
| `MEDSHIELD_FRONTEND_DIST_DIR` | `./frontend/dist` (`/app/frontend/dist` in Docker) | Only when unified | Path to built Vite production bundle |
| `MEDSHIELD_KMS_MASTER_KEY_ID` | `arn:medshield:kms:local:key/master-kek-v1` | Optional | Base Master KEK identifier |
| `MEDSHIELD_MODEL_ARCHITECTURE` | `efficientnet_v2_s` | Optional | Fallback backbone setting (`torchxrayvision` DenseNet-121 loads when weights/package available) |
| `MEDSHIELD_MODEL_CHECKPOINT_PATH` | `None` | Optional | Explicit path to custom `.pt` weights |
| `MEDSHIELD_CHAT_PROVIDER` | `gemini` | Optional | `gemini` or `medgemma` (`huggingface`) |
| `GEMINI_API_KEY` | `None` | Optional | Enables Gemini multimodal Scan Chat (falls back offline if blank) |
| `MEDSHIELD_GEMINI_MODEL` | `gemini-2.5-flash` | Optional | Gemini model ID |
| `HF_API_TOKEN` | `None` | Optional | Enables Hugging Face Router MedGemma multimodal Scan Chat |
| `MEDSHIELD_MEDGEMMA_MODEL` | `google/medgemma-1.5-4b-it` | Optional | MedGemma model ID |
| `MEDSHIELD_CHAT_TIMEOUT_SEC` | `25.0` | Optional | Upstream VLM request timeout (seconds) |
| `PORT` | `8000` | Set by PaaS | HTTP port bound by Uvicorn |

### Frontend Variables ([`frontend/.env.example`](frontend/.env.example))

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `""` (empty) | Build-time public backend origin for split CDN hosting (e.g., `https://medshield-api.up.railway.app`). Keep empty for Vite dev proxy and unified container builds. |
| `VITE_API_PROXY_TARGET` | `http://127.0.0.1:8000` | Dev-only Vite `/api` proxy target (`vite.config.ts`); ignored during production `vite build`. |

---

## 7. Local Docker Verification

Build and test the unified container locally before pushing to Railway/Render:

```bash
# 1. Build multi-stage image (frontend Vite build + CPU PyTorch runtime)
docker build -t medshield-ai:local .

# 2. Run in Unified Single-Container Mode (React PACS Portal + FastAPI at http://localhost:8000)
docker run --rm -p 8000:8000 \
  -e MEDSHIELD_ENVIRONMENT=production \
  -e MEDSHIELD_SECRET_PEPPER="$(openssl rand -hex 32)" \
  -e MEDSHIELD_REQUIRE_MTLS=false \
  -e MEDSHIELD_SERVE_FRONTEND=true \
  -v medshield_storage:/app/storage/encrypted_studies \
  -v medshield_weights:/app/weights \
  medshield-ai:local

# 3. Verify health check
curl http://localhost:8000/health
```

To test Split-API mode locally (serving only the API + `/dashboard` while pointing an external CDN/preview build at `http://localhost:8000`), set `-e MEDSHIELD_SERVE_FRONTEND=false` and `-e MEDSHIELD_CORS_ORIGINS=http://localhost:4173`.
