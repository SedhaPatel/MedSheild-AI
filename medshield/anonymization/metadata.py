import copy
import pydicom
from pydicom.dataset import Dataset
from pydicom.multival import MultiValue
from pydicom.sequence import Sequence

from medshield.anonymization.uid_hasher import generate_pseudonymized_uid
from medshield.anonymization.date_shifter import compute_patient_day_offset, shift_dicom_dates

# PS 3.15 Annex E Action X (Remove) and Action Z (Zero-length)
PS315_TAGS_TO_REMOVE = [
    "PatientName",
    "PatientBirthDate",
    "PatientBirthTime",
    "PatientSex",
    "PatientAge",
    "PatientAddress",
    "PatientMotherBirthName",
    "PatientTelephoneNumbers",
    "PatientTelecomInformation",
    "OtherPatientIDs",
    "OtherPatientIDsSequence",
    "OtherPatientNames",
    "MedicalRecordLocator",
    "EthnicGroup",
    "Occupation",
    "AdditionalPatientHistory",
    "PatientComments",
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
    "ReferringPhysicianName",
    "ReferringPhysicianAddress",
    "ReferringPhysicianTelephoneNumbers",
    "PhysiciansOfRecord",
    "PerformingPhysicianName",
    "NameOfPhysiciansReadingStudy",
    "OperatorsName",
    "AdmittingDiagnosesDescription",
    "StationName",
    "DeviceSerialNumber",
    "PlateID",
    "CustodialOrganizationSequence",
    "ProtocolName",
    "RequestedProcedureID",
    "ReasonForTheRequestedProcedure",
    "ScheduledProcedureStepDescription",
    "PerformedProcedureStepDescription"
]

# DICOM-defined UIDs (SOP classes, transfer syntaxes, coding schemes) identify *types*, not
# patients or instances, and must be preserved for the file to remain readable.
DICOM_STANDARD_UID_ROOT = "1.2.840.10008."
_NON_INSTANCE_UID_KEYWORDS = {"TransferSyntaxUID", "ImplementationClassUID", "CodingSchemeUID"}


def _is_instance_uid(keyword: str, value: str) -> bool:
    if not value or value.startswith(DICOM_STANDARD_UID_ROOT):
        return False
    return not (keyword.endswith("ClassUID") or keyword in _NON_INSTANCE_UID_KEYWORDS)


def _pseudonymize_uid_value(keyword: str, value, secret_salt: bytes):
    if isinstance(value, MultiValue):
        return [_pseudonymize_uid_value(keyword, v, secret_salt) for v in value]
    uid = str(value).strip()
    return generate_pseudonymized_uid(uid, secret_salt) if _is_instance_uid(keyword, uid) else value


PS315_TAGS_TO_ZERO = [
    "AccessionNumber",
    "StudyID"
]

def _sanitize_dataset_recursively(dataset: Dataset, secret_salt: bytes) -> None:
    """Purges PHI from elements, vendor-specific private tags, and nested sequences."""
    for elem in list(dataset):
        # 1. Purge vendor-specific private tags (odd group numbers per DICOM Part 5)
        if elem.tag.is_private or (elem.tag.group % 2 == 1):
            del dataset[elem.tag]
            continue
            
        # 2. Recursively process sequences
        if elem.VR == "SQ" and isinstance(elem.value, Sequence):
            for item in elem.value:
                if isinstance(item, Dataset):
                    _sanitize_dataset_recursively(item, secret_salt)
        elif elem.keyword in PS315_TAGS_TO_REMOVE:
            del dataset[elem.tag]
        elif elem.VR == "UI" and elem.value:
            # Action U: replace every instance UID (Study/Series/SOP, FrameOfReference, referenced
            # instances in sequences, ...) with a salted HMAC so cross-references stay consistent.
            elem.value = _pseudonymize_uid_value(elem.keyword, elem.value, secret_salt)
        elif elem.keyword in PS315_TAGS_TO_ZERO:
            elem.value = ""

def anonymize_dicom_metadata(
    dataset: Dataset,
    secret_salt: bytes,
    shift_dates: bool = True
) -> Dataset:
    """
    Applies DICOM PS 3.15 Annex E Basic Application Level Confidentiality Profile
    to strip HIPAA Safe Harbor identifiers and pseudonymize UIDs.
    """
    ds = copy.deepcopy(dataset)
    
    # 1. Compute patient offset before PatientID is stripped
    original_patient_id = str(getattr(ds, "PatientID", "") or "").strip() or "UNKNOWN_PATIENT"
    day_offset = compute_patient_day_offset(original_patient_id, secret_salt)
    
    # Assign deterministic anonymous patient ID
    anonymous_patient_id = f"ANON_{generate_pseudonymized_uid(original_patient_id, secret_salt)[5:17]}"
    ds.PatientID = anonymous_patient_id

    # 2-3. Purge PHI tags and pseudonymize all instance UIDs (Action U) recursively
    _sanitize_dataset_recursively(ds, secret_salt)

    # Keep File Meta Information consistent with the pseudonymized SOP Instance UID
    if hasattr(ds, "file_meta") and ds.file_meta is not None and "SOPInstanceUID" in ds:
        if "MediaStorageSOPInstanceUID" in ds.file_meta:
            ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    
    # Ensure PatientID wasn't deleted if in remove list
    ds.PatientID = anonymous_patient_id
    
    # 4. Apply temporal date shifting if requested
    if shift_dates:
        shift_dicom_dates(ds, day_offset)
        
    # 5. Add required DICOM de-identification audit tags
    ds.PatientIdentityRemoved = "YES"
    ds.DeidentificationMethod = "DICOM PS 3.15 Annex E / MedShield Salted HMAC"
    
    return ds

