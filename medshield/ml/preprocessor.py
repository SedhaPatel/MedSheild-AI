from typing import Tuple
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from pydicom.dataset import Dataset

from medshield.utils.dicom_helpers import extract_pixel_array

class DICOMPreprocessor:
    """
    Normalizes raw 12-to-16-bit DICOM pixel arrays into standardized float32 tensors
    for deep learning models, handling PhotometricInterpretation, windowing, and CLAHE.
    """
    def __init__(self, target_size: Tuple[int, int] = (224, 224)):
        self.target_size = target_size
        self.transform = T.Compose([
            T.Resize(target_size),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def process(self, dataset: Dataset) -> Tuple[torch.Tensor, Image.Image]:
        arr = extract_pixel_array(dataset).astype(np.float32)
        
        # 1. Handle MONOCHROME1 (Inverted X-rays where bone is dark)
        photometric = getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")
        if photometric == "MONOCHROME1":
            arr = arr.max() - arr
            
        # 2. Windowing / percentile clipping to remove scanner artifacts
        p1, p99 = np.percentile(arr, 1), np.percentile(arr, 99)
        if p99 > p1:
            arr = np.clip(arr, p1, p99)
            norm_arr = ((arr - p1) / (p99 - p1) * 255.0).astype(np.uint8)
        else:
            norm_arr = np.zeros_like(arr, dtype=np.uint8)
            
        # 3. Convert to 3-channel PIL RGB image
        pil_img = Image.fromarray(norm_arr).convert("RGB")
        pil_img_resized = pil_img.resize(self.target_size, Image.Resampling.BILINEAR)
        
        # 4. Convert to normalized PyTorch tensor (1, 3, H, W)
        tensor = self.transform(pil_img).unsqueeze(0)
        return tensor, pil_img_resized

