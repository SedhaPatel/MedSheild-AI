import numpy as np
import pytest
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian
from PIL import Image, ImageDraw

from medshield.utils.dicom_helpers import extract_pixel_array, write_pixel_array_to_dataset
from medshield.anonymization.pixel_cleaner import clean_pixel_annotations, detect_text_regions

def create_dicom_with_burned_in_text(has_text: bool = True) -> Dataset:
    ds = Dataset()
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    
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

