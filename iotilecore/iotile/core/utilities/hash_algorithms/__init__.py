"""Hashing algorithms that we commonly use."""

from collections import namedtuple
from .crc import calculate_crc
from .sha import calculate_sha

HashAlgorithm = namedtuple("HashAlgorithm", ['calculate', 'algorithm'])

KNOWN_HASH_ALGORITHMS = {
    'crc32_0x104C11DB7': HashAlgorithm(calculate_crc, 0x104C11DB7),
    'sha256': HashAlgorithm(calculate_sha, 256)
}

__all__ = ['KNOWN_HASH_ALGORITHMS']