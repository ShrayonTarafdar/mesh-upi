from pydantic import BaseModel, Field
from typing import Optional

class TransactionRequest(BaseModel):
    # Full packet fields
    header: dict = Field(..., description="Cleartext header with packet_id, ttl_expires_at, nonce")
    encrypted_session_key: str = Field(..., description="RSA-OAEP wrapped AES key (base64)")
    gcm_nonce: str = Field(..., description="AES-GCM nonce (base64)")
    encrypted_payload: str = Field(..., description="AES-GCM ciphertext (base64)")
    signature: str = Field(..., description="Ed25519 signature (base64)")
    # Extra fields relay node adds
    sender_pub_key_b64: str = Field(..., description="Sender's Ed25519 public key (base64)")
    ifsc_prefix: str = Field(..., description="Bank IFSC prefix to route to correct bank")

class TransactionResponse(BaseModel):
    packet_id: str
    tx_id: str
    status: str        # SUCCESS | FAILED
    reason: Optional[str] = None
    sender_upi: Optional[str] = None
    recipient_upi: Optional[str] = None
    amount_paise: Optional[int] = None
