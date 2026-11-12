# Local Model Inference Variance & Question-Aware Scan Chat Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` task-by-task. Never run `git push`. Work inside `D:\ISC-Project\.worktrees\fix-local-models` on branch `fix/local-models`.

**Goal:** Eliminate identical outputs across inputs in both local ML pipelines — fixing `TorchXRayVision` `DenseNet-121` normalization (`[-1024, +1024]`) and offline `op_threshs` calibration without double-sigmoid saturation, and making the local `ScanChatService` question-aware, telemetry-grounded, and capable of dispatching to a local Ollama vision-language server.

**Architecture:**
1. **Task 1 (`medshield/ml/{preprocessor,model,explainability,inference_engine}.py`):** Add `mode: Literal["xrv", "imagenet"]` to `DICOMPreprocessor` (mapping radiographs to `[-1024, +1024]` with aspect-preserving square crop/resize when `mode="xrv"`), restore `op_threshs` & `input_resolution` metadata on local offline `weights/*.pt` loads in `TorchXRayVisionClassifier`, prevent double-sigmoid squashing on `op_threshs`-calibrated `DenseNet-121` outputs, expose `forward_logits()` so `GradCAM` backpropagates cleanly without activation saturation, and wire `InferenceEngine` to match each model's expected normalization (`"xrv"` vs `"imagenet"`).
2. **Task 2 (`medshield/config.py`, `medshield/ml/chat_service.py`, `medshield/api/routes/dashboard.py`, `.env.example`):** Upgrade `ScanChatService` to extract zero-PII radiographic pixel statistics and multi-zone Grad-CAM activation distributions, route offline local queries through an intent-, pathology-, localization-, and history-aware grounded responder (`synthesize_offline_grounded_reply`) so distinct prompts never produce identical boilerplate, and add optional local Ollama multimodal chat support (`MEDSHIELD_CHAT_PROVIDER=ollama` / `MEDSHIELD_OLLAMA_BASE_URL` / `MEDSHIELD_OLLAMA_MODEL`) with safe fallback.

**Tech Stack:** Python 3.10+, PyTorch, TorchXRayVision (`densenet121-res224-all`), Pydicom, NumPy, Pillow, FastAPI, `httpx`, Pytest.

---

## Global Constraints

- **Offline Local Model First:** `TorchXRayVisionClassifier` MUST load local `weights/nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt` cleanly without requiring internet access when present, restoring `op_threshs` and `input_resolution` from `xrv.models.model_urls["densenet121-res224-all"]`.
- **Probability Range & Variance:** `InferenceEngine.predict()` outputs MUST remain calibrated in `[0.0, 1.0]` for all 5 `TARGET_PATHOLOGIES`, with distinct radiographs producing genuinely distinct probability vectors and Grad-CAM heatmaps (`std > 0`), while keeping existing `DICOMPreprocessor(target_size=(224, 224))` contracts `(1, 3, 224, 224)` float32 intact.
- **100% Zero-PII Egress & Consultation Integrity:** `ScanChatService` and `/api/chat` MUST still fail closed (`HTTP 422`) on non-compliant DICOM datasets, return `HTTP 410` on crypto-shredded studies, never read `_dashboard_session_cache`, scrub clinician PII (`redact_chat_pii`), and preserve all existing response fields (`ScanChatResponse`).
- **Question Responsiveness:** Distinct user questions (`"Explain this finding in simple terms"`, `"What did the heatmap highlight?"`, `"Next recommended clinical steps"`, pathology-specific prompts, differential/uncertainty prompts) MUST generate substantively distinct local answers tailored to both the prompt and the current scan's metrics/heatmap/image telemetry.
- **No Remote Push & Non-Breaking Tests:** Work locally in `.worktrees/fix-local-models`; never run `git push`; all 50+ pytest tests and `scripts/verify_e2e_pipeline.py` must pass cleanly.

---

## File Map

- **Modify (`Task 1`):** `medshield/ml/preprocessor.py`, `medshield/ml/model.py`, `medshield/ml/explainability.py`, `medshield/ml/inference_engine.py`, `tests/test_ml_inference.py`
- **Modify (`Task 2`):** `medshield/config.py`, `medshield/ml/chat_service.py`, `medshield/api/routes/dashboard.py`, `.env.example`, `tests/test_scan_chat.py`

---

## Tasks

### Task 1: Fix Local DenseNet-121 XRV Normalization, Calibration & Grad-CAM Gradients

