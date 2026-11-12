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


def compute_heatmap_zone_summary(heatmap_pil: Optional[Image.Image]) -> str:
    """
    Computes a clean spatial 3x3 anatomical activation zone summary from a Grad-CAM overlay.
    """
    if heatmap_pil is None:
        return "No visual explainability heatmap overlay available."

    try:
        rgb_arr = np.array(heatmap_pil.convert("RGB"), dtype=np.float32)
        r = rgb_arr[:, :, 0]
        g = rgb_arr[:, :, 1]
        b = rgb_arr[:, :, 2]

        # Saliency metric: warm/hot red activation
        saliency = np.maximum(0.0, r - (b * 0.5 + g * 0.5))
        if float(np.max(saliency)) < 15.0:
            saliency = 0.299 * r + 0.587 * g + 0.114 * b

        h, w = saliency.shape
        y_peak, x_peak = np.unravel_index(np.argmax(saliency), saliency.shape)

        # Vertical classification
        if y_peak < h / 3.0:
            v_zone = "Upper zone (apical)"
        elif y_peak < 2.0 * h / 3.0:
            v_zone = "Mid zone (perihilar)"
        else:
            v_zone = "Lower zone (basilar)"

        # Horizontal classification (radiological perspective: viewer-left is patient's right)
        if x_peak < w / 3.0:
            h_zone = "right hemithorax (viewer-left)"
        elif x_peak < 2.0 * w / 3.0:
            h_zone = "central / mediastinal field"
        else:
            h_zone = "left hemithorax (viewer-right)"

        return f"Peak saliency localized in the {v_zone} of the {h_zone}."
    except Exception as exc:
        logger.warning("Error computing heatmap zone summary: %s", exc)
        return "Diffuse or non-focal activation across lung fields."


def build_grounded_system_prompt(
    predictions: Any,
    target_pathology: str,
    heatmap_zone_summary: Optional[str] = None
) -> str:
    """
    Constructs the grounded clinical system instruction containing calibrated model metrics,
    spatial localization, and strict HIPAA Safe Harbor zero-PII directives.
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
        prob = float(p.get("probability", 0.0))
        uncertainty = float(p.get("epistemic_uncertainty", 0.0))
        urgency = p.get("triage_urgency", "ROUTINE")
        findings_lines.append(
            f"- {pathology}: {prob * 100:.1f}% calibrated probability "
            f"(Epistemic uncertainty: {uncertainty:.4f}, Triage urgency: {urgency})"
        )

    findings_text = "\n".join(findings_lines) if findings_lines else "No quantitative findings available."
    heatmap_text = f"\nGrad-CAM Heatmap Localization: {heatmap_zone_summary}" if heatmap_zone_summary else ""

    prompt = f"""You are MedShield-AI's grounded clinical assistant for thoracic radiograph analysis.
You are assisting a healthcare provider reviewing a de-identified DICOM chest X-ray.

CRITICAL ZERO-PII / PRIVACY DIRECTIVE:
Strictly adhere to HIPAA Safe Harbor and zero-PII constraints. The scan provided has been stripped of all metadata tags, names, dates, and identifiers. Never mention, infer, or request patient identifying information (PII/PHI).

GROUNDED MODEL METRICS (DenseNet-121 Classifier):
Target Pathology Under Review: {target_pathology}
{findings_text}{heatmap_text}

RESPONSE GUIDELINES:
1. Ground all diagnostic discussions strictly in the validated model findings and the visual scan provided.
2. Discuss the probability, uncertainty, and anatomical region highlighting the condition.
3. If asked about anomalies outside the model's target pathologies, provide objective observational feedback based solely on the visual radiograph, noting that it is unclassified by the model.
4. Maintain an objective, disciplined clinical tone.

