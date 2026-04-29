import uuid
import json
import os
from fastapi import APIRouter, HTTPException
from app.models.bank import BankRegisterRequest, BankRegisterResponse, BankInfo

router = APIRouter(tags=["banks"])

# In-memory store for now — replaced by Supabase in Phase 4
# Structure: { ifsc_prefix: { bank_id, rsa_pubkey_pem, api_endpoint, online } }
BANK_REGISTRY: dict = {}

BANK_REGISTRY_FILE = "/tmp/mesh_upi_banks.json"

def _load():
    if os.path.exists(BANK_REGISTRY_FILE):
        with open(BANK_REGISTRY_FILE) as f:
            BANK_REGISTRY.update(json.load(f))

def _save():
    with open(BANK_REGISTRY_FILE, "w") as f:
        json.dump(BANK_REGISTRY, f)

_load()

@router.post("/bank/register", response_model=BankRegisterResponse, status_code=201)
def register_bank(req: BankRegisterRequest):
    """
    Admin endpoint — onboard a bank with its RSA public key.
    In prod this requires admin auth. For now open for demo purposes.
    """
    if req.ifsc_prefix in BANK_REGISTRY:
        raise HTTPException(status_code=409, detail=f"Bank {req.ifsc_prefix} already registered")

    # Validate it's actually a PEM public key
    if "BEGIN PUBLIC KEY" not in req.rsa_pubkey_pem:
        raise HTTPException(status_code=400, detail="rsa_pubkey_pem must be a PEM public key")

    bank_id = str(uuid.uuid4())
    BANK_REGISTRY[req.ifsc_prefix] = {
        "bank_id":        bank_id,
        "rsa_pubkey_pem": req.rsa_pubkey_pem,
        "api_endpoint":   req.api_endpoint,
        "online":         True,
    }
    _save()

    return BankRegisterResponse(
        bank_id=bank_id,
        ifsc_prefix=req.ifsc_prefix,
        message=f"Bank {req.ifsc_prefix} registered successfully",
    )

@router.get("/bank/{ifsc_prefix}", response_model=BankInfo)
def get_bank(ifsc_prefix: str):
    """Fetch bank info by IFSC prefix."""
    bank = BANK_REGISTRY.get(ifsc_prefix)
    if not bank:
        raise HTTPException(status_code=404, detail=f"Bank {ifsc_prefix} not found")
    return BankInfo(
        bank_id=bank["bank_id"],
        ifsc_prefix=ifsc_prefix,
        api_endpoint=bank["api_endpoint"],
        online=bank["online"],
    )

@router.get("/bank/{ifsc_prefix}/pubkey")
def get_bank_pubkey(ifsc_prefix: str):
    """Return bank's RSA public key — senders use this to wrap session keys."""
    bank = BANK_REGISTRY.get(ifsc_prefix)
    if not bank:
        raise HTTPException(status_code=404, detail=f"Bank {ifsc_prefix} not found")
    return {"ifsc_prefix": ifsc_prefix, "rsa_pubkey_pem": bank["rsa_pubkey_pem"]}

def get_bank_registry():
    """Exposed to other modules (transactions router needs it)."""
    return BANK_REGISTRY
