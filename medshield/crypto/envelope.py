import struct
import secrets
from typing import NamedTuple, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from medshield.crypto.kms_provider import KMSProvider

MAGIC_HEADER = b"MEDENC01"

class EnvelopeHeader(NamedTuple):
    kek_id: str
    ciphertext_dek: bytes
    iv: bytes
    tag: bytes
    payload_len: int
    header_size: int

def pack_envelope_container(
    kek_id: str,
    ciphertext_dek: bytes,
    iv: bytes,
    tag: bytes,
    ciphertext: bytes
) -> bytes:
    """
    Serializes encrypted DICOM payload into MEDENC01 binary format per SPEC.md §5.3.
    """
    kek_id_bytes = kek_id.encode("utf-8")
    
    parts = [
        MAGIC_HEADER,
        struct.pack(">H", len(kek_id_bytes)),
        kek_id_bytes,
        struct.pack(">H", len(ciphertext_dek)),
        ciphertext_dek,
        iv,   # 12 bytes
        tag,  # 16 bytes
        struct.pack(">Q", len(ciphertext)),
        ciphertext
    ]
    return b"".join(parts)

def unpack_envelope_header(container: bytes) -> Tuple[EnvelopeHeader, bytes]:
    """
    Parses MEDENC01 binary envelope and separates header from ciphertext payload.
    """
    if len(container) < 40 or not container.startswith(MAGIC_HEADER):
        raise ValueError("Invalid envelope container: Missing MEDENC01 magic bytes")
        
    offset = 8 # Skip MAGIC_HEADER
    
    # KEK ID
    kek_id_len = struct.unpack(">H", container[offset:offset+2])[0]
    offset += 2
    kek_id = container[offset:offset+kek_id_len].decode("utf-8")
    offset += kek_id_len
    
    # Ciphertext DEK
    dek_len = struct.unpack(">H", container[offset:offset+2])[0]
    offset += 2
    ciphertext_dek = container[offset:offset+dek_len]
    offset += dek_len
    
    # IV (12 bytes) and Tag (16 bytes)
    iv = container[offset:offset+12]
    offset += 12
    tag = container[offset:offset+16]
    offset += 16
    
    # Payload Length
    payload_len = struct.unpack(">Q", container[offset:offset+8])[0]
    offset += 8
    
    ciphertext = container[offset:offset+payload_len]
    if len(ciphertext) != payload_len:
        raise ValueError(f"Corrupted payload: expected {payload_len} bytes, got {len(ciphertext)}")
        
    header = EnvelopeHeader(
        kek_id=kek_id,
        ciphertext_dek=ciphertext_dek,
        iv=iv,
        tag=tag,
        payload_len=payload_len,
        header_size=offset
    )
    return header, ciphertext

def encrypt_envelope(
    payload: bytes,
    plaintext_dek: bytes,
    kek_id: str,
    ciphertext_dek: bytes
) -> bytes:
    """
    Encrypts a raw DICOM payload using AES-256-GCM envelope encryption.
    """
    aesgcm = AESGCM(plaintext_dek)
    iv = secrets.token_bytes(12) # 96-bit unique IV
    
    # Additional Authenticated Data (AAD) binds container to KEK ID and magic header
    aad = MAGIC_HEADER + kek_id.encode("utf-8")
    
    # In cryptography library, aesgcm.encrypt returns ciphertext + 16-byte tag
    encrypted = aesgcm.encrypt(iv, payload, associated_data=aad)
    ciphertext = encrypted[:-16]
    tag = encrypted[-16:]
    
    return pack_envelope_container(
        kek_id=kek_id,
        ciphertext_dek=ciphertext_dek,
        iv=iv,
        tag=tag,
        ciphertext=ciphertext
    )

def decrypt_envelope(container: bytes, kms: KMSProvider) -> bytes:
    """
    Decrypts a MEDENC01 envelope container by retrieving the DEK from KMS and verifying GCM integrity.
    """
    header, ciphertext = unpack_envelope_header(container)
    
    # 1. Recover plaintext DEK via KMS
    plaintext_dek = kms.decrypt_data_key(header.kek_id, header.ciphertext_dek)
    
    # 2. Decrypt payload using AES-256-GCM
    aesgcm = AESGCM(plaintext_dek)
    aad = MAGIC_HEADER + header.kek_id.encode("utf-8")
    
    # Reassemble ciphertext + tag for AESGCM decrypt
    ciphertext_with_tag = ciphertext + header.tag
    
    plaintext = aesgcm.decrypt(header.iv, ciphertext_with_tag, associated_data=aad)
    return plaintext
