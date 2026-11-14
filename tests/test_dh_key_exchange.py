import pytest
from cryptography.exceptions import InvalidTag

from medshield.crypto.dh_key_exchange import (
    DHParameters,
    DiffieHellmanParty,
    compute_public_key,
    compute_shared_secret,
    derive_symmetric_key,
    encrypt_with_dh_key,
    decrypt_with_dh_key,
    generate_private_key,
    get_default_dh_parameters,
    get_rfc2409_group2_parameters,
    run_diffie_hellman_demo,
    validate_parameters,
    validate_public_key,
)


def test_dh_parameters_validation():
    # 1. Valid RFC parameters
    params_2048 = get_default_dh_parameters()
    validate_parameters(params_2048)
    assert params_2048.bit_length == 2048
    assert params_2048.g == 2

    params_1536 = get_rfc2409_group2_parameters()
    validate_parameters(params_1536)
    assert params_1536.bit_length == 1536

    # 2. Reject even modulus
    with pytest.raises(ValueError, match="odd prime"):
        validate_parameters(DHParameters(p=1000, g=2))

    # 3. Reject generator < 2
    with pytest.raises(ValueError, match="Generator 'g' must be greater than or equal to 2"):
        validate_parameters(DHParameters(p=params_1536.p, g=1))

    # 4. Reject generator >= p
    with pytest.raises(ValueError, match="strictly less than modulus"):
        validate_parameters(DHParameters(p=params_1536.p, g=params_1536.p + 1))

    # 5. Reject small modulus (< 512 bits)
    with pytest.raises(ValueError, match="too small"):
        validate_parameters(DHParameters(p=257, g=3))


def test_public_key_math_and_validation():
    params = get_rfc2409_group2_parameters()
    priv_a = generate_private_key(params)
    assert 2 <= priv_a <= params.p - 2

    # Verify public key is computed via modular exponentiation: A = g^a mod p
    pub_a = compute_public_key(priv_a, params)
    expected_pub_a = pow(params.g, priv_a, params.p)
    assert pub_a == expected_pub_a
    assert 2 <= pub_a <= params.p - 2

    # Valid key passes validation
    validate_public_key(pub_a, params)

    # Rejection of invalid public keys
    with pytest.raises(ValueError, match="out of safe range"):
        validate_public_key(0, params)

    with pytest.raises(ValueError, match="out of safe range"):
        validate_public_key(1, params)

    with pytest.raises(ValueError, match="out of safe range"):
        validate_public_key(-5, params)

    with pytest.raises(ValueError, match="out of safe range"):
        validate_public_key(params.p - 1, params)

    with pytest.raises(ValueError, match="out of safe range"):
        validate_public_key(params.p + 10, params)


def test_alice_and_bob_derive_identical_shared_secrets():
    params = get_default_dh_parameters()

    # Alice generates keypair
    alice_priv = generate_private_key(params)
    alice_pub = compute_public_key(alice_priv, params)

    # Bob generates keypair
    bob_priv = generate_private_key(params)
    bob_pub = compute_public_key(bob_priv, params)

    # Alice computes S_A = B^a mod p
    s_alice = compute_shared_secret(peer_public_key=bob_pub, private_key=alice_priv, params=params)

    # Bob computes S_B = A^b mod p
    s_bob = compute_shared_secret(peer_public_key=alice_pub, private_key=bob_priv, params=params)

    # Both must match exactly: S_A == S_B == g^(ab) mod p
    assert s_alice == s_bob
    assert s_alice == pow(params.g, alice_priv * bob_priv, params.p)


def test_different_private_keys_produce_different_secrets():
    params = get_rfc2409_group2_parameters()
    alice = DiffieHellmanParty(name="Alice", params=params)
    bob = DiffieHellmanParty(name="Bob", params=params)
    charlie = DiffieHellmanParty(name="Charlie", params=params)

    s_ab = alice.compute_shared_secret(bob.public_key)
    s_ac = alice.compute_shared_secret(charlie.public_key)

    assert s_ab != s_ac


