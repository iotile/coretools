import hashlib
from iotile.core.exceptions import ArgumentError

def calculate_sha(sha_type, data):
    """Uses sha to calculate a checksum"""

    if sha_type == 256:
        shasum = hashlib.sha256()
        shasum.update(data)

        return shasum.hexdigest()

    raise ArgumentError("Unknown/Unimplemented sha algorithm")