**Files:**
- Modify: `medshield/ml/preprocessor.py`
- Modify: `medshield/ml/model.py`
- Modify: `medshield/ml/explainability.py`
- Modify: `medshield/ml/inference_engine.py`
- Test: `tests/test_ml_inference.py`

**Interfaces:**
- `DICOMPreprocessor.__init__(self, target_size: Tuple[int, int] = (224, 224), normalization: str = "imagenet")`
- `DICOMPreprocessor.process(self, dataset: Dataset) -> Tuple[torch.Tensor, Image.Image]` returning `(1, 3, H, W)` float32 tensor (`[-1024, 1024]` when `normalization="xrv"`, ImageNet-standardized when `normalization="imagenet"`) and resized `(H, W)` RGB `PIL.Image` (for XRV, apply consistent square center-crop so PIL heatmap overlay and tensor align spatially!).
- `TorchXRayVisionClassifier`: attribute `input_normalization = "xrv"`; restores `op_threshs` and `input_resolution` from `xrv.models.model_urls["densenet121-res224-all"]` even when loaded offline from local `.pt` checkpoint; implements `forward_logits(x)` returning raw uncalibrated `(batch, len(TARGET_PATHOLOGIES))` logits before `sigmoid`/`op_norm`, while `forward(x)` returns calibrated probabilities `[0.0, 1.0]` WITHOUT double-applying `self.sigmoid` when `self.model.op_threshs` or `self.model.apply_sigmoid` already transformed outputs!
- `ThoracicClassifier`: exposes `input_normalization = "imagenet"` and `forward_logits(x)` returning pre-sigmoid logits.
- `GradCAM.generate_heatmap`: uses `self.model.forward_logits(input_tensor)` when present (falling back to `self.model(input_tensor)`) so saturating `op_norm`/clamping never zeroes spatial gradients.
- `InferenceEngine.__init__`: when `preprocessor is None`, constructs `DICOMPreprocessor(normalization=getattr(self.model, "input_normalization", "imagenet"))`.

**TDD Steps:**
1. Add failing tests in `tests/test_ml_inference.py`:
   - `test_torchxrayvision_loads_local_weights_with_op_threshs`: asserts `TorchXRayVisionClassifier()` sets `is_real_weights is True`, `input_normalization == "xrv"`, and `getattr(model.model, "op_threshs", None) is not None`.
   - `test_inference_engine_produces_distinct_predictions_across_samples`: runs `InferenceEngine()` on `test_samples/patient_01_pneumonia.dcm`, `test_samples/patient_02_effusion.dcm`, `test_samples/patient_03_cardiomegaly.dcm` (skipping cleanly only if `test_samples` absent, though present in repo) AND on distinct synthetic inputs (blank vs lung-lesion synthetic DICOMs), asserting distinct probability vectors (`max abs diff >= 0.15` across real samples and different synthetic textures, NOT identical constant logits) and non-zero Grad-CAM spatial spread (`heatmap.std() > 0.01`).
   - `test_xrv_preprocessor_range_and_spatial_alignment`: verifies `DICOMPreprocessor(normalization="xrv")` maps intensities into `[-1024.0, 1024.0]` with shape `(1, 3, 224, 224)`.
2. Run focused pytest confirming failure on current broken code, implement the fix cleanly, run `python -m pytest tests/ -v`, verify probabilities vary meaningfully across inputs, and commit locally on `fix/local-models`.

---

### Task 2: Make Local Scan Chat Question-Aware, Telemetry-Grounded & Support Local Ollama LLM

**Files:**
- Modify: `medshield/config.py`
- Modify: `medshield/ml/chat_service.py`
- Modify: `medshield/api/routes/dashboard.py`
- Modify: `.env.example`
- Test: `tests/test_scan_chat.py`