MANDATORY MEDICAL DISCLAIMER:
This AI clinical assistant provides educational and clinical decision-support assistance only. It is not a standalone diagnostic device and must not replace professional clinical diagnosis or judgment by a licensed radiologist or physician."""

    return prompt


def synthesize_offline_grounded_reply(
    user_message: str,
    predictions: Any,
    target_pathology: str,
    heatmap_zone_summary: Optional[str] = None
) -> str:
    """
    Deterministic offline fallback synthesizer when upstream VLM API credentials
    are unset or network errors occur. Strictly grounded on model metrics.
    """
    if isinstance(predictions, dict) and "predictions" in predictions:
        preds_list = predictions["predictions"]
    elif isinstance(predictions, list):
        preds_list = predictions
    else:
        preds_list = []

    # Find target pathology metrics
    target_pred = None
    for p in preds_list:
        if p.get("pathology", "").lower() == target_pathology.lower():
            target_pred = p
            break

    if target_pred:
        target_prob = float(target_pred.get("probability", 0.0)) * 100.0
        target_urgency = target_pred.get("triage_urgency", "ROUTINE")
        target_uncertainty = float(target_pred.get("epistemic_uncertainty", 0.0))
        target_summary = (
            f"The primary target under review is **{target_pathology}**, evaluated at a calibrated probability "
            f"of **{target_prob:.1f}%** ({target_urgency} triage level, epistemic uncertainty ±{target_uncertainty:.4f})."
        )
    else:
        target_summary = f"The primary target under review is **{target_pathology}**."

    saliency_text = f"\n\n**Visual Explainability (Grad-CAM):**\n{heatmap_zone_summary}" if heatmap_zone_summary else ""

    findings_summary = []
    for p in preds_list:
        pathology = p.get("pathology", "Unknown")
        prob = float(p.get("probability", 0.0)) * 100.0
        findings_summary.append(f"- **{pathology}**: {prob:.1f}% ({p.get('triage_urgency', 'ROUTINE')})")

    findings_block = "\n".join(findings_summary) if findings_summary else "- No model findings registered."

    reply = f"""**Clinical Scan Analysis Summary**

{target_summary}{saliency_text}

**Multi-Label Classifier Findings:**
{findings_block}

**Clinical Correlation:**
In response to your query regarding *"{user_message}"*:
The AI triage model evaluates features across the thoracic field corresponding to the probabilities above. Higher-urgency alerts warrant immediate clinical and radiological correlation to assess acute pathology versus artifactual density."""

    return reply


class ScanChatService:
    """
    Zero-PII clinical VLM chat orchestration service.
    Coordinates Safe Harbor dataset validation, prompt PII scrubbing,
    and multimodal VLM integration (Gemini 2.5 Flash / MedGemma / offline fallback).
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
    ) -> Dict[str, Any]:
        """
        Coordinates full zero-PII scan chat flow:
        - Re-validates zero-PII compliance and extracts anonymized RGB image.
        - Scrubs user message and history for accidental PII.
        - Analyzes Grad-CAM heatmap localization.
        - Dispatches to configured VLM provider or local deterministic fallback.
        """
        # Resolve config
        cfg = settings or self.settings or Settings()

        # 1. Zero-PII gate & pixel extraction (raises ValueError if non-compliant)
        scan_image_b64 = assert_zero_pii_and_extract_image(dataset)

        # 2. Scrub user message and history
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

        # 3. Process heatmap overlay if provided
        heatmap_zone_summary: Optional[str] = None
        heatmap_b64: Optional[str] = None
        if heatmap_pil is not None:
            heatmap_zone_summary = compute_heatmap_zone_summary(heatmap_pil)
            h_copy = heatmap_pil.copy()
            if h_copy.width > 768 or h_copy.height > 768:
                h_copy.thumbnail((768, 768), Image.Resampling.BILINEAR)
            h_buf = io.BytesIO()
            h_copy.convert("RGB").save(h_buf, format="PNG")
            heatmap_b64 = base64.b64encode(h_buf.getvalue()).decode("utf-8")

        # 4. Resolve predictions list & grounded findings
        if isinstance(predictions, dict) and "predictions" in predictions:
            preds_list = predictions["predictions"]
        elif isinstance(predictions, list):
            preds_list = predictions
        else:
            preds_list = []

        grounded_findings = [
            f"{p.get('pathology', 'Unknown')}: {float(p.get('probability', 0.0)) * 100:.1f}%"
            for p in preds_list
        ]

        # 5. Build grounded system prompt
        system_prompt = build_grounded_system_prompt(
            predictions=preds_list,
            target_pathology=target_pathology,
            heatmap_zone_summary=heatmap_zone_summary
        )

        # 6. Provider dispatch
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

        if not answer:
            answer = synthesize_offline_grounded_reply(
                user_message=scrubbed_user_message,
                predictions=preds_list,
                target_pathology=target_pathology,
                heatmap_zone_summary=heatmap_zone_summary
            )
            provider_used = "grounded-local-fallback"

        return {
            "provider_used": provider_used,
            "answer": answer,
            "grounded_findings": grounded_findings,
            "zero_pii_verified": True,
            "pii_redacted_from_prompt": pii_redacted_from_prompt,
            "medical_disclaimer": (
                "AI decision support only; not a definitive clinical diagnosis. "
                "Always correlate with full clinical presentation and radiologist review."
            )
        }
