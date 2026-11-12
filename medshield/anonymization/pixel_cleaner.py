import copy
from typing import List, Optional, Tuple
import numpy as np
from pydicom.dataset import Dataset
from scipy.ndimage import binary_dilation, find_objects, label, white_tophat

from medshield.utils.dicom_helpers import extract_pixel_array, write_pixel_array_to_dataset

# Burned-in annotations (laterality markers, patient name/ID/DOB, exposure and timestamps)
# are placed in the top 25% / bottom 20% bands of radiographs and ultrasound frames.
TOP_BAND_FRACTION = 0.25
BOTTOM_BAND_START = 0.80

# Stage A: solid or isolated overlays (e.g. "L"/"R" markers, white label boxes)
OVERLAY_INTENSITY = 0.75      # normalized intensity of overlay pixels
OVERLAY_MIN_CONTRAST = 0.45   # overlay mean minus surrounding-ring median

# Stage B: anti-aliased text drawn over gray anatomy
STROKE_TOPHAT_SIZE = 7        # removes structures wider than a text stroke
STROKE_MIN_RESPONSE = 0.12    # per-pixel top-hat response to count as a stroke pixel
TEXT_MIN_STROKE_CONTRAST = 0.28  # mean stroke response of a text line; bone edges score ~0.14-0.21


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


def _normalize(arr: np.ndarray) -> Optional[np.ndarray]:
    """Robustly maps intensities to [0, 1] (0.5/99.5 percentiles), or None for flat images."""
    n = arr.astype(np.float32)
    lo, hi = float(np.percentile(n, 0.5)), float(np.percentile(n, 99.5))
    if hi <= lo:
        lo, hi = float(n.min()), float(n.max())
    if hi <= lo:
        return None
    return np.clip((n - lo) / (hi - lo), 0.0, 1.0)


def _side_medians(norm: np.ndarray, ys: slice, xs: slice, pad: int) -> List[float]:
    """Median intensity of the strips just above, below, left and right of a box.

    Sides that lie on the image border have no strip and are omitted.
    """
    h, w = norm.shape
    strips = [
        norm[max(0, ys.start - pad):ys.start, xs.start:xs.stop],   # above
        norm[ys.stop:min(h, ys.stop + pad), xs.start:xs.stop],     # below
        norm[ys.start:ys.stop, max(0, xs.start - pad):xs.start],   # left
        norm[ys.start:ys.stop, xs.stop:min(w, xs.stop + pad)],     # right
    ]
    return [float(np.median(strip)) for strip in strips if strip.size > 0]


