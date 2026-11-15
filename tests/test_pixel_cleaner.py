import numpy as np
import pytest
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian
from PIL import Image, ImageDraw

from medshield.utils.dicom_helpers import extract_pixel_array, write_pixel_array_to_dataset
from medshield.anonymization.pixel_cleaner import clean_pixel_annotations, detect_text_regions

def create_dicom_with_burned_in_text(has_text: bool = True) -> Dataset:
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.6.1"
    file_meta.MediaStorageSOPInstanceUID = "2.25.123456789"

    ds = Dataset()
    ds.file_meta = file_meta
    
    ds.Rows = 256
    ds.Columns = 256
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Modality = "US" # Ultrasound commonly has burned-in annotations
    ds.BurnedInAnnotation = "YES" if has_text else "NO"
    
    # Create base simulated image (e.g. tissue background with mid-gray)
    img = Image.new("I;16", (256, 256), color=1500)
    
    if has_text:
        # Draw high-contrast text on top margin (e.g. y: 10 to 30)
        draw = ImageDraw.Draw(img)
        # Draw white text blocks simulating burned-in characters
        # Draw text or high-contrast block representing "MRN: 99401"
        draw.rectangle([(20, 10), (120, 25)], fill=60000)
    
    arr = np.array(img, dtype=np.uint16)
    ds.PixelData = arr.tobytes()
    return ds

def test_extract_and_write_pixel_array():
    ds = create_dicom_with_burned_in_text(has_text=False)
    arr = extract_pixel_array(ds)
    assert arr.shape == (256, 256)
    assert arr.dtype == np.uint16
    assert arr[100, 100] == 1500
    
    arr[50, 50] = 3000
    write_pixel_array_to_dataset(ds, arr)
    updated_arr = extract_pixel_array(ds)
    assert updated_arr[50, 50] == 3000

def test_detect_text_regions():
    ds = create_dicom_with_burned_in_text(has_text=True)
    arr = extract_pixel_array(ds)
    boxes = detect_text_regions(arr)
    assert len(boxes) >= 1
    # Bounding box should cover the region around x: 20..120, y: 10..25
    x_min, y_min, x_max, y_max = boxes[0]
    assert x_min <= 20 and x_max >= 120
    assert y_min <= 10 and y_max >= 25

def test_clean_pixel_annotations_redaction():
    ds = create_dicom_with_burned_in_text(has_text=True)
    cleaned_ds, was_redacted = clean_pixel_annotations(ds)
    
    assert was_redacted is True
    assert cleaned_ds.BurnedInAnnotation == "NO"
    
    # Check that the text region is zeroed out
    arr = extract_pixel_array(cleaned_ds)
    assert arr[15, 50] == 0  # Was previously 60000
    # Background outside margin should be preserved
    assert arr[100, 100] == 1500

def test_clean_pixel_annotations_clean_image():
    ds = create_dicom_with_burned_in_text(has_text=False)
    cleaned_ds, was_redacted = clean_pixel_annotations(ds)
    
    assert was_redacted is False
    assert cleaned_ds.BurnedInAnnotation == "NO"
    arr = extract_pixel_array(cleaned_ds)
    assert arr[100, 100] == 1500



# --- Text-specific detection: real samples & anatomy preservation -------------------------

import pydicom as _pydicom
from PIL import ImageFont


def _redacted_mask(ds):
    cleaned, _ = clean_pixel_annotations(ds)
    return extract_pixel_array(cleaned) != extract_pixel_array(ds)


def _overlaps(mask, x0, y0, x1, y1):
    return bool(mask[y0:y1, x0:x1].any())


def test_sample_with_burned_in_phi_text_is_redacted():
    # patient_03 has patient ID/name, DOB "10.02.1931", "[F] Age: 92", a timestamp,
    # "RT supine" and exposure text rendered in light gray over gray anatomy.
    ds = _pydicom.dcmread("test_samples/patient_03_cardiomegaly.dcm")
    mask = _redacted_mask(ds)
    for x0, y0, x1, y1 in [(5, 10, 125, 26), (525, 15, 565, 20), (2, 430, 20, 438), (2, 448, 45, 456), (270, 477, 312, 488)]:
        region = mask[y0:y1, x0:x1]
        assert region.mean() > 0.9, f"text region {(x0, y0, x1, y1)} not redacted"


