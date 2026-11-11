import hashlib
import hmac
from datetime import datetime, timedelta
import pydicom
from pydicom.dataset import Dataset
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

def shift_dicom_dates(dataset: Dataset, offset_days: int) -> None:
    """
    Shifts all date attributes in the dataset by offset_days, maintaining intra-study and inter-study deltas.
    Operates recursively on nested sequences.
    """
    for elem in dataset:
        if elem.VR == "SQ" and isinstance(elem.value, Sequence):
            for item in elem.value:
                if isinstance(item, Dataset):
                    shift_dicom_dates(item, offset_days)
        elif elem.keyword in DATE_TAGS:
            date_str = str(elem.value).strip()
            if len(date_str) == 8 and date_str.isdigit():
                try:
                    dt = datetime.strptime(date_str, "%Y%m%d")
                    shifted_dt = dt + timedelta(days=offset_days)
                    elem.value = shifted_dt.strftime("%Y%m%d")
                except ValueError:
                    pass

