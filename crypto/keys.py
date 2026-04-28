from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)
import base64

def generate_ed25519_keypair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    priv_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return priv_bytes, pub_bytes

def sign(private_key_bytes: bytes, message: bytes) -> bytes:
    key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    return key.sign(message)

def verify(public_key_bytes: bytes, message: bytes, signature: bytes) -> bool:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    try:
        key.verify(signature, message)
        return True
    except InvalidSignature:
        return False

if __name__ == "__main__":
    priv, pub = generate_ed25519_keypair()
    print(f"Private key : {base64.b64encode(priv).decode()}")
    print(f"Public key  : {base64.b64encode(pub).decode()}")

    message = b"send 100rs from alice to bob"
    sig = sign(priv, message)
    print(f"Signature   : {base64.b64encode(sig).decode()}")

    result = verify(pub, message, sig)
    print(f"Verify OK   : {result}")

    tampered = b"send 9999rs from alice to bob"
    result2 = verify(pub, tampered, sig)
    print(f"Tampered OK : {result2}  <- must be False")
