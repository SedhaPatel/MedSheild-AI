import base64
import io
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import httpx
from PIL import Image
from pydicom.dataset import Dataset

from medshield.config import Settings
from medshield.utils.dicom_helpers import extract_pixel_array
from medshield.utils.logging import get_audit_logger
from medshield.verification.compliance_scanner import ComplianceScanner
from medshield.ml.offline_assistant import answer as offline_answer, suggest_follow_ups

logger = get_audit_logger("medshield.ml.chat_service")

# Regex patterns for clinical prompt PII scrubbing
PII_PATTERNS = [
    # Email addresses
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # Phone numbers
    re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
    # SSN
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # MRN / Medical Record Number patterns (e.g. MRN-88412, MRN: 12345, MRN 88412)
    re.compile(r"\b(?:MRN|mrn)[-:\s#]*[A-Za-z0-9-]+\b"),
    # DOB / Date of Birth patterns
    re.compile(r"\b(?:DOB|dob|Date of Birth|birth date)[:\s]*(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b", re.IGNORECASE),
    re.compile(r"\b(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\b(?:19|20)\d{2}\b"),
    # Honorific + Full Name (e.g., Dr. Jane Smith, Mr. John Doe)
    re.compile(r"\b(?:Dr\.|Mr\.|Mrs\.|Ms\.|Prof\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"),
]


def redact_chat_pii(text: str) -> Tuple[str, bool]:
    """
    Scrubs accidental clinician PII input (MRN, SSN, DOB, phone, email, names)
    from user prompts and conversation turns before VLM transport.
    Returns (cleaned_text, was_redacted).
    """
    if not text:
        return "", False

    cleaned = text
    redacted = False

    for pattern in PII_PATTERNS:
        if pattern.search(cleaned):
            cleaned = pattern.sub("[REDACTED_PII]", cleaned)
            redacted = True

    return cleaned, redacted


