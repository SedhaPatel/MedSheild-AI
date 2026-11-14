"""
MedShield-AI: Classical Finite-Field Diffie–Hellman (DH) Key Exchange Implementation
Course: SVNIT AI 331 (Information Security and Cryptography)

This module implements the textbook Diffie–Hellman key exchange protocol over a finite field
using modular exponentiation, cryptographically secure random number generation (CSPRNG),
public key validation against small-subgroup confinement, and HKDF-SHA256 symmetric key derivation.

MATHEMATICAL SPECIFICATION:
1. Public Parameters: Prime modulus 'p' (safe prime p = 2q + 1) and generator 'g'.
2. Alice: Private exponent 'a' in [2, p - 2]; Public key A = g^a mod p.
3. Bob:   Private exponent 'b' in [2, p - 2]; Public key B = g^b mod p.
4. Exchange: Alice receives B; Bob receives A.
5. Shared Secret Computation:
   Alice: S_A = B^a mod p
   Bob:   S_B = A^b mod p
   Mathematical equivalence: S_A = (g^b)^a = g^(ab) = (g^a)^b = S_B mod p.
6. Key Derivation:
   K_AES = HKDF-SHA256(IKM = S, Salt = salt, Info = context, Length = 32 bytes).
7. Authenticated Symmetric Encryption:
   Payload is encrypted and decrypted using AES-256-GCM with the derived K_AES.

SECURITY CONSIDERATIONS:
- Textbook Diffie-Hellman does NOT authenticate public keys; it is vulnerable to Man-in-the-Middle (MITM)
  attacks if public keys are exchanged over an unauthenticated channel.
- In production, public keys must be authenticated via digital signatures (e.g. RSA/ECDSA/Ed25519)
  or established within TLS 1.3 (ECDHE).
"""

from dataclasses import dataclass
import hashlib
import hmac
import os
import secrets
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# RFC 3526 2048-bit MODP Group 14 (Standard Safe Prime)
# Prime: p = 2^2048 - 2^1984 - 1 + 2^64 * { [2^1918 pi] + 124476 }
RFC3526_MODP_2048_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF"
)

# RFC 3526 1536-bit MODP Group 5 (Standard Safe Prime for fast verification/testing)
RFC3526_MODP_1536_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA237327FFFFFFFFFFFFFFFF"
)