def test_hkdf_produces_identical_keys_on_both_sides():
    params = get_default_dh_parameters()
    alice = DiffieHellmanParty(name="Alice", params=params)
    bob = DiffieHellmanParty(name="Bob", params=params)

    salt = b"MedShield-Salt-2026"
    info = b"MedShield-Session-DICOM-Transfer"

    k_alice = alice.derive_key(bob.public_key, salt=salt, info=info)
    k_bob = bob.derive_key(alice.public_key, salt=salt, info=info)

    assert len(k_alice) == 32
    assert len(k_bob) == 32
    assert k_alice == k_bob
    assert alice.get_key_fingerprint() == bob.get_key_fingerprint()


def test_different_session_context_produces_different_keys():
    params = get_rfc2409_group2_parameters()
    alice = DiffieHellmanParty(name="Alice", params=params)
    bob = DiffieHellmanParty(name="Bob", params=params)

    s = alice.compute_shared_secret(bob.public_key)

    k1 = derive_symmetric_key(s, params, info=b"Context-Session-1")
    k2 = derive_symmetric_key(s, params, info=b"Context-Session-2")
    assert k1 != k2


def test_aes_gcm_encryption_and_decryption_with_derived_key():
    params = get_default_dh_parameters()
    alice = DiffieHellmanParty(name="Alice", params=params)
    bob = DiffieHellmanParty(name="Bob", params=params)

    alice.derive_key(bob.public_key)
    bob.derive_key(alice.public_key)

    payload = b"CRITICAL_CLINICAL_FINDING: Confirmed Tension Pneumothorax in Left Hemithorax"
    aad = b"PATIENT_ANON_UID=2.25.10928301928"

    # Alice encrypts with derived key
    enc = alice.encrypt(payload, aad=aad)
    assert enc["iv"] is not None and len(enc["iv"]) == 12
    assert enc["ciphertext"] != payload

    # Bob decrypts with his independently derived key
    decrypted = bob.decrypt(enc)
    assert decrypted == payload


def test_ciphertext_tampering_fails_gcm_verification():
    params = get_rfc2409_group2_parameters()
    alice = DiffieHellmanParty(name="Alice", params=params)
    bob = DiffieHellmanParty(name="Bob", params=params)

    alice.derive_key(bob.public_key)
    bob.derive_key(alice.public_key)

    payload = b"Patient status: Normal scan"
    enc = alice.encrypt(payload)

    # Tamper with the first byte of ciphertext
    tampered_bytes = bytes([enc["ciphertext"][0] ^ 0xFF]) + enc["ciphertext"][1:]
    tampered_enc = {"iv": enc["iv"], "ciphertext": tampered_bytes, "aad": enc["aad"]}

    with pytest.raises(InvalidTag):
        bob.decrypt(tampered_enc)


def test_different_derived_key_cannot_decrypt():
    params = get_default_dh_parameters()
    alice = DiffieHellmanParty(name="Alice", params=params)
    bob = DiffieHellmanParty(name="Bob", params=params)
    eve = DiffieHellmanParty(name="Eve", params=params)

    alice.derive_key(bob.public_key)
    bob.derive_key(alice.public_key)
    # Eve exchanges with an unrelated party
    dummy = DiffieHellmanParty(name="Dummy", params=params)
    eve.derive_key(dummy.public_key)

    payload = b"Top secret hospital data"
    enc = alice.encrypt(payload)

    # Eve attempts decryption -> InvalidTag
    with pytest.raises(InvalidTag):
        eve.decrypt(enc)


def test_full_diffie_hellman_academic_demo():
    result = run_diffie_hellman_demo()
    assert result["protocol"] == "Textbook Diffie-Hellman Key Exchange (Finite Field MODP)"
    assert result["parameters"]["modulus_bits"] == 2048
    assert result["parameters"]["generator_g"] == 2
    assert result["exchange"]["shared_secret_match_verified"] is True
    assert result["key_derivation"]["keys_match"] is True
    assert result["key_derivation"]["derived_key_length_bits"] == 256
    assert result["aes_gcm_integration"]["decryption_successful"] is True
    assert result["aes_gcm_integration"]["tamper_detected"] is True
    assert result["aes_gcm_integration"]["eve_rejection_verified"] is True
