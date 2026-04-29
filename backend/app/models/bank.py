from pydantic import BaseModel, Field
from typing import Optional

class BankRegisterRequest(BaseModel):
    ifsc_prefix: str = Field(..., example="SBI", description="First 4 chars of IFSC, unique per bank")
    rsa_pubkey_pem: str = Field(..., description="Bank's RSA-2048 public key in PEM format")
    api_endpoint: str = Field(..., example="https://bank.example.com/upi", description="Bank's UPI settlement endpoint")

class BankRegisterResponse(BaseModel):
    bank_id: str
    ifsc_prefix: str
    message: str

class BankInfo(BaseModel):
    bank_id: str
    ifsc_prefix: str
    api_endpoint: str
    online: bool
