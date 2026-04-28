import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

def generate_rsa_keypair(key_size: int = 2048):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    return private_key, private_key.public_key()

def export_public_key(public_key) -> bytes:
    return public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

def wrap_key(public_key, aes_key: bytes) -> bytes:
    """Encrypt AES session key with bank's RSA public key."""
    return public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def unwrap_key(private_key, wrapped: bytes) -> bytes:
    """Decrypt wrapped AES key with bank's RSA private key."""
    return private_key.decrypt(
        wrapped,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

if __name__ == "__main__":
    # Simulate bank generating its RSA keypair (done once at bank onboarding)
    print("Generating RSA-2048 keypair (bank simulation)...")
    bank_priv, bank_pub = generate_rsa_keypair()
    pub_pem = export_public_key(bank_pub)
    print(f"Bank public key (PEM):\n{pub_pem.decode()}")

    # Simulate sender wrapping AES session key with bank's public key
    from aes import generate_aes_key
    aes_key = generate_aes_key()
    print(f"Original AES key : {base64.b64encode(aes_key).decode()}")

    wrapped = wrap_key(bank_pub, aes_key)
    print(f"Wrapped key      : {base64.b64encode(wrapped).decode()[:60]}...")

    # Simulate bank unwrapping it
    unwrapped = unwrap_key(bank_priv, wrapped)
    print(f"Unwrapped AES key: {base64.b64encode(unwrapped).decode()}")

    print(f"Keys match       : {aes_key == unwrapped}  <- must be True")

    # Tamper test — wrong private key cannot unwrap
    print("\nTamper test: trying wrong private key...")
    wrong_priv, _ = generate_rsa_keypair()
    try:
        unwrap_key(wrong_priv, wrapped)
        print("Tamper           : FAILED — should have raised!")
    except Exception:
        print("Tamper           : Rejected correctly  <- must appear")
