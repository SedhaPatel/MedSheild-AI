from typing import Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

class GradCAM:
    """
    Gradient-weighted Class Activation Mapping (Grad-CAM) for deep convolutional networks.
    Computes visual saliency heatmaps highlighting the anatomical regions influencing
    a specific pathology prediction.
    """
    def __init__(self, model: nn.Module, target_layer_name: Optional[str] = None):
        self.model = model
        self.model.eval()
        
        # Locate target layer
        if hasattr(model, "get_last_conv_layer"):
            self.target_layer = model.get_last_conv_layer()
        else:
            # Fallback to last conv layer in features
            self.target_layer = model.backbone.features[-1]
            
        self.activations: Optional[torch.Tensor] = None
        self.gradients: Optional[torch.Tensor] = None
        
        # Register hooks
        self._register_hooks()

    def _register_hooks(self) -> None:
        def forward_hook(module, input, output):
            self.activations = output

        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0]

        self.target_layer.register_forward_hook(forward_hook)
        self.target_layer.register_full_backward_hook(backward_hook)

    def generate_heatmap(self, input_tensor: torch.Tensor, class_idx: int) -> np.ndarray:
        """
        Generates a 2D numpy heatmap normalized in [0.0, 1.0] for the given class index.
        """
        self.model.zero_grad()
        # Enable gradients for the input and forward pass even during eval
        input_tensor = input_tensor.clone().detach().requires_grad_(True)
        
        output = self.model(input_tensor)
        score = output[0, class_idx]
        score.backward(retain_graph=True)
        
        if self.gradients is None or self.activations is None:
            # Fallback to uniform heatmap if hooks failed
            return np.zeros((input_tensor.shape[2], input_tensor.shape[3]), dtype=np.float32)
            
        # Global Average Pooling of gradients across spatial dimensions
        weights = torch.mean(self.gradients, dim=(2, 3), keepdim=True)
        
        # Weighted combination of feature maps
        cam = torch.sum(weights * self.activations, dim=1, keepdim=True)
        cam = F.relu(cam)
        
        # Interpolate to match input spatial dimensions
        h, w = input_tensor.shape[2], input_tensor.shape[3]
        cam = F.interpolate(cam, size=(h, w), mode="bilinear", align_corners=False)
        
        cam_arr = cam.squeeze().cpu().detach().numpy()
        
        # Min-max normalization to [0.0, 1.0]
        cam_min, cam_max = cam_arr.min(), cam_arr.max()
        if cam_max > cam_min:
            cam_arr = (cam_arr - cam_min) / (cam_max - cam_min)
        else:
            cam_arr = np.zeros_like(cam_arr)
            
        return cam_arr.astype(np.float32)

def overlay_heatmap(
    heatmap: np.ndarray,
    original_img: Image.Image,
    alpha: float = 0.5
) -> Image.Image:
    """
    Overlays a 2D float heatmap onto a PIL RGB image with pseudo-coloring.
    """
    h, w = original_img.size[1], original_img.size[0]
    if heatmap.shape != (h, w):
        heatmap_img = Image.fromarray((heatmap * 255).astype(np.uint8)).resize(
            (w, h), Image.Resampling.BILINEAR
        )
        heatmap = np.array(heatmap_img) / 255.0

    # Colorize heatmap: Red for high, Yellow for medium, Blue for low
    colored_heatmap = np.zeros((h, w, 3), dtype=np.uint8)
    colored_heatmap[..., 0] = (np.clip(2.0 * heatmap, 0, 1) * 255).astype(np.uint8) # Red
    colored_heatmap[..., 1] = (np.clip(2.0 * (1 - np.abs(heatmap - 0.5)), 0, 1) * 255).astype(np.uint8) # Green
    colored_heatmap[..., 2] = (np.clip(2.0 * (0.5 - heatmap), 0, 1) * 255).astype(np.uint8) # Blue

    heatmap_pil = Image.fromarray(colored_heatmap)
    blended = Image.blend(original_img.convert("RGB"), heatmap_pil, alpha=alpha)
    return blended