@dataclass(frozen=True)
class DHParameters:
    """Public parameters for classical Diffie-Hellman: modulus p and generator g."""
    p: int
    g: int
    name: str = "RFC-3526-MODP-2048"
    q: Optional[int] = None

    def __post_init__(self):
        if self.q is None and self.p > 3:
            object.__setattr__(self, "q", (self.p - 1) // 2)

    @property
    def bit_length(self) -> int:
        return self.p.bit_length()


def get_default_dh_parameters() -> DHParameters:
    """Returns standard 2048-bit RFC 3526 MODP Group 14 parameters (g=2)."""
    p = int(RFC3526_MODP_2048_HEX, 16)
    return DHParameters(p=p, g=2, name="RFC-3526-MODP-2048")


def get_rfc3526_group5_parameters() -> DHParameters:
    """Returns standard 1536-bit RFC 3526 MODP Group 5 parameters (g=2)."""
    p = int(RFC3526_MODP_1536_HEX, 16)
    return DHParameters(p=p, g=2, name="RFC-3526-MODP-1536")


# Alias for compatibility
get_rfc2409_group2_parameters = get_rfc3526_group5_parameters


def validate_parameters(params: DHParameters) -> None:
    """
    Validates that public parameters satisfy minimum cryptographic security properties.
    """
    if not isinstance(params.p, int) or not isinstance(params.g, int):
        raise ValueError("Diffie-Hellman parameters (p, g) must be integers")
    if params.p % 2 == 0:
        raise ValueError("Modulus 'p' must be an odd prime number")
    if params.bit_length < 512:
        raise ValueError(f"Modulus 'p' is too small ({params.bit_length} bits); minimum is 512 bits for test / 2048 bits for production")
    if params.g < 2:
        raise ValueError("Generator 'g' must be greater than or equal to 2")
    if params.g >= params.p:
        raise ValueError("Generator 'g' must be strictly less than modulus 'p'")


def generate_private_key(params: DHParameters) -> int:
    """
    Generate a private key exponent 'x' using a cryptographically secure
    pseudorandom number generator (CSPRNG via secrets.randbelow).
    Range: 2 <= x <= p - 2.
    """
    validate_parameters(params)
    # Range [2, p - 2]
    # secrets.randbelow(n) returns [0, n - 1]; using n = p - 3 gives [0, p - 4] + 2 = [2, p - 2]
    return secrets.randbelow(params.p - 3) + 2


def compute_public_key(private_key: int, params: DHParameters) -> int:
    """
    Calculate public key Y = g^x mod p using modular exponentiation.
    """
    validate_parameters(params)
    if not (2 <= private_key <= params.p - 2):
        raise ValueError("Private key must be in range [2, p - 2]")
    return pow(params.g, private_key, params.p)


def validate_public_key(public_key: int, params: DHParameters) -> None:
    """
    Validates a received public key to prevent small subgroup and invalid curve/field attacks.
    Criteria:
    1. Public key must be an integer.
    2. Range check: 2 <= Y <= p - 2 (rejects 0, 1, p - 1, and negative/out-of-range values).
    3. If safe prime subgroup order q = (p - 1)//2 is known:
       verify Y^q mod p == 1 (verifies key is in the quadratic residue subgroup).
    """
    validate_parameters(params)
    if not isinstance(public_key, int):
        raise ValueError(f"Public key must be an integer, got {type(public_key).__name__}")
    if public_key < 2 or public_key > params.p - 2:
        raise ValueError(f"Public key {public_key} is out of safe range [2, p - 2]")

    # Subgroup check for safe prime groups (where p = 2q + 1)
    if params.q is not None:
        if pow(public_key, params.q, params.p) != 1:
            raise ValueError("Public key failed quadratic residue subgroup validation (potential subgroup attack)")


def compute_shared_secret(peer_public_key: int, private_key: int, params: DHParameters) -> int:
    """
    Computes the raw shared secret S = (peer_public_key)^private_key mod p.
    """
    validate_public_key(peer_public_key, params)
    if not (2 <= private_key <= params.p - 2):
        raise ValueError("Private key must be in range [2, p - 2]")

    shared_secret = pow(peer_public_key, private_key, params.p)
    if shared_secret <= 1 or shared_secret >= params.p - 1:
        raise ValueError("Computed shared secret is invalid (trivial subgroup element)")
    return shared_secret


def derive_symmetric_key(
    shared_secret: int,
    params: DHParameters,
    salt: Optional[bytes] = None,
    info: bytes = b"MedShield-DH-v1:AES-256-GCM",
    key_length: int = 32,
) -> bytes:
    """
    Derives a cryptographically strong 256-bit symmetric key from the raw DH shared secret
    using HKDF-SHA256 (RFC 5869).
    Never uses the raw modular exponentiation output directly as an AES key.
    """
    byte_length = (params.p.bit_length() + 7) // 8
    ikm = shared_secret.to_bytes(byte_length, byteorder="big")

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=key_length,
        salt=salt or b"MedShield-DH-KeyExchange-Salt-v1",
        info=info,
    )
    return hkdf.derive(ikm)


def compute_key_fingerprint(key_bytes: bytes) -> str:
    """Computes a SHA-256 hex fingerprint of a key, safe for logging/display."""
    return hashlib.sha256(key_bytes).hexdigest()


def compute_confirmation_tag(key_bytes: bytes, transcript: bytes) -> str:
    """Computes an HMAC-SHA256 key-confirmation tag over the exchange transcript."""
    return hmac.new(key_bytes, transcript, hashlib.sha256).hexdigest()


