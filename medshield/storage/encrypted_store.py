import os
import tempfile
from typing import Optional

class EncryptedStore:
    """
    Local filesystem encrypted object store simulating S3 / Azure Blob Storage.
    Enforces atomic writes via temporary files to avoid partial writes during crashes.
    """
    def __init__(self, storage_dir: str = "./storage/encrypted_studies"):
        self.storage_dir = os.path.abspath(storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _get_path(self, study_uid: str) -> str:
        # Sanitize study UID for filename
        safe_uid = "".join(c for c in study_uid if c.isalnum() or c in (".", "_", "-"))
        return os.path.join(self.storage_dir, f"{safe_uid}.enc")

    def save(self, study_uid: str, encrypted_bytes: bytes) -> str:
        target_path = self._get_path(study_uid)
        
        # Atomic write via temp file in same directory
        dir_name = os.path.dirname(target_path)
        with tempfile.NamedTemporaryFile(dir=dir_name, delete=False) as tmp:
            tmp.write(encrypted_bytes)
            tmp_path = tmp.name
            
        os.replace(tmp_path, target_path)
        return target_path

    def load(self, study_uid: str) -> Optional[bytes]:
        target_path = self._get_path(study_uid)
        if not os.path.exists(target_path):
            return None
        with open(target_path, "rb") as f:
            return f.read()

    def delete(self, study_uid: str) -> bool:
        target_path = self._get_path(study_uid)
        if os.path.exists(target_path):
            os.remove(target_path)
            return True
        return False

    def exists(self, study_uid: str) -> bool:
        return os.path.exists(self._get_path(study_uid))