def _detect_solid_overlays(norm: np.ndarray, band: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Bright overlays that stand out sharply from their surroundings on every side.

    Bright anatomy (clavicles, shoulders) is bordered by similarly bright soft tissue on at least one
    side. Requiring contrast on all sides also protects anatomy that merely touches a black border
    or letterbox band (dark on one side only), which is common in screenshots and exported JPEGs.
    """
    h, w = norm.shape
    labeled, _ = label((norm > OVERLAY_INTENSITY) & band)
    boxes = []
    for idx, sl in enumerate(find_objects(labeled), start=1):
        if sl is None:
            continue
        ys, xs = sl
        box_h, box_w = ys.stop - ys.start, xs.stop - xs.start
        if not (4 <= box_h <= int(h * 0.20) and 4 <= box_w <= int(w * 0.90)):
            continue
        component_mean = float(norm[sl][labeled[sl] == idx].mean())
        sides = _side_medians(norm, ys, xs, max(3, box_h // 2))
        if sides and all(component_mean - side >= OVERLAY_MIN_CONTRAST for side in sides):
            boxes.append((xs.start, ys.start, xs.stop, ys.stop))
    return boxes


def _detect_text_lines(norm: np.ndarray, band: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Rows of thin, high-contrast strokes, i.e. rendered text over gray image content."""
    h, _ = norm.shape
    tophat = white_tophat(norm, size=(STROKE_TOPHAT_SIZE, STROKE_TOPHAT_SIZE))
    strokes = (tophat > STROKE_MIN_RESPONSE) & band

    max_glyph_h = max(6, int(h * 0.05))
    stroke_labels, _ = label(strokes)
    glyphs = np.zeros_like(strokes)
    for idx, sl in enumerate(find_objects(stroke_labels), start=1):
        if sl is None:
            continue
        glyph_h, glyph_w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if 3 <= glyph_h <= max_glyph_h and glyph_w <= max_glyph_h * 6:
            glyphs[sl] |= stroke_labels[sl] == idx

    # Merge horizontally adjacent glyphs into candidate text lines
    gap = max(3, int(round(h * 0.012)))
    line_labels, _ = label(binary_dilation(glyphs, structure=np.ones((3, 2 * gap + 1), dtype=bool)))
    boxes = []
    for idx, sl in enumerate(find_objects(line_labels), start=1):
        if sl is None:
            continue
        ys, xs = sl
        line_h, line_w = ys.stop - ys.start, xs.stop - xs.start
        line_glyphs = glyphs[sl] & (line_labels[sl] == idx)
        n_glyphs = label(line_glyphs)[1]
        is_line_shaped = line_h <= max_glyph_h + 4 and (
            (n_glyphs >= 2 and line_w >= 1.5 * line_h) or line_w >= 2.5 * line_h
        )
        if is_line_shaped and float(tophat[sl][line_glyphs].mean()) >= TEXT_MIN_STROKE_CONTRAST:
            boxes.append((xs.start, ys.start, xs.stop, ys.stop))
    return boxes


def detect_text_regions(
    arr: np.ndarray,
    dilation_pct: float = 0.15
) -> List[Tuple[int, int, int, int]]:
    """
    Detects burned-in text / overlay annotations in the top and bottom margin bands of a 2D image
    (bright-on-dark display convention). Returns dilated (x_min, y_min, x_max, y_max) boxes.

    Two complementary detectors:
      A. Solid/isolated bright overlays with high contrast against their surroundings.
      B. Text lines: rows of thin strokes found via a white top-hat transform, accepted only when
         stroke contrast is text-like (anatomical edges produce weaker responses).
    """
    h, w = arr.shape[:2]
    norm = _normalize(arr)
    if norm is None:
        return []

    band = np.zeros((h, w), dtype=bool)
    band[: int(h * TOP_BAND_FRACTION), :] = True
    band[int(h * BOTTOM_BAND_START):, :] = True

    raw_boxes = _detect_solid_overlays(norm, band) + _detect_text_lines(norm, band)
    return [dilate_bounding_box(b, w, h, dilation_pct=dilation_pct) for b in raw_boxes]


def _detection_plane(arr: np.ndarray, photometric: str) -> Optional[np.ndarray]:
    """Collapses the pixel array to one 2D plane where annotations appear bright."""
    if arr.ndim == 2:
        plane = arr
    elif arr.ndim == 3 and arr.shape[-1] in (3, 4):   # single-frame color
        plane = arr[..., :3].mean(axis=-1)
    elif arr.ndim == 3:                               # multi-frame grayscale
        plane = arr.max(axis=0)
    else:
        return None
    if photometric == "MONOCHROME1":
        # Displayed white is stored as low values; invert so overlays are bright for detection
        plane = plane.max() - plane.astype(np.float32)
    return plane


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

    photometric = str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2"))
    plane = _detection_plane(arr, photometric)
    boxes = detect_text_regions(plane, dilation_pct=dilation_pct) if plane is not None else []

    if boxes:
        # Black out in display terms: MONOCHROME1 displays its maximum value as black
        fill = arr.max() if photometric == "MONOCHROME1" else 0
        multi_frame = arr.ndim == 3 and arr.shape[-1] not in (3, 4)
        for (x_min, y_min, x_max, y_max) in boxes:
            if multi_frame:
                arr[:, y_min:y_max, x_min:x_max] = fill
            else:
                arr[y_min:y_max, x_min:x_max] = fill

        write_pixel_array_to_dataset(ds, arr)
        ds.BurnedInAnnotation = "NO"
        return ds, True

    ds.BurnedInAnnotation = "NO"
    return ds, False