def encrypt_with_dh_key(
    payload: bytes,
    derived_aes_key: bytes,
    aad: Optional[bytes] = None,
) -> Dict[str, bytes]:
    """
    Encrypts a payload with AES-256-GCM using the Diffie-Hellman derived symmetric key.
    Returns dictionary with IV (96 bits), ciphertext with GCM tag (128 bits), and AAD.
    """
    if len(derived_aes_key) != 32:
        raise ValueError(f"AES-256 requires exactly 32-byte key, got {len(derived_aes_key)}")
    iv = secrets.token_bytes(12)
    aesgcm = AESGCM(derived_aes_key)
    ciphertext_with_tag = aesgcm.encrypt(iv, payload, aad)
    return {
        "iv": iv,
        "ciphertext": ciphertext_with_tag,
        "aad": aad or b"",
    }


def decrypt_with_dh_key(
    encrypted_payload: Dict[str, bytes],
    derived_aes_key: bytes,
) -> bytes:
    """
    Decrypts an AES-256-GCM payload using the independently derived symmetric key.
    Verifies authentication tag and AAD; raises InvalidTag on tampering or key mismatch.
    """
    if len(derived_aes_key) != 32:
        raise ValueError(f"AES-256 requires exactly 32-byte key, got {len(derived_aes_key)}")
    iv = encrypted_payload["iv"]
    ciphertext = encrypted_payload["ciphertext"]
    aad = encrypted_payload.get("aad") or None
    aesgcm = AESGCM(derived_aes_key)
    return aesgcm.decrypt(iv, ciphertext, aad)


class DiffieHellmanParty:
    """
    Represents an entity (e.g. Alice or Bob) participating in Diffie-Hellman key exchange.
    Enforces that private keys are never exposed in string representations or serialized dumps.
    """
    def __init__(self, name: str, params: Optional[DHParameters] = None):
        self.name = name
        self.params = params or get_default_dh_parameters()
        self._private_key = generate_private_key(self.params)
        self.public_key = compute_public_key(self._private_key, self.params)
        self._shared_secret: Optional[int] = None
        self._derived_key: Optional[bytes] = None

    def compute_shared_secret(self, peer_public_key: int) -> int:
        """Compute the shared secret from peer's public key."""
        self._shared_secret = compute_shared_secret(peer_public_key, self._private_key, self.params)
        return self._shared_secret

    def derive_key(
        self,
        peer_public_key: int,
        salt: Optional[bytes] = None,
        info: bytes = b"MedShield-DH-v1:AES-256-GCM",
    ) -> bytes:
        """Derive 256-bit symmetric key using HKDF-SHA256."""
        s = self.compute_shared_secret(peer_public_key)
        self._derived_key = derive_symmetric_key(s, self.params, salt=salt, info=info)
        return self._derived_key

    def get_key_fingerprint(self) -> Optional[str]:
        """Return SHA-256 fingerprint of the derived key without revealing the key bytes."""
        if self._derived_key is None:
            return None
        return compute_key_fingerprint(self._derived_key)

    def encrypt(self, plaintext: bytes, aad: Optional[bytes] = None) -> Dict[str, bytes]:
        if self._derived_key is None:
            raise RuntimeError(f"{self.name} has not derived a symmetric key yet")
        return encrypt_with_dh_key(plaintext, self._derived_key, aad=aad)

    def decrypt(self, encrypted_data: Dict[str, bytes]) -> bytes:
        if self._derived_key is None:
            raise RuntimeError(f"{self.name} has not derived a symmetric key yet")
        return decrypt_with_dh_key(encrypted_data, self._derived_key)

    def __repr__(self) -> str:
        # Deliberately NEVER expose self._private_key
        return (
            f"<DiffieHellmanParty(name='{self.name}', "
            f"group='{self.params.name}', "
            f"public_key_preview=0x{hex(self.public_key)[2:18]}...)>"
        )


