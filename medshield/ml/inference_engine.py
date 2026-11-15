from typing import Any, Dict, List, Optional
import time
import numpy as np
import torch
from PIL import Image
from pydicom.dataset import Dataset

from medshield.ml.model import ThoracicClassifier, build_thoracic_model, TARGET_PATHOLOGIES
from medshield.ml.preprocessor import DICOMPreprocessor
from medshield.ml.explainability import GradCAM, overlay_heatmap

SCORE_SEMANTICS = (
    "Threshold-normalized model score: 0.5 is the model's operating threshold (>= 0.5 = positive). "
    "It is not a calibrated probability of disease."
)


class InferenceEngine:
    """
    High-level clinical inference orchestration service.
    Processes DICOM datasets, executes multi-label disease classification,
    assigns triage urgency levels, and extracts Grad-CAM visual heatmaps.
    """
    def __init__(
        self,
        model: Optional[Any] = None,
        preprocessor: Optional[DICOMPreprocessor] = None
    ):
        self.model = model or build_thoracic_model()
        self.model.eval()
        norm = getattr(self.model, "input_normalization", "imagenet")
        self.preprocessor = preprocessor or DICOMPreprocessor(normalization=norm)
        self.gradcam = GradCAM(self.model)

    def _scores(self, input_tensor: torch.Tensor) -> List[Dict[str, Optional[float]]]:
        """
        Returns, per target pathology, the raw sigmoid output, the model's operating threshold, and a
        threshold-normalized score where 0.5 == the operating threshold (TorchXRayVision `op_norm`):
            raw <  t:  score = raw / (2t)              -> [0, 0.5)
            raw >= t:  score = 1 - (1 - raw) / (2(1-t)) -> [0.5, 1]
        Without a tuned threshold, t = 0.5 and score == raw.
        """
        with torch.no_grad():
            if hasattr(self.model, "forward_logits"):
                raw = torch.sigmoid(self.model.forward_logits(input_tensor))[0].cpu().numpy()
            else:
                raw = self.model(input_tensor)[0].cpu().numpy()

        thresholds = (
            self.model.operating_thresholds()
            if hasattr(self.model, "operating_thresholds")
            else [None] * len(TARGET_PATHOLOGIES)
        )
        results = []
        for idx in range(len(TARGET_PATHOLOGIES)):
            r = float(np.clip(raw[idx], 0.0, 1.0))
            t = thresholds[idx]
            t_eff = t if (t is not None and 0.0 < t < 1.0) else 0.5
            score = r / (2.0 * t_eff) if r < t_eff else 1.0 - (1.0 - r) / (2.0 * (1.0 - t_eff))
            results.append({"raw": r, "threshold": t, "score": float(np.clip(score, 0.0, 1.0))})
        return results

    def predict(self, dataset: Dataset) -> Dict[str, Any]:
        start_time = time.perf_counter()

        study_uid = getattr(dataset, "StudyInstanceUID", "2.25.0000000000")
        input_tensor, pil_img = self.preprocessor.process(dataset)
        scores = self._scores(input_tensor)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        predictions: List[Dict[str, Any]] = []
        for idx, pathology in enumerate(TARGET_PATHOLOGIES):
            score = scores[idx]["score"]
            threshold = scores[idx]["threshold"]

            # Triage rules on the threshold-normalized score (0.5 == model operating threshold)
            if score >= 0.70 and pathology in ("Pneumothorax", "Pneumonia"):
                urgency = "STAT_CRITICAL"
            elif score >= 0.50:
                urgency = "ELEVATED"
            else:
                urgency = "ROUTINE"

            predictions.append({
                "pathology": pathology,
                # Kept under its historical name for API compatibility. This is a
                # threshold-normalized score, NOT a calibrated probability: see SCORE_SEMANTICS.
                "probability": round(score, 4),
                "is_positive": score >= 0.5,
                "raw_score": round(scores[idx]["raw"], 4),
                "operating_threshold": round(threshold, 4) if threshold is not None else 0.5,
                "triage_urgency": urgency,
                "gradcam_heatmap_url": f"/api/v1/heatmaps/{study_uid}/{pathology.lower().replace(' ', '_')}.png" if score >= 0.3 else None,
                "bounding_box_normalized": None
            })

        return {
            "study_instance_uid": study_uid,
            "model_name": getattr(self.model, "model_name", "EfficientNet-V2-S-Thoracic-Triage-v1"),
            "is_real_weights": getattr(self.model, "is_real_weights", False),
            "weights_source": getattr(self.model, "weights_source", "Random/Uninitialized"),
            "inference_latency_ms": latency_ms,
            "score_semantics": SCORE_SEMANTICS,
            "predictions": predictions
        }

    def generate_heatmap_image(self, dataset: Dataset, pathology: str) -> Image.Image:
        """
        Generates blended PIL image of Grad-CAM overlay for the requested pathology.
        """
        # predict() emits heatmap URLs as ".../{pathology}.png"; accept that suffix
        if pathology.lower().endswith(".png"):
            pathology = pathology[:-4]
        if pathology not in TARGET_PATHOLOGIES:
            # Case-insensitive lookup
            matched = [p for p in TARGET_PATHOLOGIES if p.lower().replace(" ", "_") == pathology.lower().replace(" ", "_")]
            if not matched:
                raise ValueError(f"Unknown pathology '{pathology}'. Must be one of {TARGET_PATHOLOGIES}")
            pathology = matched[0]
            
        class_idx = TARGET_PATHOLOGIES.index(pathology)
        input_tensor, pil_img = self.preprocessor.process(dataset)
        
        heatmap_2d = self.gradcam.generate_heatmap(input_tensor, class_idx=class_idx)
        blended_img = overlay_heatmap(heatmap_2d, pil_img, alpha=0.45)
        return blended_img

