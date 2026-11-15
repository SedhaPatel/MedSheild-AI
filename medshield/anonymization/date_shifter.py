import hashlib
import hmac
from datetime import datetime, timedelta
import pydicom
from pydicom.dataset import Dataset
from pydicom.multival import MultiValue
from pydicom.sequence import Sequence

DATE_TAGS = [
    "StudyDate",
    "SeriesDate",
    "AcquisitionDate",
    "ContentDate",
    "InstanceCreationDate",
    "DateOfSecondaryCapture"
]

def compute_patient_day_offset(patient_id: str, master_pepper: bytes) -> int:
    """
    Computes a deterministic pseudorandom day offset for a patient between -365 and +365 days.
    Preserves exact temporal consistency across all longitudinal studies for the same patient.
    """
    if not patient_id:
        patient_id = "UNKNOWN_PATIENT"
        
    digest = hmac.new(master_pepper, patient_id.encode("utf-8"), hashlib.sha256).digest()
    int_val = int.from_bytes(digest[:8], byteorder="big")
    # Map to [-365, 365], avoid 0
    offset = (int_val % 730) - 365
    return offset if offset != 0 else 42

def _shift_date_string(value: str, offset_days: int) -> str:
    """Shifts the leading YYYYMMDD of a DA or DT value, preserving any time/offset suffix."""
    raw = str(value)
    stripped = raw.strip()
    if len(stripped) >= 8 and stripped[:8].isdigit():
        try:
            shifted = datetime.strptime(stripped[:8], "%Y%m%d") + timedelta(days=offset_days)
            return shifted.strftime("%Y%m%d") + stripped[8:]
        except ValueError:
            return raw
    return raw


def shift_dicom_dates(dataset: Dataset, offset_days: int) -> None:
    """
    Shifts every date (DA) and date-time (DT) attribute in the dataset by offset_days,
    maintaining intra-study and inter-study deltas. Operates recursively on nested sequences.
    DT values keep their time and UTC-offset suffix (only the YYYYMMDD part moves).
    """
    for elem in dataset:
        if elem.VR == "SQ" and isinstance(elem.value, Sequence):
            for item in elem.value:
                if isinstance(item, Dataset):
                    shift_dicom_dates(item, offset_days)
        elif (elem.VR in ("DA", "DT") or elem.keyword in DATE_TAGS) and elem.value not in (None, ""):
            if isinstance(elem.value, MultiValue):
                elem.value = [_shift_date_string(v, offset_days) for v in elem.value]
            else:
                elem.value = _shift_date_string(elem.value, offset_days)