def test_laterality_markers_redacted_without_touching_anatomy():
    for name, marker in [("patient_01_pneumonia", (3, 7, 15, 20)), ("patient_02_effusion", (27, 7, 36, 20))]:
        ds = _pydicom.dcmread(f"test_samples/{name}.dcm")
        mask = _redacted_mask(ds)
        x0, y0, x1, y1 = marker
        assert mask[y0:y1, x0:x1].mean() > 0.9, f"{name}: marker not redacted"
        # Nothing outside a small neighbourhood of the marker may be altered
        outside = mask.copy()
        outside[: y1 + 10, : x1 + 10] = False
        assert not outside.any(), f"{name}: anatomy outside the marker was altered"


def test_rendered_text_over_gray_background_is_redacted():
    img = Image.new("L", (512, 512), color=110)
    draw = ImageDraw.Draw(img)
    # Soft anatomical gradient so the background is not flat
    for y in range(512):
        draw.line([(0, y), (511, y)], fill=90 + y // 8)
    font = ImageFont.load_default()
    draw.text((12, 14), "DOE^JANE  MRN 88412  DOB 1961-03-02", fill=235, font=font)
    arr = np.array(img, dtype=np.uint8)
    boxes = detect_text_regions(arr)
    assert boxes, "rendered text was not detected"
    x_min = min(b[0] for b in boxes); y_min = min(b[1] for b in boxes)
    x_max = max(b[2] for b in boxes); y_max = max(b[3] for b in boxes)
    assert x_min <= 14 and y_min <= 16 and x_max >= 150 and y_max >= 22


def test_bright_anatomy_like_structures_are_not_redacted():
    # Smooth bright band (clavicle-like) over bright soft tissue in the top margin
    yy, xx = np.mgrid[0:400, 0:400].astype(np.float32)
    tissue = 120 + 40 * np.exp(-((yy - 60) ** 2) / (2 * 40.0 ** 2))
    clavicle = 90 * np.exp(-((yy - (50 + 0.15 * xx)) ** 2) / (2 * 7.0 ** 2))
    arr = np.clip(tissue + clavicle, 0, 255).astype(np.uint8)
    assert detect_text_regions(arr) == []


def test_monochrome1_overlay_detected_and_blacked_out_in_display_terms():
    ds = create_dicom_with_burned_in_text(has_text=False)
    arr = np.full((256, 256), 60000, dtype=np.uint16)   # MONOCHROME1: high = dark
    arr[10:26, 20:121] = 500                            # displayed as bright white block
    write_pixel_array_to_dataset(ds, arr)
    ds.PhotometricInterpretation = "MONOCHROME1"
    cleaned, was_redacted = clean_pixel_annotations(ds)
    assert was_redacted is True
    out = extract_pixel_array(cleaned)
    assert out[15, 50] == arr.max()      # rendered as black on a MONOCHROME1 display
    assert out[150, 150] == 60000


@pytest.mark.parametrize("sample", ["patient_01_pneumonia", "patient_02_effusion", "patient_03_cardiomegaly"])
@pytest.mark.parametrize("band", [40, 80])
def test_anatomy_touching_a_letterbox_band_is_not_redacted(sample, band):
    # Exported/screenshot X-rays often have black letterbox bands. Shoulders and lower chest that
    # touch a band are dark on that side only and must not be mistaken for a bright overlay.
    arr = _pydicom.dcmread(f"test_samples/{sample}.dcm").pixel_array
    padded = np.pad(arr, ((band, band), (0, 0)))
    h, w = padded.shape
    for x0, y0, x1, y1 in detect_text_regions(padded):
        # Only marker/text-sized regions may be redacted, never broad anatomical areas
        assert (x1 - x0) <= 0.4 * w and (y1 - y0) <= 0.1 * h, (sample, band, (x0, y0, x1, y1))
