import os
import httpx
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

def get_user(upi_id: str) -> dict | None:
    try:
        db = get_db()
        result = db.table("users").select("*").eq("upi_id", upi_id).execute()
        return result.data[0] if result.data else None
    except Exception:
        # Reconnect on next call
        global _client
        _client = None
        return None

def get_balance(upi_id: str) -> int:
    user = get_user(upi_id)
    return user["balance_paise"] if user else 0

def debit(upi_id: str, amount_paise: int) -> bool:
    try:
        db = get_db()
        user = get_user(upi_id)
        if not user or user["balance_paise"] < amount_paise:
            return False
        new_balance = user["balance_paise"] - amount_paise
        db.table("users").update({"balance_paise": new_balance}).eq("upi_id", upi_id).execute()
        return True
    except Exception:
        global _client
        _client = None
        return False

def credit(upi_id: str, amount_paise: int) -> None:
    try:
        db = get_db()
        user = get_user(upi_id)
        if not user:
            return
        new_balance = user["balance_paise"] + amount_paise
        db.table("users").update({"balance_paise": new_balance}).eq("upi_id", upi_id).execute()
    except Exception:
        global _client
        _client = None

def get_bank(ifsc_prefix: str) -> dict | None:
    try:
        db = get_db()
        result = db.table("banks").select("*").eq("ifsc_prefix", ifsc_prefix).execute()
        return result.data[0] if result.data else None
    except Exception:
        global _client
        _client = None
        return None

def register_bank(ifsc_prefix: str, rsa_pubkey_pem: str, api_endpoint: str) -> dict:
    db = get_db()
    result = db.table("banks").insert({
        "ifsc_prefix":    ifsc_prefix,
        "rsa_pubkey_pem": rsa_pubkey_pem,
        "api_endpoint":   api_endpoint,
        "online":         True,
    }).execute()
    return result.data[0]

def create_transaction(packet_id: str, sender_upi: str, recipient_upi: str,
                       amount_paise: int, bank_id: str | None, expires_at: str) -> dict:
    try:
        db = get_db()
        sender    = get_user(sender_upi)
        recipient = get_user(recipient_upi)
        insert_data = {
            "packet_id":    packet_id,
            "amount_paise": amount_paise,
            "status":       "PROCESSING",
            "expires_at":   expires_at,
        }
        if sender:
            insert_data["sender_id"] = sender["id"]
        if recipient:
            insert_data["recipient_id"] = recipient["id"]
        # Only include bank_id if it's a valid non-empty UUID
        if bank_id and len(bank_id) == 36:
            insert_data["bank_id"] = bank_id
        result = db.table("transactions").insert(insert_data).execute()
        return result.data[0]
    except Exception as e:
        raise Exception(e)

def settle_transaction(packet_id: str, status: str, error_code: str | None = None) -> None:
    try:
        db = get_db()
        update = {"status": status}
        if error_code:
            update["error_code"] = error_code
        db.table("transactions").update(update).eq("packet_id", packet_id).execute()
    except Exception:
        global _client
        _client = None

def get_transaction(packet_id: str) -> dict | None:
    try:
        db = get_db()
        result = db.table("transactions").select("*").eq("packet_id", packet_id).execute()
        return result.data[0] if result.data else None
    except Exception:
        global _client
        _client = None
        return None

def claim_idempotency(packet_id: str, expires_at: str) -> bool:
    try:
        db = get_db()
        result = db.table("idempotency_keys").insert({
            "key":           f"idem:{packet_id}",
            "result_status": "processing",
            "expires_at":    expires_at,
        }).execute()
        return len(result.data) > 0
    except Exception:
        return False
