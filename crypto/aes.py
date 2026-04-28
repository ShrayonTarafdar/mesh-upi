import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def generate_aes_key() -> bytes:
    return os.urandom(32)  # 256 bits

def encrypt(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)  # 96 bits, GCM standard
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext

def decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)

if __name__ == "__main__":
    key = generate_aes_key()
    print(f"AES key     : {base64.b64encode(key).decode()}")

    payload = b'{"sender":"alice@upi","recipient":"bob@upi","amount_paise":10000}'
    print(f"Plaintext   : {payload.decode()}")

    nonce, ciphertext = encrypt(key, payload)
    print(f"Nonce       : {base64.b64encode(nonce).decode()}")
    print(f"Ciphertext  : {base64.b64encode(ciphertext).decode()}")

    decrypted = decrypt(key, nonce, ciphertext)
    print(f"Decrypted   : {decrypted.decode()}")
    print(f"Match       : {payload == decrypted}  <- must be True")

    # Tamper test — flip one byte in ciphertext
    bad = bytearray(ciphertext)
    bad[4] ^= 0xFF
    try:
        decrypt(key, nonce, bytes(bad))
        print("Tamper      : FAILED — should have raised!")
    except Exception:
        print("Tamper      : Rejected correctly  <- must appear")
