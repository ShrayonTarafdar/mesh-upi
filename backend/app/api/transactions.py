import sys
import os
import uuid
import base64
import logging

# Make crypto/ importable from here
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../crypto"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../core"))

from fastapi import APIRouter, HTTPException
from app.models.transaction import TransactionRequest, TransactionResponse
from app.api.banks import get_bank_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["transactions"])

# ── Fake balance store ────────────────────────────────────────────────────────
# Amounts in paise (integer only — never float)
# 50000 paise = ₹500, 20000 paise = ₹200
BALANCES: dict = {
    "alice@upi": 50000,
    "bob@upi":   20000,
}
BALANCE_LOCK = __import__("threading").Lock()

# ── Transaction log (in-memory, replaced by Supabase in Phase 4) ─────────────
TRANSACTIONS: dict = {}

def _load_bank_private_key():
    """
    Load test bank RSA private key from disk.
    In prod each bank has its own key loaded at startup from a secrets manager.
    """
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    with open("/tmp/test_bank_priv.pem", "rb") as f:
        return load_pem_private_key(f.read(), password=None)

@router.post("/transaction", response_model=TransactionResponse, status_code=200)
def process_transaction(req: TransactionRequest):
    """
    Main endpoint — called by relay nodes that have internet.
    Runs full bank-side verification pipeline:
      1. Look up bank by ifsc_prefix
      2. Verify Ed25519 signature + TTL
      3. Unwrap AES session key with bank RSA private key
      4. Decrypt payload
      5. Idempotency check
      6. Balance check
      7. Debit + credit
      8. Return result
    """
    packet_id = req.header.get("packet_id")
    if not packet_id:
        raise HTTPException(status_code=400, detail="Missing packet_id in header")

    # Step 1 — look up bank
    registry = get_bank_registry()
    if req.ifsc_prefix not in registry:
        raise HTTPException(status_code=404, detail=f"Bank {req.ifsc_prefix} not registered")

    bank_priv = _load_bank_private_key()

    # Step 2-4 — full crypto verification
    from verifier import verify_packet
    packet = {
        "header":                req.header,
        "encrypted_session_key": req.encrypted_session_key,
        "gcm_nonce":             req.gcm_nonce,
        "encrypted_payload":     req.encrypted_payload,
        "signature":             req.signature,
    }
    sender_pub = base64.b64decode(req.sender_pub_key_b64)
    verification = verify_packet(packet, sender_pub, bank_priv)

    if not verification["decryption_ok"]:
        logger.warning(f"Packet {packet_id} failed verification: {verification['error']}")
        return TransactionResponse(
            packet_id=packet_id,
            tx_id="none",
            status="FAILED",
            reason=verification["error"],
        )

    payload = verification["payload"]
    sender_upi    = payload["sender_upi"]
    recipient_upi = payload["recipient_upi"]
    amount_paise  = payload["amount_paise"]

    # Step 5 — idempotency check
    from idempotency_guard import claim, complete
    from idempotency_db import init_db
    init_db()

    if not claim(packet_id):
        # Already processed — return cached result
        existing = TRANSACTIONS.get(packet_id)
        if existing:
            return TransactionResponse(**existing)
        return TransactionResponse(
            packet_id=packet_id,
            tx_id="duplicate",
            status="FAILED",
            reason="Duplicate packet — already processed",
        )

    # Step 6 — balance check + Step 7 — debit/credit (atomic under lock)
    tx_id = str(uuid.uuid4())
    with BALANCE_LOCK:
        sender_balance = BALANCES.get(sender_upi, 0)
        if sender_balance < amount_paise:
            complete(packet_id, "FAILED")
            result = TransactionResponse(
                packet_id=packet_id,
                tx_id=tx_id,
                status="FAILED",
                reason=f"Insufficient balance: have {sender_balance} paise, need {amount_paise} paise",
                sender_upi=sender_upi,
                recipient_upi=recipient_upi,
                amount_paise=amount_paise,
            )
        else:
            BALANCES[sender_upi]    -= amount_paise
            BALANCES[recipient_upi]  = BALANCES.get(recipient_upi, 0) + amount_paise
            complete(packet_id, "SUCCESS")
            result = TransactionResponse(
                packet_id=packet_id,
                tx_id=tx_id,
                status="SUCCESS",
                reason=None,
                sender_upi=sender_upi,
                recipient_upi=recipient_upi,
                amount_paise=amount_paise,
            )
            logger.info(f"TX {tx_id}: {sender_upi} → {recipient_upi} {amount_paise} paise")
            logger.info(f"Balances after: {sender_upi}={BALANCES[sender_upi]}, {recipient_upi}={BALANCES[recipient_upi]}")

    # Cache result for duplicate requests
    TRANSACTIONS[packet_id] = result.model_dump()
    return result

@router.get("/transaction/{packet_id}", response_model=TransactionResponse)
def get_transaction(packet_id: str):
    """Status polling endpoint — frontend calls this while waiting."""
    tx = TRANSACTIONS.get(packet_id)
    if not tx:
        # Check idempotency store for processing state
        from idempotency import get_status
        status = get_status(packet_id)
        if status == "processing":
            return TransactionResponse(
                packet_id=packet_id,
                tx_id="pending",
                status="PROCESSING",
                reason="Transaction is being processed",
            )
        raise HTTPException(status_code=404, detail=f"Transaction {packet_id} not found")
    return TransactionResponse(**tx)

@router.get("/balances")
def get_balances():
    """Debug endpoint — shows current fake balance store."""
    return {upi: {"paise": bal, "rupees": bal / 100} for upi, bal in BALANCES.items()}

async def _notify_ws(packet_id: str, result: dict):
    """Fire-and-forget WebSocket notification."""
    try:
        from app.api.ws import notify
        await notify(packet_id, result)
    except Exception as e:
        logger.warning(f"WS notify failed: {e}")
