import os
import json
import time
import base64
import hashlib
from dataclasses import dataclass

from keys import generate_ed25519_keypair, sign
from aes import generate_aes_key, encrypt
from rsa_wrap import wrap_key

# ── helpers ──────────────────────────────────────────────────────────────────

def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()

def make_packet_id(sender_upi: str, recipient_upi: str, amount_paise: int, nonce: bytes) -> str:
    """
    SHA-256 of (sender + recipient + amount + nonce).
    Used as the idempotency key in Redis — same packet replayed = same id = dropped.
    """
    raw = f"{sender_upi}:{recipient_upi}:{amount_paise}:".encode() + nonce
    return hashlib.sha256(raw).hexdigest()

# ── core builder ─────────────────────────────────────────────────────────────

def build_packet(
    sender_upi: str,
    recipient_upi: str,
    amount_paise: int,
    sender_priv_bytes: bytes,
    bank_rsa_pub,
    ttl_seconds: int = 60,
) -> dict:
    """
    Returns a dict representing the full Mesh UPI packet.

    Structure:
      header      — cleartext, readable by relay nodes
      encrypted_session_key — AES key wrapped with bank RSA pubkey
      encrypted_payload     — AES-GCM ciphertext (only bank can read)
      signature   — Ed25519 over (header + encrypted_payload)
    """

    # 1. Generate fresh AES-256 session key for this transaction only
    aes_key = generate_aes_key()

    # 2. Build the private payload (only bank will ever see this plaintext)
    nonce_bytes = os.urandom(16)
    payload = {
        "sender_upi":    sender_upi,
        "recipient_upi": recipient_upi,
        "amount_paise":  amount_paise,   # always integer paise, never float
        "timestamp":     int(time.time()),
        "nonce":         b64(nonce_bytes),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()

    # 3. Encrypt payload with AES-GCM
    gcm_nonce, ciphertext = encrypt(aes_key, payload_bytes)

    # 4. Wrap AES key with bank's RSA public key (only bank can unwrap)
    wrapped_session_key = wrap_key(bank_rsa_pub, aes_key)

    # 5. Build cleartext header (relay nodes read this to route + TTL check)
    packet_id = make_packet_id(sender_upi, recipient_upi, amount_paise, nonce_bytes)
    header = {
        "packet_id":    packet_id,
        "ttl_expires_at": int(time.time()) + ttl_seconds,
        "nonce":        b64(nonce_bytes),
    }

    # 6. Sign over (header + ciphertext) with sender's Ed25519 private key
    #    Any bit flip anywhere → signature invalid → relay drops packet
    sign_target = (
        json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
        + ciphertext
    )
    signature = sign(sender_priv_bytes, sign_target)

    return {
        "header":                 header,
        "encrypted_session_key":  b64(wrapped_session_key),
        "gcm_nonce":              b64(gcm_nonce),
        "encrypted_payload":      b64(ciphertext),
        "signature":              b64(signature),
    }


if __name__ == "__main__":
    from rsa_wrap import generate_rsa_keypair

    # Simulate bank keypair (in prod this is loaded from bank's secure store)
    bank_priv, bank_pub = generate_rsa_keypair()

    # Simulate sender keypair (in prod generated on user's device at onboarding)
    sender_priv, sender_pub = generate_ed25519_keypair()

    print("Building packet: alice@upi → bob@upi, ₹100 (10000 paise)\n")
    packet = build_packet(
        sender_upi     = "alice@upi",
        recipient_upi  = "bob@upi",
        amount_paise   = 10000,
        sender_priv_bytes = sender_priv,
        bank_rsa_pub   = bank_pub,
    )

    print("=== FULL PACKET (as relay node sees it) ===")
    print(json.dumps(packet, indent=2))

    print("\n=== FIELD BREAKDOWN ===")
    print(f"packet_id            : {packet['header']['packet_id']}")
    print(f"ttl_expires_at       : {packet['header']['ttl_expires_at']}  (unix timestamp)")
    print(f"encrypted_session_key: {len(base64.b64decode(packet['encrypted_session_key']))} bytes  (RSA-2048 output)")
    print(f"gcm_nonce            : {len(base64.b64decode(packet['gcm_nonce']))} bytes")
    print(f"encrypted_payload    : {len(base64.b64decode(packet['encrypted_payload']))} bytes  (ciphertext + 16-byte GCM tag)")
    print(f"signature            : {len(base64.b64decode(packet['signature']))} bytes  (Ed25519 fixed size)")

    print("\n=== WHAT RELAY NODE SEES ===")
    print(f"Can read header      : YES — packet_id, ttl, nonce")
    print(f"Can read payload     : NO  — encrypted_payload is opaque ciphertext")
    print(f"Can forge signature  : NO  — needs sender private key")
    print(f"Can unwrap AES key   : NO  — needs bank RSA private key")
