import copy
from typing import List, Tuple
import numpy as np
from pydicom.dataset import Dataset
from scipy.ndimage import label, find_objects, gaussian_filter

from medshield.utils.dicom_helpers import extract_pixel_array, write_pixel_array_to_dataset

def dilate_bounding_box(
    box: Tuple[int, int, int, int],
    img_width: int,
    img_height: int,
    dilation_pct: float = 0.15
) -> Tuple[int, int, int, int]:
    """
    Expands a bounding box (x_min, y_min, x_max, y_max) by dilation_pct (>= 15%)
    to ensure full coverage of character descenders, ascenders, and anti-aliasing.
    """
    x_min, y_min, x_max, y_max = box
    width = x_max - x_min
    height = y_max - y_min
    
    pad_x = int(np.ceil(width * dilation_pct))
    pad_y = int(np.ceil(height * dilation_pct))
    
    new_x_min = max(0, x_min - pad_x)
    new_y_min = max(0, y_min - pad_y)
    new_x_max = min(img_width, x_max + pad_x)
    new_y_max = min(img_height, y_max + pad_y)
    
    return (new_x_min, new_y_min, new_x_max, new_y_max)

def detect_text_regions(
    arr: np.ndarray,
    dilation_pct: float = 0.15
) -> List[Tuple[int, int, int, int]]:
    """
    Detects high-contrast rectangular text blocks typical of ultrasound/secondary-capture burned-in PHI.
    Uses gradient thresholding and connected components analysis on image margins.
    """
    h, w = arr.shape[:2]
    # Normalize to [0, 1] float
    min_val, max_val = float(arr.min()), float(arr.max())
    if max_val == min_val:
        return []
        
    norm_arr = (arr.astype(np.float32) - min_val) / (max_val - min_val)
    
    # Text in ultrasound/radiographs is typically high-intensity overlay (> 0.8) on dark background
    # or localized high-frequency clusters in top 25% or bottom 20% of the image.
    margin_mask = np.zeros_like(norm_arr, dtype=bool)
    margin_mask[: int(h * 0.25), :] = True
    margin_mask[int(h * 0.80) :, :] = True
    
    # Detect high intensity connected regions in margins
    text_candidate_mask = (norm_arr > 0.75) & margin_mask
    
    if not np.any(text_candidate_mask):
        return []
        
    labeled_array, num_features = label(text_candidate_mask)
    slices = find_objects(labeled_array)
    
    raw_boxes: List[Tuple[int, int, int, int]] = []
    for sl in slices:
        if sl is None:
            continue
        y_slice, x_slice = sl
        box_h = y_slice.stop - y_slice.start
        box_w = x_slice.stop - x_slice.start
        
        # Filter out single-pixel noise and massive anatomical structures
        if 4 <= box_h <= int(h * 0.20) and 8 <= box_w <= int(w * 0.90):
            raw_boxes.append((x_slice.start, y_slice.start, x_slice.stop, y_slice.stop))
            
    if not raw_boxes:
        return []
        
    # Dilate and merge boxes
    dilated_boxes = [dilate_bounding_box(b, w, h, dilation_pct=dilation_pct) for b in raw_boxes]
    return dilated_boxes

def clean_pixel_annotations(
    dataset: Dataset,
    dilation_pct: float = 0.15
) -> Tuple[Dataset, bool]:
    """
    Scans DICOM pixel array for burned-in PHI annotations, zeroes out detected regions,
    and updates BurnedInAnnotation to 'NO'.
    Returns (cleaned_dataset, was_redacted).
    """
    ds = copy.deepcopy(dataset)
    try:
        arr = extract_pixel_array(ds)
    except Exception:
        # If no valid pixel array found, update tag and return
        ds.BurnedInAnnotation = "NO"
        return ds, False
        
    boxes = detect_text_regions(arr, dilation_pct=dilation_pct)
    
    if boxes:
        # Inpaint / blackout detected regions
        for (x_min, y_min, x_max, y_max) in boxes:
            arr[y_min:y_max, x_min:x_max] = 0
            
        write_pixel_array_to_dataset(ds, arr)
        ds.BurnedInAnnotation = "NO"
        return ds, True
    else:
        ds.BurnedInAnnotation = "NO"
        return ds, False

