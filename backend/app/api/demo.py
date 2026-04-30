import sys
import os
import base64

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../crypto"))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from cryptography.hazmat.primitives.serialization import load_pem_private_key

router = APIRouter(tags=["demo"])

class DemoSendRequest(BaseModel):
    sender_upi:    str
    recipient_upi: str
    amount_paise:  int

@router.post("/demo/send")
def demo_send(req: DemoSendRequest):
    """
    Demo-only endpoint — builds packet server-side using test keys.
    In production the mobile app builds the packet locally using on-device keys.
    Labeled clearly in UI as simulated for demo purposes.
    """
    from keys import generate_ed25519_keypair
    from packet import build_packet

    # Load test bank private key and extract public key
    pem_data = os.getenv("BANK_PRIV_KEY_PEM")
    if pem_data:
        bank_priv = load_pem_private_key(pem_data.encode(), password=None)
    else:
        with open("/tmp/test_bank_priv.pem", "rb") as f:
            bank_priv = load_pem_private_key(f.read(), password=None)
    bank_pub = bank_priv.public_key()

    # Generate fresh sender keypair for this demo transaction
    sender_priv, sender_pub = generate_ed25519_keypair()

    packet = build_packet(
        sender_upi        = req.sender_upi,
        recipient_upi     = req.recipient_upi,
        amount_paise      = req.amount_paise,
        sender_priv_bytes = sender_priv,
        bank_rsa_pub      = bank_pub,
    )

    # Now process it immediately (simulating relay node forwarding)
    from app.api.transactions import process_transaction
    from app.models.transaction import TransactionRequest

    tx_req = TransactionRequest(
        **packet,
        sender_pub_key_b64 = base64.b64encode(sender_pub).decode(),
        ifsc_prefix        = "SBI0",
    )
    result = process_transaction(tx_req)
    return result

@router.get("/demo/debug")
def demo_debug():
    import traceback
    try:
        pem_data = os.getenv("BANK_PRIV_KEY_PEM")
        if not pem_data:
            return {"error": "BANK_PRIV_KEY_PEM not set"}
        bank_priv = load_pem_private_key(pem_data.encode(), password=None)
        bank_pub = bank_priv.public_key()
        return {"status": "ok", "key_type": str(type(bank_priv)), "pem_length": len(pem_data)}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}
