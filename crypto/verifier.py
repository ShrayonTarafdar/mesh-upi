import json
import time
import base64

from keys import verify
from aes import decrypt
from rsa_wrap import unwrap_key

def b64d(s: str) -> bytes:
    return base64.b64decode(s)

def verify_packet(packet: dict, sender_pub_bytes: bytes, bank_rsa_priv) -> dict:
    """
    Full bank-side verification pipeline.
    Returns a result dict with status and decoded payload (if valid).

    Steps mirror exactly what the bank server will do:
      1. Check TTL — drop stale packets immediately
      2. Verify Ed25519 signature — drop tampered packets
      3. Unwrap AES session key with bank RSA private key
      4. Decrypt AES-GCM payload
      5. Return decoded payload for balance check
    """
    result = {
        "ttl_ok":        False,
        "signature_ok":  False,
        "decryption_ok": False,
        "payload":       None,
        "error":         None,
    }

    # Step 1 — TTL check (relay nodes also do this to drop stale packets)
    now = int(time.time())
    ttl = packet["header"]["ttl_expires_at"]
    if now > ttl:
        result["error"] = f"Packet expired {now - ttl}s ago"
        return result
    result["ttl_ok"] = True
    print(f"[1] TTL check      : OK — expires in {ttl - now}s")

    # Step 2 — Verify Ed25519 signature over (header + ciphertext)
    sign_target = (
        json.dumps(packet["header"], sort_keys=True, separators=(",", ":")).encode()
        + b64d(packet["encrypted_payload"])
    )
    sig_valid = verify(sender_pub_bytes, sign_target, b64d(packet["signature"]))
    if not sig_valid:
        result["error"] = "Signature invalid — packet tampered or forged"
        return result
    result["signature_ok"] = True
    print(f"[2] Signature check: OK — Ed25519 verified")

    # Step 3 — Unwrap AES session key with bank's RSA private key
    try:
        aes_key = unwrap_key(bank_rsa_priv, b64d(packet["encrypted_session_key"]))
        print(f"[3] Key unwrap     : OK — {len(aes_key)}-byte AES key recovered")
    except Exception as e:
        result["error"] = f"Key unwrap failed: {e}"
        return result

    # Step 4 — Decrypt AES-GCM payload
    try:
        plaintext = decrypt(aes_key, b64d(packet["gcm_nonce"]), b64d(packet["encrypted_payload"]))
        payload = json.loads(plaintext)
        result["decryption_ok"] = True
        result["payload"] = payload
        print(f"[4] AES-GCM decrypt: OK — payload recovered")
    except Exception as e:
        result["error"] = f"Decryption failed (tampered ciphertext?): {e}"
        return result

    return result


if __name__ == "__main__":
    from packet import build_packet
    from keys import generate_ed25519_keypair
    from rsa_wrap import generate_rsa_keypair

    bank_priv, bank_pub = generate_rsa_keypair()
    sender_priv, sender_pub = generate_ed25519_keypair()

    packet = build_packet(
        sender_upi        = "alice@upi",
        recipient_upi     = "bob@upi",
        amount_paise      = 10000,
        sender_priv_bytes = sender_priv,
        bank_rsa_pub      = bank_pub,
    )

    # ── Test 1: valid packet ──────────────────────────────────────────────────
    print("=" * 50)
    print("TEST 1: Valid packet")
    print("=" * 50)
    result = verify_packet(packet, sender_pub, bank_priv)
    print(f"\nResult status:")
    print(f"  ttl_ok        : {result['ttl_ok']}")
    print(f"  signature_ok  : {result['signature_ok']}")
    print(f"  decryption_ok : {result['decryption_ok']}")
    print(f"  payload       : {result['payload']}")

    # ── Test 2: tampered ciphertext ───────────────────────────────────────────
    print("\n" + "=" * 50)
    print("TEST 2: Tampered encrypted_payload")
    print("=" * 50)
    import base64, copy
    bad_packet = copy.deepcopy(packet)
    raw = bytearray(base64.b64decode(bad_packet["encrypted_payload"]))
    raw[10] ^= 0xFF
    bad_packet["encrypted_payload"] = base64.b64encode(bytes(raw)).decode()
    result2 = verify_packet(bad_packet, sender_pub, bank_priv)
    print(f"  error         : {result2['error']}  <- must show tamper error")

    # ── Test 3: wrong sender public key (impersonation attempt) ───────────────
    print("\n" + "=" * 50)
    print("TEST 3: Wrong sender public key (impersonation)")
    print("=" * 50)
    _, attacker_pub = generate_ed25519_keypair()
    result3 = verify_packet(packet, attacker_pub, bank_priv)
    print(f"  error         : {result3['error']}  <- must show signature error")

    # ── Test 4: expired TTL ───────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("TEST 4: Expired TTL (replay attack simulation)")
    print("=" * 50)
    expired_packet = copy.deepcopy(packet)
    expired_packet["header"]["ttl_expires_at"] = int(time.time()) - 120
    result4 = verify_packet(expired_packet, sender_pub, bank_priv)
    print(f"  error         : {result4['error']}  <- must show expired error")

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Valid packet    : {'PASS' if result['decryption_ok'] else 'FAIL'}")
    print(f"Tamper detect   : {'PASS' if result2['error'] else 'FAIL'}")
    print(f"Impersonation   : {'PASS' if result3['error'] else 'FAIL'}")
    print(f"Replay (TTL)    : {'PASS' if result4['error'] else 'FAIL'}")
