import math
from collections import Counter

def calculate_shannon_entropy(data: bytes) -> float:
    """
    Calculates Shannon entropy in bits per byte for binary data:
    H(X) = - sum( P(x) * log2( P(x) ) )
    
    A truly random byte distribution (such as high-grade AES-256 ciphertext)
    yields entropy approaching the theoretical maximum of 8.0 bits/byte.
    """
    if not data:
        return 0.0
        
    length = len(data)
    counts = Counter(data)
    
    entropy = 0.0
    for count in counts.values():
        prob = count / length
        entropy -= prob * math.log2(prob)
        
    return entropy
