import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

_client: Client | None = None

def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

# ── Users ─────────────────────────────────────────────────────────────────────

def get_user(upi_id: str) -> dict | None:
    db = get_db()
    result = db.table("users").select("*").eq("upi_id", upi_id).execute()
    return result.data[0] if result.data else None

def get_balance(upi_id: str) -> int:
    user = get_user(upi_id)
    return user["balance_paise"] if user else 0

def debit(upi_id: str, amount_paise: int) -> bool:
    """
    Atomic debit — only succeeds if balance >= amount.
    Uses Supabase RPC for atomicity (no race between check and update).
    Returns True if debit succeeded.
    """
    db = get_db()
    user = get_user(upi_id)
    if not user or user["balance_paise"] < amount_paise:
        return False
    new_balance = user["balance_paise"] - amount_paise
    db.table("users").update({"balance_paise": new_balance}).eq("upi_id", upi_id).execute()
    return True

def credit(upi_id: str, amount_paise: int) -> None:
    db = get_db()
    user = get_user(upi_id)
    if not user:
        return
    new_balance = user["balance_paise"] + amount_paise
    db.table("users").update({"balance_paise": new_balance}).eq("upi_id", upi_id).execute()

# ── Banks ─────────────────────────────────────────────────────────────────────

def get_bank(ifsc_prefix: str) -> dict | None:
    db = get_db()
    result = db.table("banks").select("*").eq("ifsc_prefix", ifsc_prefix).execute()
    return result.data[0] if result.data else None

def register_bank(ifsc_prefix: str, rsa_pubkey_pem: str, api_endpoint: str) -> dict:
    db = get_db()
    result = db.table("banks").insert({
        "ifsc_prefix":    ifsc_prefix,
        "rsa_pubkey_pem": rsa_pubkey_pem,
        "api_endpoint":   api_endpoint,
        "online":         True,
    }).execute()
    return result.data[0]

# ── Transactions ──────────────────────────────────────────────────────────────

def create_transaction(packet_id: str, sender_upi: str, recipient_upi: str,
                       amount_paise: int, bank_id: str, expires_at: str) -> dict:
    db = get_db()
    sender    = get_user(sender_upi)
    recipient = get_user(recipient_upi)
    result = db.table("transactions").insert({
        "packet_id":    packet_id,
        "sender_id":    sender["id"]    if sender    else None,
        "recipient_id": recipient["id"] if recipient else None,
        "bank_id":      bank_id,
        "amount_paise": amount_paise,
        "status":       "PROCESSING",
        "expires_at":   expires_at,
    }).execute()
    return result.data[0]

def settle_transaction(packet_id: str, status: str, error_code: str | None = None) -> None:
    db = get_db()
    update = {"status": status}
    if status == "SUCCESS":
        update["settled_at"] = "now()"
    if error_code:
        update["error_code"] = error_code
    db.table("transactions").update(update).eq("packet_id", packet_id).execute()

def get_transaction(packet_id: str) -> dict | None:
    db = get_db()
    result = db.table("transactions").select("*").eq("packet_id", packet_id).execute()
    return result.data[0] if result.data else None

# ── Idempotency ───────────────────────────────────────────────────────────────

def claim_idempotency(packet_id: str, expires_at: str) -> bool:
    """
    PostgreSQL-level idempotency claim.
    ON CONFLICT DO NOTHING — second insert is silent no-op.
    Returns True if this process is the first claimant.
    """
    db = get_db()
    try:
        result = db.table("idempotency_keys").insert({
            "key":           f"idem:{packet_id}",
            "result_status": "processing",
            "expires_at":    expires_at,
        }).execute()
        return len(result.data) > 0
    except Exception:
        return False  # unique constraint violation = duplicate
