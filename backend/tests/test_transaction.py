import sys
import os
import base64
import json
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../crypto"))

from keys import generate_ed25519_keypair
from packet import build_packet
from rsa_wrap import generate_rsa_keypair
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

BASE = "http://localhost:8000/api/v1"

def test_full_transaction():
    # Load the test bank private key and extract public key
    with open("/tmp/test_bank_priv.pem", "rb") as f:
        bank_priv = load_pem_private_key(f.read(), password=None)
    bank_pub = bank_priv.public_key()

    # Generate sender keypair (simulating alice's device)
    sender_priv, sender_pub = generate_ed25519_keypair()

    print("=== TEST 1: Valid transaction alice→bob ₹100 ===")
    packet = build_packet(
        sender_upi        = "alice@upi",
        recipient_upi     = "bob@upi",
        amount_paise      = 10000,
        sender_priv_bytes = sender_priv,
        bank_rsa_pub      = bank_pub,
    )
    payload = {**packet, "sender_pub_key_b64": base64.b64encode(sender_pub).decode(), "ifsc_prefix": "SBI0"}
    r = requests.post(f"{BASE}/transaction", json=payload)
    print(f"Status code : {r.status_code}  <- must be 200")
    data = r.json()
    print(json.dumps(data, indent=2))
    assert data["status"] == "SUCCESS", f"Expected SUCCESS got {data['status']}"
    assert data["amount_paise"] == 10000
    print("PASS\n")

    print("=== TEST 2: Duplicate packet (replay attack) ===")
    r2 = requests.post(f"{BASE}/transaction", json=payload)
    data2 = r2.json()
    print(json.dumps(data2, indent=2))
    assert data2["status"] in ("FAILED", "SUCCESS")
    assert data2["tx_id"] in ("duplicate", data["tx_id"])
    print("PASS (duplicate blocked or returned cached)\n")

    print("=== TEST 3: Insufficient balance ===")
    sender_priv2, sender_pub2 = generate_ed25519_keypair()
    packet3 = build_packet(
        sender_upi        = "alice@upi",
        recipient_upi     = "bob@upi",
        amount_paise      = 999999999,   # way more than alice has
        sender_priv_bytes = sender_priv2,
        bank_rsa_pub      = bank_pub,
    )
    payload3 = {**packet3, "sender_pub_key_b64": base64.b64encode(sender_pub2).decode(), "ifsc_prefix": "SBI0"}
    r3 = requests.post(f"{BASE}/transaction", json=payload3)
    data3 = r3.json()
    print(json.dumps(data3, indent=2))
    assert data3["status"] == "FAILED"
    assert "Insufficient" in data3["reason"]
    print("PASS\n")

    print("=== TEST 4: Balance check after transactions ===")
    r4 = requests.get(f"{BASE}/balances")
    balances = r4.json()
    print(json.dumps(balances, indent=2))
    # alice started 50000, sent 10000 → should have 40000
    assert balances["alice@upi"]["paise"] == 40000, f"alice balance wrong: {balances['alice@upi']}"
    # bob started 20000, received 10000 → should have 30000
    assert balances["bob@upi"]["paise"] == 30000, f"bob balance wrong: {balances['bob@upi']}"
    print("PASS\n")

    print("=== TEST 5: Status polling ===")
    tx_id_from_test1 = data["packet_id"]
    r5 = requests.get(f"{BASE}/transaction/{tx_id_from_test1}")
    data5 = r5.json()
    print(json.dumps(data5, indent=2))
    assert data5["status"] == "SUCCESS"
    print("PASS\n")

    print("=" * 40)
    print("ALL TESTS PASSED")

if __name__ == "__main__":
    test_full_transaction()
