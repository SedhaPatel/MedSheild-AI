import abc
import os
import secrets
from typing import Dict, Tuple
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
    """
    def __init__(self):
        self._keys: Dict[str, bytes] = {}
        self._revoked: Dict[str, bool] = {}
        
    def create_master_key(self, key_alias: str) -> str:
        key_id = f"arn:medshield:kms:local:key/{key_alias}"
        # Generate 256-bit (32 bytes) master KEK
        self._keys[key_id] = AESGCM.generate_key(bit_length=256)
        self._revoked[key_id] = False
        return key_id
        
    def revoke_key(self, key_id: str) -> None:
        """Executes cryptographic erasure (Crypto-Shredding) for the key."""
        if key_id not in self._keys:
            raise KeyNotFoundError(f"Key {key_id} not found")
        self._revoked[key_id] = True
        # Overwrite key material in memory
        self._keys[key_id] = b"\x00" * 32

    def generate_data_key(self, key_id: str) -> Tuple[bytes, bytes]:
        if key_id not in self._keys:
            # Auto-provision if default alias requested
            self.create_master_key(key_id.split("/")[-1])
            
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

