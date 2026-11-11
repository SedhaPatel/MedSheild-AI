import numpy as np
import pydicom
from pydicom.dataset import Dataset

def extract_pixel_array(dataset: Dataset) -> np.ndarray:
    """
    Extracts a 2D/3D writable numpy array from a DICOM dataset's raw PixelData.
    """
    if hasattr(dataset, "pixel_array") and dataset.pixel_array is not None:
        return dataset.pixel_array.copy()
        
    rows = int(dataset.Rows)
    cols = int(dataset.Columns)
    bits_allocated = int(getattr(dataset, "BitsAllocated", 16))
    pixel_rep = int(getattr(dataset, "PixelRepresentation", 0)) # 0 = unsigned, 1 = signed
    
    if bits_allocated == 8:
        dtype = np.uint8 if pixel_rep == 0 else np.int8
    elif bits_allocated == 16:
        dtype = np.uint16 if pixel_rep == 0 else np.int16
    elif bits_allocated == 32:
        dtype = np.uint32 if pixel_rep == 0 else np.int32
    else:
        dtype = np.uint16
        
    arr = np.frombuffer(dataset.PixelData, dtype=dtype).copy()
    expected_size = rows * cols
    if arr.size >= expected_size:
        arr = arr[:expected_size].reshape((rows, cols))
    else:
        raise ValueError(f"PixelData buffer size ({arr.size}) does not match expected rows*cols ({expected_size})")
        
    return arr

def write_pixel_array_to_dataset(dataset: Dataset, arr: np.ndarray) -> None:
    """
    Writes a numpy array back into a DICOM dataset's PixelData attribute.
    """
    dataset.Rows, dataset.Columns = arr.shape[:2]
    dataset.PixelData = arr.tobytes()
