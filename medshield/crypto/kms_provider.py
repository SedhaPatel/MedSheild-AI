import abc
import base64
import json
import os
import secrets
import tempfile
import threading
from typing import Dict, Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class KMSError(Exception):
    """Base exception for KMS errors."""
    pass

class KeyNotFoundError(KMSError):
    """Raised when the specified key ID does not exist."""
    pass

class KeyRevokedError(KMSError):
    """Raised when attempting to use a revoked/crypto-shredded key."""
    pass

class KMSProvider(abc.ABC):
    @abc.abstractmethod
    def generate_data_key(self, key_id: str) -> Tuple[bytes, bytes]:
        """Returns (plaintext_dek, ciphertext_dek)."""
        pass

    @abc.abstractmethod
    def decrypt_data_key(self, key_id: str, ciphertext_dek: bytes) -> bytes:
        """Decrypts ciphertext_dek and returns plaintext_dek."""
        pass

class LocalKMSProvider(KMSProvider):
    """
    Simulated Hardware Security Module (HSM) / KMS conforming to FIPS 140-3 Level 3 interfaces.
    Maintains Master Key Encryption Keys (KEKs) in memory with lifecycle management and revocation.

    By default keys exist only in process memory and are lost on restart (every stored study then
    becomes undecryptable). Pass ``keystore_path`` (MEDSHIELD_KMS_KEYSTORE_PATH) to persist KEKs to a
    0600 JSON file for local development. Revoked keys are persisted as tombstones with no key
    material, so crypto-shredding survives restarts. A keystore file on the same disk as the
    ciphertext weakens at-rest protection; use a real KMS/HSM in production.
    """
    def __init__(self, keystore_path: Optional[str] = None):
        self._keys: Dict[str, bytes] = {}
        self._revoked: Dict[str, bool] = {}
        self._keystore_path = os.path.abspath(keystore_path) if keystore_path else None
        self._lock = threading.Lock()
        if self._keystore_path:
            self._load_keystore()

    def _load_keystore(self) -> None:
        if not os.path.exists(self._keystore_path):
            return
        with open(self._keystore_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key_id, entry in data.get("keys", {}).items():
            revoked = bool(entry.get("revoked", False))
            self._revoked[key_id] = revoked
            self._keys[key_id] = b"\x00" * 32 if revoked else base64.b64decode(entry["kek"])

    def _persist(self) -> None:
        if not self._keystore_path:
            return
        entries = {
            key_id: ({"revoked": True} if self._revoked.get(key_id) else
                     {"revoked": False, "kek": base64.b64encode(kek).decode("ascii")})
            for key_id, kek in self._keys.items()
        }
        directory = os.path.dirname(self._keystore_path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".kms-", suffix=".tmp")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "keys": entries}, f)
            os.replace(tmp_path, self._keystore_path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def create_master_key(self, key_alias: str) -> str:
        key_id = f"arn:medshield:kms:local:key/{key_alias}"
        with self._lock:
            # Generate 256-bit (32 bytes) master KEK
            self._keys[key_id] = AESGCM.generate_key(bit_length=256)
            self._revoked[key_id] = False
            self._persist()
        return key_id

    def revoke_key(self, key_id: str) -> None:
        """Executes cryptographic erasure (Crypto-Shredding) for the key."""
        with self._lock:
            if key_id not in self._keys:
                raise KeyNotFoundError(f"Key {key_id} not found")
            self._revoked[key_id] = True
            # Overwrite key material in memory (and drop it from the persisted keystore)
            self._keys[key_id] = b"\x00" * 32
            self._persist()

    def generate_data_key(self, key_id: str) -> Tuple[bytes, bytes]:
        with self._lock:
            if key_id not in self._keys:
                # Auto-provision if requested
                self._keys[key_id] = AESGCM.generate_key(bit_length=256)
                self._revoked[key_id] = False
                self._persist()

        if self._revoked.get(key_id, False):
            raise KeyRevokedError(f"Master key {key_id} has been revoked (Crypto-Shredded)")
            
        kek = self._keys[key_id]
        # 1. Generate 256-bit ephemeral DEK via CSPRNG
        plaintext_dek = AESGCM.generate_key(bit_length=256)
        
        # 2. Encrypt DEK with KEK using AES-256-GCM
        aesgcm = AESGCM(kek)
        iv = secrets.token_bytes(12) # 96-bit IV
        # Encrypted DEK format: [12-byte IV] + [Ciphertext + 16-byte Tag]
        encrypted_dek = iv + aesgcm.encrypt(iv, plaintext_dek, associated_data=key_id.encode("utf-8"))
        
        return plaintext_dek, encrypted_dek

    def decrypt_data_key(self, key_id: str, ciphertext_dek: bytes) -> bytes:
        if key_id not in self._keys:
            raise KeyNotFoundError(f"Master key {key_id} not found")
            
        if self._revoked.get(key_id, False):
            raise KeyRevokedError(f"Master key {key_id} has been revoked (Crypto-Shredded)")
            
        kek = self._keys[key_id]
        aesgcm = AESGCM(kek)
        
        iv = ciphertext_dek[:12]
        payload = ciphertext_dek[12:]
        
        plaintext_dek = aesgcm.decrypt(iv, payload, associated_data=key_id.encode("utf-8"))
        return plaintext_dek

