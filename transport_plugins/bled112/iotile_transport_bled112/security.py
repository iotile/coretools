import hashlib
import hmac
import struct

from Crypto.Cipher import AES

EPHEMERAL_KEY_CYCLE_POWER = 6

def generate_per_reboot_key(root_key, key_purpose, reboot_counter):
    signed_data = struct.pack("<LL", key_purpose, reboot_counter)

    hmac_calc = hmac.new(root_key, signed_data, hashlib.sha256)
    return bytearray(hmac_calc.digest()[:16])


def generate_ephemeral_key(reboot_key, current_timestamp):
    timestamp = current_timestamp & (~(2 ** EPHEMERAL_KEY_CYCLE_POWER - 1))
    cipher = AES.new(reboot_key, AES.MODE_ECB)
    msg = struct.pack("<LLLL", timestamp, 0, 0, 0)

    return cipher.encrypt(msg)


def generate_nonce(device_uuid, timestamp, low_reboots, high_reboots, counter_packed):
    return struct.pack("<LLHBBB", device_uuid, timestamp, low_reboots, high_reboots, counter_packed, 0)


def verify_payload(key, message, nonce):
    aad = message[0:14]
    body = message[14:20]
    mac = message[20:]

    cipher = AES.new(key, AES.MODE_CCM, nonce, mac_len=4)
    cipher.update(aad)
    cipher.encrypt(body)

    #print(mac, cipher.digest())
    return mac == cipher.digest()
