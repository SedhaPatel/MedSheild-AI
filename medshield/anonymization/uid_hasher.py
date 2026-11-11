import hashlib
import hmac

def generate_pseudonymized_uid(original_uid: str, secret_salt: bytes) -> str:
    """
    Cryptographically hashes a DICOM UID using HMAC-SHA256 with an organizational secret salt.
    Returns a standardized, valid numeric dot-delimited DICOM UID prefixed with '2.25.'.
    Conforms to ISO/IEC 8824 and DICOM Part 5 UID length limits (<= 64 characters).
    """
    if not original_uid:
        raise ValueError("Original UID cannot be empty")
        
    digest = hmac.new(secret_salt, original_uid.encode("utf-8"), hashlib.sha256).digest()
    
    # Convert digest to integer and format as decimal string
    int_val = int.from_bytes(digest, byteorder="big")
    int_str = str(int_val)
    
    # Prefix with '2.25.' (Standard UUID-derived DICOM Root)
    # 2.25. + digits (length of prefix is 5, max total length is 64 -> digits <= 59)
    anon_uid = f"2.25.{int_str[:58]}"
    return anon_uid
