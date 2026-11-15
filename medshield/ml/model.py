from typing import List, Optional, Tuple
import logging
import os
import torch
import torch.nn as nn
import torchvision.models as models

logger = logging.getLogger(__name__)

TARGET_PATHOLOGIES: List[str] = [
    "Pneumonia",
    "Cardiomegaly",
    "Pleural Effusion",
    "Pneumothorax",
    "Atelectasis"
]

XRV_PATHOLOGY_MAP = {
    "Pneumonia": "Pneumonia",
    "Cardiomegaly": "Cardiomegaly",
    "Pleural Effusion": "Effusion",
    "Pneumothorax": "Pneumothorax",
    "Atelectasis": "Atelectasis"
}

class ThoracicClassifier(nn.Module):
    """
    Multi-label convolutional classifier for chest radiography disease detection.
    Wraps EfficientNet-V2-S with multi-label Sigmoid output heads.
    """
    def __init__(self, num_classes: int = len(TARGET_PATHOLOGIES)):
        super().__init__()
        self.input_normalization = "imagenet"
        self.backbone = models.efficientnet_v2_s(weights=None)
        in_features = self.backbone.classifier[1].in_features
        # Replace classifier head
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(p=0.2, inplace=True),
            nn.Linear(in_features, num_classes)
        )
        self.sigmoid = nn.Sigmoid()
        self.is_real_weights = False
        self.model_name = "EfficientNet-V2-S-Thoracic-Triage-v1"

    def forward_logits(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 4 and x.shape[1] == 1:
            x = x.repeat(1, 3, 1, 1)
        return self.backbone(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits = self.forward_logits(x)
        return self.sigmoid(logits)

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 4 and x.shape[1] == 1:
            x = x.repeat(1, 3, 1, 1)
        return self.backbone.features(x)

    def get_last_conv_layer(self) -> nn.Module:
        return self.backbone.features[-1]

    def get_last_conv_layer_name(self) -> str:
        return "backbone.features.7"

    def operating_thresholds(self) -> List[Optional[float]]:
        """No tuned operating points: sigmoid outputs are thresholded at 0.5."""
        return [None] * len(TARGET_PATHOLOGIES)


class TorchXRayVisionClassifier(nn.Module):
    """
    Medical deep learning classifier backed by TorchXRayVision DenseNet-121,
    pre-trained on NIH ChestX-ray14, CheXpert, MIMIC-CXR, OpenI, and Kaggle.
    """
    def __init__(self, checkpoint_path: Optional[str] = None):
        super().__init__()
        import torchxrayvision as xrv
        
        cache_dir = os.path.abspath("weights")
        weights_file = "nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt"
        default_weights_path = os.path.join(cache_dir, weights_file)
        
        target_path = checkpoint_path or (default_weights_path if os.path.exists(default_weights_path) else None)
        
        if target_path and os.path.exists(target_path):
            self.model = xrv.models.DenseNet(weights=None)
            try:
                state_dict = torch.load(target_path, map_location="cpu", weights_only=False)
                if hasattr(state_dict, "state_dict"):
                    state_dict = state_dict.state_dict()
                clean_state = {}
                for k, v in state_dict.items():
                    key = k.replace("model.", "") if k.startswith("model.") else k
                    clean_state[key] = v
                self.model.load_state_dict(clean_state, strict=False)
                self.is_real_weights = True
            except Exception:
                # Fallback to xrv internal loader with cache_dir
                try:
                    self.model = xrv.models.DenseNet(weights="densenet121-res224-all", cache_dir=cache_dir)
                    self.is_real_weights = True
                except Exception:
                    self.model = xrv.models.DenseNet(weights=None)
                    self.is_real_weights = False
        else:
            try:
                self.model = xrv.models.DenseNet(weights="densenet121-res224-all", cache_dir=cache_dir)
                self.is_real_weights = True
            except Exception:
                self.model = xrv.models.DenseNet(weights=None)
                self.is_real_weights = False

        # Restore op_threshs, input_resolution, and pathologies from TorchXRayVision metadata
        model_meta = getattr(xrv.models, "model_urls", {}).get("densenet121-res224-all", {})
        if "op_threshs" in model_meta and getattr(self.model, "op_threshs", None) is None:
            self.model.op_threshs = torch.tensor(model_meta["op_threshs"], dtype=torch.float32)
        if "input_resolution" in model_meta and getattr(self.model, "input_resolution", None) is None:
            self.model.input_resolution = model_meta["input_resolution"]
        if "labels" in model_meta:
            self.model.targets = model_meta["labels"]
            self.model.pathologies = self.model.targets

        self.input_normalization = "xrv"
        self.model_name = "DenseNet121-TorchXRayVision-Pretrained"
        self.weights_source = "NIH-ChestX-ray14 + CheXpert + MIMIC-CXR" if self.is_real_weights else "Uninitialized"
        
        # Map our 5 target pathologies to XRV indices
        pathologies = getattr(self.model, "pathologies", xrv.datasets.default_pathologies)
        self.target_indices: List[int] = []
        for p in TARGET_PATHOLOGIES:
            xrv_name = XRV_PATHOLOGY_MAP[p]
            if xrv_name in pathologies:
                self.target_indices.append(pathologies.index(xrv_name))
            else:
                self.target_indices.append(-1)
                
        self.sigmoid = nn.Sigmoid()

    def forward_logits(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 4 and x.shape[1] == 3:
            x = x.mean(dim=1, keepdim=True)
            
        features = self.model.features2(x)
        all_logits = self.model.classifier(features)
        
        selected_logits = []
        for idx in self.target_indices:
            if idx >= 0:
                selected_logits.append(all_logits[:, idx:idx+1])
            else:
                selected_logits.append(torch.zeros(x.shape[0], 1, device=x.device))
        return torch.cat(selected_logits, dim=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # XRV expects single channel (1, 1, 224, 224)
        if x.dim() == 4 and x.shape[1] == 3:
            x = x.mean(dim=1, keepdim=True)
            
        raw_output = self.model(x)
        # Avoid double-applying sigmoid when self.model already normalized via op_threshs or apply_sigmoid
        has_op_threshs = getattr(self.model, "op_threshs", None) is not None
        has_apply_sigmoid = getattr(self.model, "apply_sigmoid", False)
        
        if has_op_threshs or has_apply_sigmoid:
            probs = raw_output
        else:
            probs = self.sigmoid(raw_output)
            
        selected_probs = []
        for idx in self.target_indices:
            if idx >= 0:
                selected_probs.append(probs[:, idx:idx+1])
            else:
                selected_probs.append(torch.zeros(x.shape[0], 1, device=x.device))
        out = torch.cat(selected_probs, dim=1)
        return torch.clamp(out, 0.0, 1.0)

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 4 and x.shape[1] == 3:
            x = x.mean(dim=1, keepdim=True)
        return self.model.features(x)

    def get_last_conv_layer(self) -> nn.Module:
        return self.model.features.denseblock4.denselayer16.conv2

    def get_last_conv_layer_name(self) -> str:
        return "model.features.denseblock4.denselayer16.conv2"

    def operating_thresholds(self) -> List[Optional[float]]:
        """
        Per-target operating thresholds on the raw sigmoid output (TorchXRayVision `op_threshs`),
        or None where unavailable. These were tuned on the training data and are low for rare
        findings (e.g. ~0.057 for Pneumonia), so raw sigmoid values are not calibrated probabilities.
        """
        op_threshs = getattr(self.model, "op_threshs", None)
        thresholds: List[Optional[float]] = []
        for idx in self.target_indices:
            value = float(op_threshs[idx]) if (op_threshs is not None and idx >= 0) else float("nan")
            thresholds.append(None if value != value else value)  # NaN -> None
        return thresholds


XRV_ARCHITECTURES = ("torchxrayvision", "densenet121")
EFFICIENTNET_ARCHITECTURES = ("efficientnet_v2_s", "efficientnet")


def build_thoracic_model(
    checkpoint_path: Optional[str] = None,
    pretrained: bool = True,
    architecture: str = "torchxrayvision"
) -> nn.Module:
    """
    Factory constructing the clinical disease detection model.

    - "torchxrayvision" / "densenet121" (default): pre-trained TorchXRayVision DenseNet-121, optionally
      from a local checkpoint; falls back to ThoracicClassifier if it cannot be constructed.
    - "efficientnet_v2_s": ThoracicClassifier. It has NO pre-trained clinical weights, so a
      checkpoint_path is required for meaningful predictions.
    """
    arch = (architecture or "torchxrayvision").strip().lower()
    if arch not in XRV_ARCHITECTURES + EFFICIENTNET_ARCHITECTURES:
        raise ValueError(
            f"Unknown model architecture '{architecture}'. "
            f"Expected one of {XRV_ARCHITECTURES + EFFICIENTNET_ARCHITECTURES}."
        )

    if pretrained and arch in XRV_ARCHITECTURES:
        try:
            return TorchXRayVisionClassifier(checkpoint_path=checkpoint_path)
        except Exception:
            logger.warning("TorchXRayVision model unavailable; falling back to untrained ThoracicClassifier",
                           exc_info=True)
            return ThoracicClassifier(num_classes=len(TARGET_PATHOLOGIES))

    model = ThoracicClassifier(num_classes=len(TARGET_PATHOLOGIES))
    if checkpoint_path and os.path.exists(checkpoint_path):
        state_dict = torch.load(checkpoint_path, map_location="cpu")
        model.load_state_dict(state_dict)
        model.is_real_weights = True
        model.weights_source = f"Local checkpoint: {os.path.basename(checkpoint_path)}"
    elif pretrained:
        logger.warning("ThoracicClassifier has no trained weights; predictions are not clinically meaningful. "
                       "Set MEDSHIELD_MODEL_CHECKPOINT_PATH or use MEDSHIELD_MODEL_ARCHITECTURE=torchxrayvision.")
    return model
