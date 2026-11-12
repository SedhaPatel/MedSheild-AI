import numpy as np
import pydicom
from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian

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
    Writes a numpy array back into a DICOM dataset's PixelData attribute as native
    (uncompressed) pixel data.
    """
    samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
    is_color = samples > 1 and arr.ndim >= 3 and arr.shape[-1] == samples
    frame_dims = arr.shape[-3:-1] if is_color else arr.shape[-2:]
    dataset.Rows, dataset.Columns = (int(d) for d in frame_dims)
    if is_color:
        # pydicom decodes color to interleaved RGB; record that layout for the raw bytes
        dataset.PhotometricInterpretation = "RGB"
        dataset.PlanarConfiguration = 0
    dataset.PixelData = arr.tobytes()

    # Raw bytes are uncompressed; a leftover compressed transfer syntax would corrupt the file
    file_meta = getattr(dataset, "file_meta", None)
    if file_meta is not None:
        ts = getattr(file_meta, "TransferSyntaxUID", None)
        if ts is not None and getattr(ts, "is_compressed", False):
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
