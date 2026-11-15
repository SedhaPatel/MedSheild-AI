import io

import numpy as np
import pydicom
from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian


def read_dicom_bytes(data: bytes) -> Dataset:
    """
    Parses an in-memory DICOM file. pydicom keeps the source buffer on `dataset.buffer`, so every
    deepcopy in the de-identification pipeline would duplicate the whole upload; the parsed
    dataset no longer needs it (nothing is read lazily), so the reference is dropped.
    """
    ds = pydicom.dcmread(io.BytesIO(data), force=True)
    if getattr(ds, "buffer", None) is not None:
        ds.buffer = None
    return ds

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

def _box_downsample(frame: np.ndarray, k: int) -> np.ndarray:
    """Averages k x k pixel blocks of a (rows, cols) or (rows, cols, samples) frame.

    Works in strips of k rows so no full-size floating-point copy of the image is ever held.
    """
    out_h, out_w = frame.shape[0] // k, frame.shape[1] // k
    out = np.empty((out_h, out_w) + frame.shape[2:], dtype=frame.dtype)
    rounding = np.issubdtype(frame.dtype, np.integer)
    for i in range(out_h):
        strip = frame[i * k:(i + 1) * k, :out_w * k].astype(np.float32)
        block_mean = strip.reshape((k, out_w, k) + frame.shape[2:]).mean(axis=(0, 2))
        out[i] = np.rint(block_mean) if rounding else block_mean
    return out


def downscale_dataset(dataset: Dataset, max_dim: int) -> int:
    """
    Shrinks the image in place by an integer factor so neither side exceeds max_dim, averaging
    k x k pixel blocks (anti-aliased, keeps the pixel data type). Pixel spacing tags are scaled to
    match. Used by low-memory deployments; the model itself only sees 224 x 224 pixels.

    Returns the factor applied (1 when nothing changed or max_dim <= 0).
    """
    if max_dim <= 0 or "PixelData" not in dataset:
        return 1
    rows, cols = int(dataset.Rows), int(dataset.Columns)
    k = -(-max(rows, cols) // max_dim)  # ceil division
    if k <= 1:
        return 1

    arr = extract_pixel_array(dataset)
    frames = int(getattr(dataset, "NumberOfFrames", 1) or 1)
    if frames > 1:
        small = np.stack([_box_downsample(frame, k) for frame in arr])
    else:
        small = _box_downsample(arr, k)
    del arr
    write_pixel_array_to_dataset(dataset, small)

    for tag in ("PixelSpacing", "ImagerPixelSpacing", "NominalScannedPixelSpacing"):
        spacing = getattr(dataset, tag, None)
        if spacing is not None:
            try:
                setattr(dataset, tag, [f"{float(v) * k:.6g}" for v in spacing])
            except (TypeError, ValueError):
                pass
    return k


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
