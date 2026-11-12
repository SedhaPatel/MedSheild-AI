from typing import Tuple
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from pydicom.dataset import Dataset

from medshield.utils.dicom_helpers import extract_pixel_array

class DICOMPreprocessor:
    """
    Normalizes raw DICOM pixel arrays into standardized float32 tensors
    for deep learning models, handling PhotometricInterpretation, dynamic range,
    and aspect-ratio preserving spatial transformations.
    """
    def __init__(
        self,
        target_size: Tuple[int, int] = (224, 224),
        normalization: str = "imagenet"
    ):
        self.target_size = target_size
        self.normalization = normalization.lower()
        self.transform = T.Compose([
            T.Resize(target_size),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def process(self, dataset: Dataset) -> Tuple[torch.Tensor, Image.Image]:
        arr = extract_pixel_array(dataset).astype(np.float32)
        photometric = getattr(dataset, "PhotometricInterpretation", "MONOCHROME2")
        
        if self.normalization == "xrv":
            # 1. Calibrate dynamic range for linear scaling without crushing contrast
            bits_stored = getattr(dataset, "BitsStored", None)
            if bits_stored is not None and int(bits_stored) > 0:
                bs = int(bits_stored)
                # If BitsStored is 16 but scan values fit in 12-bit (<= 4095), calibrate to 12-bit
                if bs == 16 and arr.max() <= 4095.0 and arr.max() > 255.0:
                    max_val = 4095.0
                elif bs <= 8 or (arr.max() <= 255.0 and bs <= 8):
                    max_val = 255.0
                else:
                    max_val = float((1 << bs) - 1)
            else:
                if arr.max() <= 255.0:
                    max_val = 255.0
                elif arr.max() <= 1023.0:
                    max_val = 1023.0
                elif arr.max() <= 4095.0:
                    max_val = 4095.0
                elif arr.max() <= 65535.0:
                    max_val = 65535.0
                else:
                    max_val = float(arr.max()) if arr.max() > 0 else 1.0

            if arr.max() > max_val:
                max_val = float(arr.max())
            if max_val <= 0:
                max_val = 1.0

            # 2. Invert MONOCHROME1 if needed
            if photometric == "MONOCHROME1":
                arr = max_val - arr
                arr = np.clip(arr, 0.0, max_val)

            # 3. Square center crop to prevent spatial distortion and ensure Grad-CAM alignment
            h, w = arr.shape[:2]
            min_dim = min(h, w)
            top = (h - min_dim) // 2
            left = (w - min_dim) // 2
            arr_cropped = arr[top : top + min_dim, left : left + min_dim]

            # 4. Normalize to [0.0, 1.0] and map to XRV [-1024.0, 1024.0]
            arr_norm = np.clip(arr_cropped / max_val, 0.0, 1.0)
            arr_xrv = (2.0 * arr_norm - 1.0) * 1024.0

            # 5. Convert to resized (1, 3, H, W) float32 tensor
            tensor_2d = torch.from_numpy(arr_xrv.astype(np.float32)).unsqueeze(0).unsqueeze(0)
            tensor_resized = torch.nn.functional.interpolate(
                tensor_2d,
                size=self.target_size,
                mode="bilinear",
                align_corners=False
            )
            tensor = tensor_resized.repeat(1, 3, 1, 1)

            # 6. Convert to matching (H, W) RGB PIL Image for visualization/heatmaps
            arr_uint8 = (arr_norm * 255.0).astype(np.uint8)
            pil_img_cropped = Image.fromarray(arr_uint8).convert("RGB")
            pil_img_resized = pil_img_cropped.resize(self.target_size, Image.Resampling.BILINEAR)

            return tensor, pil_img_resized

        else:
            # Default: ImageNet normalization
            if photometric == "MONOCHROME1":
                arr = arr.max() - arr
                
            p1, p99 = np.percentile(arr, 1), np.percentile(arr, 99)
            if p99 > p1:
                arr = np.clip(arr, p1, p99)
                norm_arr = ((arr - p1) / (p99 - p1) * 255.0).astype(np.uint8)
            else:
                norm_arr = np.zeros_like(arr, dtype=np.uint8)
                
            pil_img = Image.fromarray(norm_arr).convert("RGB")
            pil_img_resized = pil_img.resize(self.target_size, Image.Resampling.BILINEAR)
            tensor = self.transform(pil_img).unsqueeze(0)
            return tensor, pil_img_resized

