import os
import pytest
from cryptography.exceptions import InvalidTag

from medshield.crypto.kms_provider import LocalKMSProvider, KeyRevokedError, KeyNotFoundError
from medshield.crypto.envelope import (
    encrypt_envelope,
    decrypt_envelope,
    unpack_envelope_header,
    MAGIC_HEADER
)
from medshield.storage.encrypted_store import EncryptedStore

def test_kms_generate_and_decrypt_data_key():
    kms = LocalKMSProvider()
    kek_id = kms.create_master_key("master-kek-01")
    
    plaintext_dek, ciphertext_dek = kms.generate_data_key(kek_id)
    assert len(plaintext_dek) == 32 # 256 bits
    assert len(ciphertext_dek) > 32 # includes GCM IV + tag
    assert plaintext_dek != ciphertext_dek
    
    recovered_dek = kms.decrypt_data_key(kek_id, ciphertext_dek)
    assert recovered_dek == plaintext_dek

def test_envelope_encrypt_decrypt_roundtrip():
    kms = LocalKMSProvider()
    kek_id = kms.create_master_key("master-kek-01")
    plaintext_dek, ciphertext_dek = kms.generate_data_key(kek_id)
    
    raw_payload = b"DICM" + b"Simulated DICOM byte stream with patient scans..." * 20
    
    container = encrypt_envelope(
        payload=raw_payload,
        plaintext_dek=plaintext_dek,
        kek_id=kek_id,
        ciphertext_dek=ciphertext_dek
    )
    
    assert container.startswith(MAGIC_HEADER)
    assert len(container) > len(raw_payload)
    
    decrypted_payload = decrypt_envelope(container, kms)
    assert decrypted_payload == raw_payload

def test_envelope_tamper_detection():
    kms = LocalKMSProvider()
    kek_id = kms.create_master_key("master-kek-01")
    plaintext_dek, ciphertext_dek = kms.generate_data_key(kek_id)
    
    raw_payload = b"Critical diagnostic scan payload"
    container = bytearray(encrypt_envelope(raw_payload, plaintext_dek, kek_id, ciphertext_dek))
    
    # Mutate a single bit in the ciphertext payload (at the end)
    container[-1] ^= 0x01
    
    with pytest.raises(Exception): # Must raise InvalidTag or IntegrityError
        decrypt_envelope(bytes(container), kms)

def test_crypto_shredding_via_key_revocation():
    kms = LocalKMSProvider()
    kek_id = kms.create_master_key("master-kek-shred")
    plaintext_dek, ciphertext_dek = kms.generate_data_key(kek_id)
    
    raw_payload = b"Patient scan subject to DPDP Right to Erasure"
    container = encrypt_envelope(raw_payload, plaintext_dek, kek_id, ciphertext_dek)
    
    # Verify decryption works initially
    assert decrypt_envelope(container, kms) == raw_payload
    
    # Execute Crypto-Shredding by revoking the KEK
    kms.revoke_key(kek_id)
    
    with pytest.raises(KeyRevokedError):
        decrypt_envelope(container, kms)

def test_encrypted_store_persistence(tmp_path):
    store = EncryptedStore(storage_dir=str(tmp_path))
    study_uid = "2.25.998811223344"
    dummy_encrypted_data = MAGIC_HEADER + b"\x00\x05local" + b"\x12\x34" * 50
    
    saved_path = store.save(study_uid, dummy_encrypted_data)
    assert os.path.exists(saved_path)
    assert saved_path.endswith(f"{study_uid}.enc")
    
    loaded_data = store.load(study_uid)
    assert loaded_data == dummy_encrypted_data
    
    # Verify deletion
    assert store.delete(study_uid) is True
    assert not os.path.exists(saved_path)
    assert store.load(study_uid) is None

