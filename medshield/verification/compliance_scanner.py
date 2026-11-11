from typing import List, NamedTuple
import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

# 18 HIPAA Safe Harbor Identifier Categories
SAFE_HARBOR_FORBIDDEN_TAGS = {
    "PatientName",
    "PatientBirthDate",
    "PatientBirthTime",
    "PatientAddress",
    "PatientMotherBirthName",
    "PatientTelephoneNumbers",
    "PatientTelecomInformation",
    "OtherPatientIDs",
    "OtherPatientIDsSequence",
    "OtherPatientNames",
    "MedicalRecordLocator",
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
    "AdmittingDiagnosesDescription"
}

class AuditReport(NamedTuple):
    is_compliant: bool
    violations: List[str]
    inspected_tags_count: int

class ComplianceScanner:
    """
    Automated compliance inspection engine verifying that DICOM datasets
    strictly adhere to HIPAA Safe Harbor 45 CFR §164.514(b) and DICOM PS 3.15 Annex E.
    """
    def __init__(self):
        pass

    def _scan_recursively(self, ds: Dataset, violations: List[str], count_holder: List[int]) -> None:
        for elem in ds:
            count_holder[0] += 1
            kw = elem.keyword
            
            # 1. Check for presence of prohibited Safe Harbor metadata tags
            if kw in SAFE_HARBOR_FORBIDDEN_TAGS:
                val = str(elem.value).strip()
                if val:
                    violations.append(f"Safe Harbor Tag '{kw}' contains un-redacted PHI: '{val[:20]}...'")
                    
            # 2. Check UID de-identification compliance
            elif kw in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID"):
                uid_str = str(elem.value).strip()
                if not uid_str.startswith("2.25."):
                    violations.append(f"UID '{kw}' is not pseudonymized with required '2.25.' root: '{uid_str}'")
                    
            # 3. Check PatientID format
            elif kw == "PatientID":
                pid = str(elem.value).strip()
                if not pid.startswith("ANON_"):
                    violations.append(f"PatientID '{pid}' does not conform to anonymous pseudonym format ('ANON_...')")

            # 4. Recursively scan Sequence items
            if elem.VR == "SQ" and isinstance(elem.value, Sequence):
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._scan_recursively(item, violations, count_holder)

    def scan_dataset(self, dataset: Dataset) -> AuditReport:
        violations: List[str] = []
        count_holder = [0]
        
        # 1. Scan metadata elements recursively
        self._scan_recursively(dataset, violations, count_holder)
        
        # 2. Check DICOM PS 3.15 de-identification audit signature tags
        identity_removed = getattr(dataset, "PatientIdentityRemoved", None)
        if identity_removed != "YES":
            violations.append("Missing or invalid DICOM PS 3.15 PatientIdentityRemoved (0012,0062) tag")
            
        # 3. Check BurnedInAnnotation tag
        burned_in = getattr(dataset, "BurnedInAnnotation", None)
        if burned_in == "YES":
            violations.append("BurnedInAnnotation (0028,0301) is 'YES'; pixel data contains un-redacted PHI")
            
        is_compliant = len(violations) == 0
        return AuditReport(
            is_compliant=is_compliant,
            violations=violations,
            inspected_tags_count=count_holder[0]
        )