**Interfaces:**
- `Settings` in `medshield/config.py`: add `ollama_base_url: str` (`MEDSHIELD_OLLAMA_BASE_URL`, default `"http://127.0.0.1:11434"`) and `ollama_model: str` (`MEDSHIELD_OLLAMA_MODEL`, default `"llama3.2-vision"`), preserving existing `chat_provider` (`"gemini" | "medgemma" | "ollama" | "local" | "auto"`).
- In `medshield/ml/chat_service.py`:
  - Add zero-PII `extract_scan_telemetry(dataset: Dataset) -> Dict[str, Any]` extracting numeric pixel metrics only (dynamic range/contrast std, left-vs-right hemithorax brightness asymmetry, upper/mid/lower optical density ratios, photometric polarity — ZERO DICOM text tags!).
  - Upgrade `compute_heatmap_zone_summary(heatmap_pil)` (preserve string return signature for existing callers/tests!) AND add structured `analyze_heatmap_zones(heatmap_pil) -> Dict[str, Any]` computing peak 3×3 zone, secondary zone, and spatial activation focus percentage.
  - Upgrade `synthesize_offline_grounded_reply(user_message, predictions, target_pathology, heatmap_zone_summary=None, scan_telemetry=None, heatmap_analysis=None, conversation_history=None)` (keep backward-compatible default kwargs for existing unit tests!) so that:
    - Simple-terms intent (`simple`, `plain`, `explain`, `mean`, `layman`), heatmap/spatial intent (`heatmap`, `highlight`, `where`, `zone`, `region`, `red`, `grad-cam`), clinical next-steps intent (`next`, `step`, `recommend`, `workup`, `action`, `ct`, `follow`), specific pathology inquiry (for any of Pneumonia / Cardiomegaly / Pleural Effusion / Pneumothorax / Atelectasis or colloquial synonyms like fluid/heart/collapse/infection), and confidence/differential/normal queries (`uncertain`, `sure`, `compare`, `differential`, `normal`, `other`) each produce genuinely distinct, directly helpful responses grounded in THAT scan's probabilities, telemetry, and heatmap zones.
    - Open-ended custom questions synthesize a focused answer addressing the exact clinical topic/terms raised + prior turn awareness so repeat questions never dump the same boilerplate block.
  - Add `ScanChatService._call_ollama(...)` calling `{cfg.ollama_base_url}/api/chat` via async `httpx` with base64 sanitized PNG (+ optional heatmap PNG), grounded system prompt, and scrubbed history (`stream: False`). Support `provider in ("ollama", "local")` directly, plus `provider == "auto"` (uses Gemini if key set -> MedGemma if HF token set -> local Ollama -> question-aware local grounded fallback without crashing!). Note: leave default `MEDSHIELD_CHAT_PROVIDER` backwards-compatible (`"gemini"`, which falls back to question-aware local grounded reply when key is blank — OR optionally probe local Ollama when explicitly configured `"ollama"`/`"auto"` so default unit tests / unconfigured environments never unexpectedly wait on localhost:11434 timeouts!). Record `provider_used` accurately (`cfg.ollama_model` when Ollama responds, `"grounded-local-fallback"` when synthesized locally).
- `medshield/api/routes/dashboard.py`: compute `heatmap_pil` cleanly inside `/api/chat` (defaulting to generating Grad-CAM for resolved `target_pathology` OR keeping existing `include_heatmap_overlay` / passing heatmap telemetry cleanly — wait: inspect `dashboard.py:555` and check if `include_heatmap_overlay` defaults `False` cleanly; still pass `dataset` so `ScanChatService` extracts `scan_telemetry`, and if user asks about heatmap even with `include_heatmap_overlay=False`, `ScanChatService` or `dashboard.py` should ensure heatmap analysis or note explains clearly; even better, allow `ScanChatService` to use `heatmap_pil` whenever supplied!).

**TDD Steps:**
1. Add failing tests in `tests/test_scan_chat.py`:
   - `test_local_chat_gives_distinct_answers_per_question`: calls `/api/chat` (and `synthesize_offline_grounded_reply`) with 4 different questions (`"Explain this finding in simple terms"`, `"What did the heatmap highlight?"`, `"Next recommended clinical steps"`, `"Is there evidence of Pneumothorax?"`) on the same study and asserts all 4 replies are pairwise distinct (`len({r1, r2, r3, r4}) == 4`) and contain question-specific terms/telemetry while maintaining `zero_pii_verified is True`.
   - `test_local_chat_adapts_across_different_scans`: asserts replies differ quantitatively between two distinct scans/prediction profiles.
   - `test_ollama_local_provider_dispatch_and_fallback`: mocks `httpx.AsyncClient.post` for `MEDSHIELD_CHAT_PROVIDER=ollama` verifying zero-PII payload sent to `/api/chat` and clean fallback when Ollama is unreachable.
2. Run focused pytest confirming failures first, implement Task 2 cleanly, re-run full `python -m pytest tests/ -v` + `python scripts/verify_e2e_pipeline.py`, and commit locally on `fix/local-models`.
