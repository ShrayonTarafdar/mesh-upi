import sys
import os
import uuid
import base64
import logging
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../crypto"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../core"))

from fastapi import APIRouter, HTTPException
from app.models.transaction import TransactionRequest, TransactionResponse
from app.api.banks import get_bank_registry
from app.services.db import (
    get_user, get_balance, debit, credit,
    create_transaction, settle_transaction, get_transaction,
    get_bank, claim_idempotency
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["transactions"])

# Keep in-memory cache for WebSocket notify + mesh health
TRANSACTIONS: dict = {}

def _load_bank_private_key():
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    pem_data = os.getenv("BANK_PRIV_KEY_PEM")
    if pem_data:
        return load_pem_private_key(pem_data.encode(), password=None)
    path = os.getenv("BANK_PRIV_KEY_PATH", "/tmp/test_bank_priv.pem")
    with open(path, "rb") as f:
        return load_pem_private_key(f.read(), password=None)

@router.post("/transaction", response_model=TransactionResponse, status_code=200)
def process_transaction(req: TransactionRequest):
    packet_id = req.header.get("packet_id")
    if not packet_id:
        raise HTTPException(status_code=400, detail="Missing packet_id in header")

    # Step 1 — check in-memory cache first (fastest path for duplicates)
    if packet_id in TRANSACTIONS:
        return TransactionResponse(**TRANSACTIONS[packet_id])

    # Step 2 — look up bank
    registry = get_bank_registry()
    if req.ifsc_prefix not in registry:
        raise HTTPException(status_code=404, detail=f"Bank {req.ifsc_prefix} not registered")

    bank_record = get_bank(req.ifsc_prefix)
    bank_id     = bank_record["id"] if bank_record else None
    bank_priv   = _load_bank_private_key()

    # Step 3 — full crypto verification
    from verifier import verify_packet
    packet = {
        "header":                req.header,
        "encrypted_session_key": req.encrypted_session_key,
        "gcm_nonce":             req.gcm_nonce,
        "encrypted_payload":     req.encrypted_payload,
        "signature":             req.signature,
    }
    sender_pub   = base64.b64decode(req.sender_pub_key_b64)
    verification = verify_packet(packet, sender_pub, bank_priv)

    if not verification["decryption_ok"]:
        logger.warning(f"Packet {packet_id} failed verification: {verification['error']}")
        return TransactionResponse(
            packet_id=packet_id,
            tx_id="none",
            status="FAILED",
            reason=verification["error"],
        )

    payload       = verification["payload"]
    sender_upi    = payload["sender_upi"]
    recipient_upi = payload["recipient_upi"]
    amount_paise  = payload["amount_paise"]
    ttl           = req.header.get("ttl_expires_at", int(time.time()) + 60)
    expires_at    = datetime.fromtimestamp(ttl, tz=timezone.utc).isoformat()

    # Step 4 — Redis idempotency (fast path)
    from idempotency_guard import claim, complete
    from idempotency_db import init_db
    init_db()

    redis_claimed = claim(packet_id)

    # Step 5 — PostgreSQL idempotency (safety net)
    db_claimed = claim_idempotency(packet_id, expires_at)

    if not redis_claimed and not db_claimed:
        # Both stores say duplicate — return cached result
        existing = get_transaction(packet_id)
        if existing:
            result = TransactionResponse(
                packet_id=packet_id,
                tx_id=str(existing["id"]),
                status=existing["status"],
                reason=existing.get("error_code"),
                sender_upi=sender_upi,
                recipient_upi=recipient_upi,
                amount_paise=amount_paise,
            )
            TRANSACTIONS[packet_id] = result.model_dump()
            return result
        return TransactionResponse(
            packet_id=packet_id,
            tx_id="duplicate",
            status="FAILED",
            reason="Duplicate packet — already processed",
        )

    # Step 6 — create transaction record in Supabase
    try:
        tx_record = create_transaction(
            packet_id     = packet_id,
            sender_upi    = sender_upi,
            recipient_upi = recipient_upi,
            amount_paise  = amount_paise,
            bank_id       = bank_id or "",
            expires_at    = expires_at,
        )
        tx_id = str(tx_record["id"])
    except Exception as e:
        logger.error(f"Failed to create transaction record: {e}")
        tx_id = str(uuid.uuid4())

    # Step 7 — balance check + debit/credit
    sender_balance = get_balance(sender_upi)
    if sender_balance < amount_paise:
        settle_transaction(packet_id, "FAILED", "INSUFFICIENT_BALANCE")
        complete(packet_id, "FAILED")
        result = TransactionResponse(
            packet_id     = packet_id,
            tx_id         = tx_id,
            status        = "FAILED",
            reason        = f"Insufficient balance: have {sender_balance} paise, need {amount_paise} paise",
            sender_upi    = sender_upi,
            recipient_upi = recipient_upi,
            amount_paise  = amount_paise,
        )
    else:
        debit(sender_upi, amount_paise)
        credit(recipient_upi, amount_paise)
        settle_transaction(packet_id, "SUCCESS")
        complete(packet_id, "SUCCESS")
        logger.info(f"TX {tx_id}: {sender_upi} → {recipient_upi} {amount_paise} paise")
        result = TransactionResponse(
            packet_id     = packet_id,
            tx_id         = tx_id,
            status        = "SUCCESS",
            sender_upi    = sender_upi,
            recipient_upi = recipient_upi,
            amount_paise  = amount_paise,
        )

    TRANSACTIONS[packet_id] = result.model_dump()
    return result

@router.get("/transaction/{packet_id}", response_model=TransactionResponse)
def get_transaction_status(packet_id: str):
    # Check memory cache first
    if packet_id in TRANSACTIONS:
        return TransactionResponse(**TRANSACTIONS[packet_id])
    # Fall back to Supabase
    tx = get_transaction(packet_id)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction {packet_id} not found")
    return TransactionResponse(
        packet_id     = tx["packet_id"],
        tx_id         = str(tx["id"]),
        status        = tx["status"],
        reason        = tx.get("error_code"),
        amount_paise  = tx["amount_paise"],
    )

@router.get("/balances")
def get_balances():
    from app.services.db import get_user
    users = ["alice@upi", "bob@upi"]
    return {
        upi: {
            "paise":  get_balance(upi),
            "rupees": get_balance(upi) / 100
        }
        for upi in users
    }

async def _notify_ws(packet_id: str, result: dict):
    try:
        from app.api.ws import notify
        await notify(packet_id, result)
    except Exception as e:
        logger.warning(f"WS notify failed: {e}")
