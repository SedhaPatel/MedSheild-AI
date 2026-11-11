from typing import List, Optional
import torch
import torch.nn as nn
import torchvision.models as models

TARGET_PATHOLOGIES: List[str] = [
    "Pneumonia",
    "Cardiomegaly",
    "Pleural Effusion",
    "Pneumothorax",
    "Atelectasis"
]

class ThoracicClassifier(nn.Module):
    """
    Multi-label convolutional classifier for chest radiography disease detection.
    Wraps EfficientNet-V2-S with multi-label Sigmoid output heads.
    """
    def __init__(self, num_classes: int = len(TARGET_PATHOLOGIES)):
        super().__init__()
        self.backbone = models.efficientnet_v2_s(weights=None)
        in_features = self.backbone.classifier[1].in_features
        # Replace classifier head
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(p=0.2, inplace=True),
            nn.Linear(in_features, num_classes)
        )
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits = self.backbone(x)
        return self.sigmoid(logits)

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone.features(x)

    def get_last_conv_layer(self) -> nn.Module:
        return self.backbone.features[-1]

    def get_last_conv_layer_name(self) -> str:
        return "backbone.features.7"

def build_thoracic_model(
    checkpoint_path: Optional[str] = None,
    pretrained: bool = False
) -> ThoracicClassifier:
    """
    Factory constructing the model and loading weights if available.
    """
    model = ThoracicClassifier(num_classes=len(TARGET_PATHOLOGIES))
    if checkpoint_path is not None:
        state_dict = torch.load(checkpoint_path, map_location="cpu")
        model.load_state_dict(state_dict)
    return model