def run_diffie_hellman_demo() -> Dict[str, Any]:
    """
    Executes a complete, reproducible academic demonstration of textbook Diffie-Hellman
    key exchange integrated with AES-256-GCM medical payload encryption.
    """
    params = get_default_dh_parameters()

    # 1. Initialize Alice and Bob
    alice = DiffieHellmanParty(name="Alice (Hospital Ingestion Gateway)", params=params)
    bob = DiffieHellmanParty(name="Bob (PACS Inference Engine)", params=params)

    # 2. Compute shared secrets and derive keys
    alice_derived_key = alice.derive_key(bob.public_key, info=b"MedShield-Clinical-Exchange-v1")
    bob_derived_key = bob.derive_key(alice.public_key, info=b"MedShield-Clinical-Exchange-v1")

    # Verify secrets and derived keys match exactly
    secrets_match = (alice._shared_secret == bob._shared_secret)
    keys_match = (alice_derived_key == bob_derived_key)

    # 3. Medical Payload Encryption via AES-256-GCM
    sample_medical_payload = (
        b"PATIENT_STUDY_DISPATCH: ANONYMOUS_UID=2.25.98765432101234567890; "
        b"MODALITY=DX; INDICATION=Rule out Pneumothorax; PRIORITY=STAT_CRITICAL"
    )
    aad = b"MEDSHIELD-STUDY-HEADER-v1"

    encrypted_data = alice.encrypt(sample_medical_payload, aad=aad)

    # 4. Decryption by Bob
    decrypted_by_bob = bob.decrypt(encrypted_data)
    payloads_match = (decrypted_by_bob == sample_medical_payload)

    # 5. Negative Test: Malicious Eve with a different key
    eve = DiffieHellmanParty(name="Eve (Attacker / Unauthorized Node)", params=params)
    # Eve derives key with another party
    dummy_peer = DiffieHellmanParty(name="Dummy", params=params)
    eve.derive_key(dummy_peer.public_key, info=b"MedShield-Clinical-Exchange-v1")

    eve_decryption_failed = False
    try:
        eve.decrypt(encrypted_data)
    except Exception:
        eve_decryption_failed = True

    # 6. Negative Test: Tampering with ciphertext
    tampered_data = {
        "iv": encrypted_data["iv"],
        "ciphertext": bytes([encrypted_data["ciphertext"][0] ^ 0x01]) + encrypted_data["ciphertext"][1:],
        "aad": encrypted_data["aad"],
    }
    tamper_detection_succeeded = False
    try:
        bob.decrypt(tampered_data)
    except Exception:
        tamper_detection_succeeded = True

    result = {
        "protocol": "Textbook Diffie-Hellman Key Exchange (Finite Field MODP)",
        "parameters": {
            "group_name": params.name,
            "modulus_bits": params.bit_length,
            "generator_g": params.g,
            "modulus_p_hex_preview": f"0x{RFC3526_MODP_2048_HEX[:24]}...{RFC3526_MODP_2048_HEX[-16:]}",
        },
        "exchange": {
            "alice_public_key_hex_preview": f"0x{hex(alice.public_key)[2:24]}...{hex(alice.public_key)[-16:]}",
            "bob_public_key_hex_preview": f"0x{hex(bob.public_key)[2:24]}...{hex(bob.public_key)[-16:]}",
            "shared_secret_match_verified": secrets_match,
            "shared_secret_sha256": hashlib.sha256(alice._shared_secret.to_bytes(256, "big")).hexdigest(),
        },
        "key_derivation": {
            "kdf": "HKDF-SHA256 (RFC 5869)",
            "derived_key_algorithm": "AES-256-GCM",
            "derived_key_length_bits": len(alice_derived_key) * 8,
            "derived_key_fingerprint_sha256": alice.get_key_fingerprint(),
            "keys_match": keys_match,
        },
        "aes_gcm_integration": {
            "plaintext_bytes": len(sample_medical_payload),
            "ciphertext_bytes": len(encrypted_data["ciphertext"]),
            "iv_bytes": len(encrypted_data["iv"]),
            "decryption_successful": payloads_match,
            "tamper_detected": tamper_detection_succeeded,
            "eve_rejection_verified": eve_decryption_failed,
        },
    }
    return result


if __name__ == "__main__":
    import pprint
    print("=" * 80)
    print("MedShield-AI: Diffie-Hellman Key Exchange & AES-256-GCM Academic Demonstration")
    print("=" * 80)
    demo = run_diffie_hellman_demo()
    pprint.pprint(demo, width=100)