def assert_zero_pii_and_extract_image(dataset: Dataset) -> str:
    """
    Strict zero-PII security gate and pixel extractor:
    1. Re-validates HIPAA Safe Harbor / DICOM PS 3.15 compliance via ComplianceScanner.
    2. Enforces BurnedInAnnotation == 'NO' and presence of valid PixelData.
    3. Normalizes monochrome pixel intensities safely into an RGB PNG (<= 768x768).
    4. Returns clean base64-encoded PNG with zero DICOM metadata tags forwarded.
    """
    # 1. Compliance scan
    scanner = ComplianceScanner()
    report = scanner.scan_dataset(dataset)
    if not report.is_compliant:
        violations_str = "; ".join(report.violations)
        raise ValueError(f"DICOM dataset violates HIPAA/Safe Harbor zero-PII compliance: {violations_str}")

    # 2. BurnedInAnnotation check
    burned_in = getattr(dataset, "BurnedInAnnotation", None)
    if burned_in != "NO":
        raise ValueError(f"BurnedInAnnotation must be explicitly 'NO', got '{burned_in}'")

    # 3. Validate PixelData
    if not hasattr(dataset, "PixelData") or not dataset.PixelData:
        raise ValueError("DICOM dataset does not contain valid PixelData")

    # 4. Extract and normalize pixel array
    arr = extract_pixel_array(dataset).astype(np.float32)

    photometric = getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")
    if photometric == "MONOCHROME1":
        arr = arr.max() - arr

    p1, p99 = np.percentile(arr, 1), np.percentile(arr, 99)
    if p99 > p1:
        arr = np.clip(arr, p1, p99)
        norm_arr = ((arr - p1) / (p99 - p1) * 255.0).astype(np.uint8)
    else:
        norm_arr = np.zeros_like(arr, dtype=np.uint8)

    # 5. Convert to RGB PIL and resize to max 768x768 keeping aspect ratio
    pil_img = Image.fromarray(norm_arr).convert("RGB")
    if pil_img.width > 768 or pil_img.height > 768:
        pil_img.thumbnail((768, 768), Image.Resampling.BILINEAR)

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def extract_scan_telemetry(dataset: Dataset) -> Dict[str, Any]:
    """
    Zero-PII extraction of objective numeric image telemetry from DICOM pixel data:
    - Dynamic range (ptp), mean pixel intensity, contrast standard deviation.
    - Left-vs-right hemithorax brightness asymmetry.
    - Vertical optical density ratios (upper/mid/lower lung fields).
    - Photometric interpretation polarity.
    CRITICAL: Strictly zero DICOM metadata text tags are read or forwarded.
    """
    arr = extract_pixel_array(dataset).astype(np.float32)
    photometric = str(getattr(dataset, "PhotometricInterpretation", "MONOCHROME2"))
    if photometric == "MONOCHROME1":
        arr = arr.max() - arr

    h, w = arr.shape[:2]
    dynamic_range = float(np.ptp(arr))
    mean_intensity = float(np.mean(arr))
    contrast_std = float(np.std(arr))

    # Left vs Right hemithorax brightness asymmetry
    # In radiology: viewer-left is patient right, viewer-right is patient left
    w_mid = max(1, w // 2)
    ptp = float(np.ptp(arr))
    if ptp > 1e-6:
        norm_01 = (arr - arr.min()) / ptp
    else:
        norm_01 = np.zeros_like(arr)

    viewer_left_mean = float(np.mean(arr[:, :w_mid]))
    viewer_right_mean = float(np.mean(arr[:, w_mid:]))
    norm_left_mean = float(np.mean(norm_01[:, :w_mid]))
    norm_right_mean = float(np.mean(norm_01[:, w_mid:]))
    asymmetry_ratio = float(norm_right_mean / (norm_left_mean + 1e-6))

    # Upper / Mid / Lower vertical optical density
    h_tier = max(1, h // 3)
    upper_mean = float(np.mean(arr[:h_tier, :]))
    mid_mean = float(np.mean(arr[h_tier:2 * h_tier, :]))
    lower_mean = float(np.mean(arr[2 * h_tier:, :]))
    norm_upper_mean = float(np.mean(norm_01[:h_tier, :]))
    norm_lower_mean = float(np.mean(norm_01[2 * h_tier:, :]))
    upper_to_lower = float(norm_upper_mean / (norm_lower_mean + 1e-6))

    return {
        "rows": int(h),
        "cols": int(w),
        "dynamic_range": round(dynamic_range, 2),
        "mean_intensity": round(mean_intensity, 2),
        "contrast_std": round(contrast_std, 2),
        "photometric_polarity": photometric,
        "left_vs_right_asymmetry": {
            "viewer_left_mean": round(viewer_left_mean, 2),
            "viewer_right_mean": round(viewer_right_mean, 2),
            "ratio": round(asymmetry_ratio, 3),
        },
        "vertical_density": {
            "upper_mean": round(upper_mean, 2),
            "mid_mean": round(mid_mean, 2),
            "lower_mean": round(lower_mean, 2),
            "upper_to_lower_ratio": round(upper_to_lower, 3),
        },
    }


def analyze_heatmap_zones(heatmap_pil: Optional[Image.Image]) -> Dict[str, Any]:
    """
    Structured 3x3 anatomical zone activation analysis for Grad-CAM explainability overlays.
    Computes peak zone, secondary zone, and spatial activation focus percentage.
    """
    if heatmap_pil is None:
        return {
            "has_heatmap": False,
            "peak_zone": "None",
            "secondary_zone": "None",
            "focus_percentage": 0.0,
            "summary": "No visual explainability heatmap overlay available.",
            "zone_intensities": {},
        }

    try:
        rgb_arr = np.array(heatmap_pil.convert("RGB"), dtype=np.float32)
        r = rgb_arr[:, :, 0]
        g = rgb_arr[:, :, 1]
        b = rgb_arr[:, :, 2]

        saliency = np.maximum(0.0, r - (b * 0.5 + g * 0.5))
        if float(np.max(saliency)) < 15.0:
            saliency = 0.299 * r + 0.587 * g + 0.114 * b

        h, w = saliency.shape
        y_peak, x_peak = np.unravel_index(np.argmax(saliency), saliency.shape)

        v_names = ["Upper zone (apical)", "Mid zone (perihilar)", "Lower zone (basilar)"]
        h_names = ["right hemithorax (viewer-left)", "central / mediastinal field", "left hemithorax (viewer-right)"]

        zone_intensities: Dict[str, float] = {}
        cell_scores = []
        for i in range(3):
            y_start, y_end = int(i * h / 3.0), int((i + 1) * h / 3.0)
            for j in range(3):
                x_start, x_end = int(j * w / 3.0), int((j + 1) * w / 3.0)
                cell_val = float(np.mean(saliency[y_start:y_end, x_start:x_end]))
                label = f"{v_names[i]} of the {h_names[j]}"
                zone_intensities[label] = round(cell_val, 2)
                cell_scores.append((cell_val, label, i, j))

        cell_scores.sort(key=lambda x: x[0], reverse=True)
        peak_zone = cell_scores[0][1]
        secondary_zone = cell_scores[1][1] if len(cell_scores) > 1 else cell_scores[0][1]

        max_val = float(np.max(saliency))
        if max_val > 1e-4:
            hot_pixels = float(np.sum(saliency > (max_val * 0.5)))
            focus_percentage = round((hot_pixels / float(h * w)) * 100.0, 1)
        else:
            focus_percentage = 0.0

        summary = f"Peak saliency localized in the {peak_zone}. Secondary activation in {secondary_zone} ({focus_percentage}% focal area)."

        return {
            "has_heatmap": True,
            "peak_zone": peak_zone,
            "secondary_zone": secondary_zone,
            "focus_percentage": focus_percentage,
            "summary": summary,
            "zone_intensities": zone_intensities,
            "peak_coordinates": {"y": int(y_peak), "x": int(x_peak)},
        }
    except Exception as exc:
        logger.warning("Error computing structured heatmap zones: %s", exc)
        return {
            "has_heatmap": False,
            "peak_zone": "Diffuse",
            "secondary_zone": "Diffuse",
            "focus_percentage": 0.0,
            "summary": "Diffuse or non-focal activation across lung fields.",
            "zone_intensities": {},
        }


def compute_heatmap_zone_summary(heatmap_pil: Optional[Image.Image]) -> str:
    """
    Computes a clean spatial 3x3 anatomical activation zone summary from a Grad-CAM overlay.
    Preserves exact string return signature for existing callers and unit tests.
    """
    if heatmap_pil is None:
        return "No visual explainability heatmap overlay available."

    analysis = analyze_heatmap_zones(heatmap_pil)
    if not analysis.get("has_heatmap"):
        return analysis.get("summary", "Diffuse or non-focal activation across lung fields.")

    peak = analysis.get("peak_zone", "")
    return f"Peak saliency localized in the {peak}."


def score_verdict(p: Dict[str, Any]) -> str:
    """POSITIVE / NEGATIVE relative to the model's operating threshold (score 0.5)."""
    if "is_positive" in p:
        return "POSITIVE" if p["is_positive"] else "NEGATIVE"
    return "POSITIVE" if float(p.get("probability", 0.0)) >= 0.5 else "NEGATIVE"


def format_score(p: Dict[str, Any]) -> str:
    """Human-readable score, e.g. 'score 0.34 (NEGATIVE; 0.50 = model threshold)'."""
    return f"score {float(p.get('probability', 0.0)):.2f} ({score_verdict(p)}; 0.50 = model threshold)"


def short_score(p: Dict[str, Any]) -> str:
    """Score without the verdict, for sentences that already state POSITIVE/NEGATIVE."""
    return f"score {float(p.get('probability', 0.0)):.2f}; 0.50 = model threshold"


SCORE_EXPLANATION = (
    "Scores are threshold-normalized: 0.50 is the model's operating threshold (>= 0.50 = positive). "
    "They are not calibrated probabilities and must not be quoted as a percentage chance of disease."
)


def build_grounded_system_prompt(
    predictions: Any,
    target_pathology: str,
    heatmap_zone_summary: Optional[str] = None,
    scan_telemetry: Optional[Dict[str, Any]] = None,
    heatmap_analysis: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Constructs the grounded clinical system instruction containing threshold-normalized model scores,
    telemetry, spatial localization, and strict HIPAA Safe Harbor zero-PII directives.
    """
    if isinstance(predictions, dict) and "predictions" in predictions:
        preds_list = predictions["predictions"]
    elif isinstance(predictions, list):
        preds_list = predictions
    else:
        preds_list = []

    findings_lines: List[str] = []
    for p in preds_list:
        pathology = p.get("pathology", "Unknown")
        urgency = p.get("triage_urgency", "ROUTINE")
        findings_lines.append(f"- {pathology}: {format_score(p)}, Triage urgency: {urgency}")

    findings_text = "\n".join(findings_lines) if findings_lines else "No quantitative findings available."

    zone_summary = heatmap_zone_summary
    if not zone_summary and heatmap_analysis and heatmap_analysis.get("summary"):
        zone_summary = heatmap_analysis["summary"]

    heatmap_text = f"\nGrad-CAM Heatmap Localization: {zone_summary}" if zone_summary else ""

    telemetry_text = ""
    if scan_telemetry:
        lr = scan_telemetry.get("left_vs_right_asymmetry", {})
        vd = scan_telemetry.get("vertical_density", {})
        telemetry_lines = [
            f"- Photometric Polarity: {scan_telemetry.get('photometric_polarity', 'MONOCHROME2')}",
            f"- Dynamic Range: {scan_telemetry.get('dynamic_range', 'N/A')} (Contrast Std: {scan_telemetry.get('contrast_std', 'N/A')})",
            f"- Hemithorax Brightness Ratio (L/R): {lr.get('ratio', '1.0')}",
            f"- Optical Density Ratio (Apical/Basilar): {vd.get('upper_to_lower_ratio', '1.0')}",
        ]
        telemetry_text = "\nSCAN TELEMETRY METRICS:\n" + "\n".join(telemetry_lines)

    prompt = f"""You are MedShield-AI's grounded clinical assistant for thoracic radiograph analysis.
You are assisting a healthcare provider reviewing a de-identified DICOM chest X-ray.

CRITICAL ZERO-PII / PRIVACY DIRECTIVE:
Strictly adhere to HIPAA Safe Harbor and zero-PII constraints. The scan provided has been stripped of all metadata tags, names, dates, and identifiers. Never mention, infer, or request patient identifying information (PII/PHI).

GROUNDED MODEL METRICS (DenseNet-121 Classifier):
Target Pathology Under Review: {target_pathology}
{SCORE_EXPLANATION}
{findings_text}{heatmap_text}{telemetry_text}

RESPONSE GUIDELINES:
1. Ground all diagnostic discussions strictly in the validated model findings and the visual scan provided.
2. Discuss each finding as positive or negative relative to the model threshold, and the anatomical region highlighting it. Never present a score as a percentage chance or probability. Scores near 0.50 are borderline and should be described as uncertain.
3. The tool only reports five findings (pneumonia, cardiomegaly, pleural effusion, pneumothorax, atelectasis). If asked about anything else (e.g. cancer, nodules, tuberculosis, fractures, COVID-19), say plainly that this tool does not assess it and that a radiologist's read is needed; do not guess.
4. If asked who the patient is or for any personal details, explain that the study is de-identified and no identifiers are available.
5. Answer in plain, concise language with short paragraphs. Answer only what was asked; do not repeat the full findings list unless it is relevant.

MANDATORY MEDICAL DISCLAIMER:
This AI clinical assistant provides educational and clinical decision-support assistance only. It is not a standalone diagnostic device and must not replace professional clinical diagnosis or judgment by a licensed radiologist or physician."""

    return prompt


def synthesize_offline_grounded_reply(
    user_message: str,
    predictions: Any,
    target_pathology: str,
    heatmap_zone_summary: Optional[str] = None,
    scan_telemetry: Optional[Dict[str, Any]] = None,
    heatmap_analysis: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Built-in answer used when no external model is configured or it fails. See
    medshield.ml.offline_assistant for topic detection and the answer sections.
    (scan_telemetry is accepted for API compatibility; raw pixel statistics are not shown to users.)
    """
    text, _ = offline_answer(
        user_message,
        predictions,
        target_pathology,
        heatmap_analysis=heatmap_analysis,
        heatmap_zone_summary=heatmap_zone_summary,
        conversation_history=conversation_history,
    )
    return text


class ScanChatService:
    """
    Zero-PII clinical VLM chat orchestration service.
    Coordinates Safe Harbor dataset validation, prompt PII scrubbing,
    and multimodal VLM integration (Gemini 2.5 Flash, MedGemma, local Ollama,
    and local telemetry/question-aware grounded fallback).
    """
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings

    async def _call_gemini(
        self,
        *,
        cfg: Settings,
        system_prompt: str,
        scrubbed_user_message: str,
        scrubbed_history: List[Dict[str, str]],
        scan_image_b64: str,
        heatmap_b64: Optional[str] = None
    ) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.gemini_model}:generateContent"
        headers = {
            "x-goog-api-key": cfg.gemini_api_key or "",
            "Content-Type": "application/json"
        }

        # Gemini multi-turn format:
        # Outbound 'contents' MUST start with role 'user' and strictly alternate 'user' and 'model'.
        # 1. Normalize scrubbed history roles and filter empty contents.
        raw_history: List[Dict[str, str]] = []
        for turn in scrubbed_history:
            role = "user" if turn.get("role") == "user" else "model"
            content = turn.get("content", "").strip()
            if content:
                raw_history.append({"role": role, "content": content})

        # 2. Prune any leading assistant/model turns so contents start with 'user'.
        while raw_history and raw_history[0]["role"] != "user":
            raw_history.pop(0)

        # 3. Merge consecutive same-role history turns safely.
        merged_history: List[Dict[str, str]] = []
        for turn in raw_history:
            if merged_history and merged_history[-1]["role"] == turn["role"]:
                merged_history[-1]["content"] = f"{merged_history[-1]['content']}\n\n{turn['content']}".strip()
            else:
                merged_history.append({"role": turn["role"], "content": turn["content"]})

        # 4. If the last history turn is 'user', prune it so that history ends with 'model'
        # before we append the current final 'user' turn (preserving strict role alternation).
        while merged_history and merged_history[-1]["role"] == "user":
            merged_history.pop()

        contents: List[Dict[str, Any]] = []
        for turn in merged_history:
            contents.append({
                "role": turn["role"],
                "parts": [{"text": turn["content"]}]
            })

        user_parts: List[Dict[str, Any]] = [
            {"text": scrubbed_user_message},
            {"inlineData": {"mimeType": "image/png", "data": scan_image_b64}}
        ]
        if heatmap_b64:
            user_parts.append({"inlineData": {"mimeType": "image/png", "data": heatmap_b64}})

        contents.append({"role": "user", "parts": user_parts})

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": contents
        }

        timeout = httpx.Timeout(cfg.chat_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("Gemini returned empty candidates list")
            parts = candidates[0].get("content", {}).get("parts", [])
            answer = "".join([p.get("text", "") for p in parts]).strip()
            if not answer:
                raise ValueError("Gemini returned empty text in candidates")
            return answer

    async def _call_medgemma(
        self,
        *,
        cfg: Settings,
        system_prompt: str,
        scrubbed_user_message: str,
        scrubbed_history: List[Dict[str, str]],
        scan_image_b64: str,
        heatmap_b64: Optional[str] = None
    ) -> str:
        url = "https://router.huggingface.co/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg.hf_api_token or ''}",
            "Content-Type": "application/json"
        }

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        for turn in scrubbed_history:
            role = turn.get("role", "user")
            messages.append({"role": role, "content": turn.get("content", "")})

        user_content: List[Dict[str, Any]] = [
            {"type": "text", "text": scrubbed_user_message},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{scan_image_b64}"}}
        ]
        if heatmap_b64:
            user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{heatmap_b64}"}})

        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": cfg.medgemma_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1024
        }

        timeout = httpx.Timeout(cfg.chat_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("MedGemma returned empty choices")
            content = choices[0].get("message", {}).get("content", "").strip()
            if not content:
                raise ValueError("MedGemma returned empty message content")
            return content

    async def _call_ollama(
        self,
        *,
        cfg: Settings,
        system_prompt: str,
        scrubbed_user_message: str,
        scrubbed_history: List[Dict[str, str]],
        scan_image_b64: str,
        heatmap_b64: Optional[str] = None
    ) -> str:
        url = f"{cfg.ollama_base_url.rstrip('/')}/api/chat"
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        for turn in scrubbed_history:
            role = turn.get("role", "user")
            if role in ("assistant", "model"):
                role = "assistant"
            else:
                role = "user"
            content = turn.get("content", "")
            messages.append({"role": role, "content": content})

        user_images = [scan_image_b64]
        if heatmap_b64:
            user_images.append(heatmap_b64)

        messages.append({
            "role": "user",
            "content": scrubbed_user_message,
            "images": user_images,
        })

        payload = {
            "model": cfg.ollama_model,
            "messages": messages,
            "stream": False,
        }

        timeout = httpx.Timeout(cfg.chat_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            if not content:
                raise ValueError("Ollama returned empty message content")
            return content

    async def generate_reply(
        self,
        *,
        dataset: Dataset,
        user_message: str,
        predictions: Any,
        target_pathology: str,
        conversation_history: List[Dict[str, str]],
        heatmap_pil: Optional[Image.Image] = None,
        settings: Optional[Settings] = None,
        attach_heatmap_image: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Coordinates full zero-PII scan chat flow:
        - Re-validates zero-PII compliance and extracts anonymized RGB image.
        - Computes zero-PII objective pixel telemetry (dynamic range, asymmetry, density).
        - Scrubs user message and history for accidental PII.
        - Analyzes Grad-CAM heatmap localization.
        - Dispatches to configured VLM provider (Gemini / MedGemma / Ollama / Auto) or local deterministic fallback.
        """
        # Resolve config
        cfg = settings or self.settings or Settings()

        # 1. Zero-PII gate & pixel extraction (raises ValueError if non-compliant)
        scan_image_b64 = assert_zero_pii_and_extract_image(dataset)

        # 2. Extract zero-PII objective numeric scan telemetry
        scan_telemetry = extract_scan_telemetry(dataset)

        # 3. Scrub user message and history
        scrubbed_user_message, msg_redacted = redact_chat_pii(user_message)
        pii_redacted_from_prompt = msg_redacted

        scrubbed_history: List[Dict[str, str]] = []
        for turn in (conversation_history or [])[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            cleaned_content, turn_redacted = redact_chat_pii(content)
            if turn_redacted:
                pii_redacted_from_prompt = True
            scrubbed_history.append({"role": role, "content": cleaned_content})

        # 4. Process heatmap overlay and structured zone analysis
        heatmap_analysis = analyze_heatmap_zones(heatmap_pil)
        heatmap_zone_summary: Optional[str] = heatmap_analysis["summary"] if heatmap_analysis["has_heatmap"] else None

        should_attach_heatmap = attach_heatmap_image if attach_heatmap_image is not None else (heatmap_pil is not None)
        heatmap_b64: Optional[str] = None
        if should_attach_heatmap and heatmap_pil is not None:
            h_copy = heatmap_pil.copy()
            if h_copy.width > 768 or h_copy.height > 768:
                h_copy.thumbnail((768, 768), Image.Resampling.BILINEAR)
            h_buf = io.BytesIO()
            h_copy.convert("RGB").save(h_buf, format="PNG")
            heatmap_b64 = base64.b64encode(h_buf.getvalue()).decode("utf-8")

        # 5. Resolve predictions list & grounded findings
        if isinstance(predictions, dict) and "predictions" in predictions:
            preds_list = predictions["predictions"]
        elif isinstance(predictions, list):
            preds_list = predictions
        else:
            preds_list = []

        grounded_findings = [
            f"{p.get('pathology', 'Unknown')}: {format_score(p)}"
            for p in preds_list
        ]

        # 6. Build grounded system prompt
        system_prompt = build_grounded_system_prompt(
            predictions=preds_list,
            target_pathology=target_pathology,
            heatmap_zone_summary=heatmap_zone_summary,
            scan_telemetry=scan_telemetry,
            heatmap_analysis=heatmap_analysis,
        )

        # 7. Provider dispatch
        provider = (cfg.chat_provider or "gemini").lower()
        provider_used = "grounded-local-fallback"
        answer: Optional[str] = None

        if provider == "gemini":
            if cfg.gemini_api_key and cfg.gemini_api_key.strip():
                try:
                    answer = await self._call_gemini(
                        cfg=cfg,
                        system_prompt=system_prompt,
                        scrubbed_user_message=scrubbed_user_message,
                        scrubbed_history=scrubbed_history,
                        scan_image_b64=scan_image_b64,
                        heatmap_b64=heatmap_b64
                    )
                    provider_used = cfg.gemini_model
                except Exception as exc:
                    logger.warning("Gemini multimodal request failed: %s; falling back to offline", exc)
                    answer = None
        elif provider in ("medgemma", "huggingface"):
            if cfg.hf_api_token and cfg.hf_api_token.strip():
                try:
                    answer = await self._call_medgemma(
                        cfg=cfg,
                        system_prompt=system_prompt,
                        scrubbed_user_message=scrubbed_user_message,
                        scrubbed_history=scrubbed_history,
                        scan_image_b64=scan_image_b64,
                        heatmap_b64=heatmap_b64
                    )
                    provider_used = cfg.medgemma_model
                except Exception as exc:
                    logger.warning("MedGemma multimodal request failed: %s; falling back to offline", exc)
                    answer = None
        elif provider in ("ollama", "local"):
            try:
                answer = await self._call_ollama(
                    cfg=cfg,
                    system_prompt=system_prompt,
                    scrubbed_user_message=scrubbed_user_message,
                    scrubbed_history=scrubbed_history,
                    scan_image_b64=scan_image_b64,
                    heatmap_b64=heatmap_b64
                )
                provider_used = cfg.ollama_model
            except Exception as exc:
                logger.warning("Ollama local multimodal request failed: %s; falling back to offline", exc)
                answer = None
        elif provider == "auto":
            # Auto fallback chain: Gemini (if key) -> MedGemma (if token) -> Ollama local -> offline
            if cfg.gemini_api_key and cfg.gemini_api_key.strip():
                try:
                    answer = await self._call_gemini(
                        cfg=cfg,
                        system_prompt=system_prompt,
                        scrubbed_user_message=scrubbed_user_message,
                        scrubbed_history=scrubbed_history,
                        scan_image_b64=scan_image_b64,
                        heatmap_b64=heatmap_b64
                    )
                    provider_used = cfg.gemini_model
                except Exception as exc:
                    logger.warning("Auto provider Gemini failed: %s", exc)

            if not answer and cfg.hf_api_token and cfg.hf_api_token.strip():
                try:
                    answer = await self._call_medgemma(
                        cfg=cfg,
                        system_prompt=system_prompt,
                        scrubbed_user_message=scrubbed_user_message,
                        scrubbed_history=scrubbed_history,
                        scan_image_b64=scan_image_b64,
                        heatmap_b64=heatmap_b64
                    )
                    provider_used = cfg.medgemma_model
                except Exception as exc:
                    logger.warning("Auto provider MedGemma failed: %s", exc)

            if not answer:
                try:
                    answer = await self._call_ollama(
                        cfg=cfg,
                        system_prompt=system_prompt,
                        scrubbed_user_message=scrubbed_user_message,
                        scrubbed_history=scrubbed_history,
                        scan_image_b64=scan_image_b64,
                        heatmap_b64=heatmap_b64
                    )
                    provider_used = cfg.ollama_model
                except Exception as exc:
                    logger.warning("Auto provider Ollama failed: %s; falling back to offline synthesizer", exc)

        # The built-in answer doubles as topic detection for follow-up suggestions on every path
        offline_text, topic_info = offline_answer(
            scrubbed_user_message,
            preds_list,
            target_pathology,
            heatmap_analysis=heatmap_analysis,
            heatmap_zone_summary=heatmap_zone_summary,
            conversation_history=scrubbed_history,
        )
        if not answer:
            answer = offline_text
            provider_used = "grounded-local-fallback"

        asked_before = [t["content"] for t in scrubbed_history if t.get("role") == "user"] + [scrubbed_user_message]
        suggested_questions = suggest_follow_ups(
            topic_info, preds_list, asked_before=asked_before, history=scrubbed_history
        )

        return {
            "provider_used": provider_used,
            "answer": answer,
            "suggested_questions": suggested_questions,
            "grounded_findings": grounded_findings,
            "zero_pii_verified": True,
            "pii_redacted_from_prompt": pii_redacted_from_prompt,
            "medical_disclaimer": (
                "AI decision support only; not a definitive clinical diagnosis. "
                "Always correlate with full clinical presentation and radiologist review."
            )
        }
