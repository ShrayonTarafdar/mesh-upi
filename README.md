cat > ~/mesh-upi/README.md << 'READMEEOF'
# Mesh UPI — Offline-First UPI Payment System

> BLE mesh networking + hybrid cryptography = UPI transactions without internet

**Live Demo:** https://mesh-upi-frontend-2.onrender.com
**API Docs:** https://mesh-upi-backend.onrender.com/docs
**GitHub:** https://github.com/ShrayonTarafdar/mesh-upi

---

## Tools & Technologies

| Category | Tool | Version |
|----------|------|---------|
| Backend | FastAPI (Python) | 3.12 |
| Frontend | Next.js + Tailwind CSS | 16 |
| Database | PostgreSQL via Supabase | — |
| Cache | Redis via Upstash | 7 |
| Crypto | Python `cryptography` lib | — |
| Containerisation | Docker + Docker Compose | 29.4 |
| Deployment | Render (backend + frontend) | — |
| Version Control | Git + GitHub | — |
| Runtime | Node.js | 22 |
| OS / Dev Env | WSL2 Ubuntu on Windows | 22.04 |

---

## The Problem

Standard UPI fails in three scenarios:
1. Bank servers go down
2. User has no internet
3. Even lite apps like Paytm Lite fail without connectivity

Root cause: UPI requires the sender to have internet to get bank permission before every transaction.

---

## The Solution

Distribute the permission-taking process. Instead of the sender needing internet, anyone nearby can relay the encrypted transaction packet to the bank via Bluetooth Low Energy (BLE) mesh networking.

Sender (no internet) │ │ BLE broadcast — AES-256-GCM encrypted, Ed25519 signed ▼ Relay Node A ──── has internet ──→ Bank Server Relay Node B ──── no internet ──→ rebroadcasts to next node Relay Node C ──── has internet ──→ Bank Server (duplicate dropped) │ │ BLE unicast — encrypted response ▼ Sender receives confirmation

Relay nodes never see transaction details — they only forward opaque encrypted blobs.

---

## Three Security Problems Solved

**Problem 1 — Eavesdropping**
AES-256-GCM payload encryption. Relay nodes see only ciphertext. No UPI PIN travels in the packet. Device biometric/PIN unlocks the private key which IS the authentication.

**Problem 2 — Replay Attacks**
Every packet has a 60s TTL and unique `packet_id = SHA256(sender+recipient+amount+nonce)`. Bank uses Redis `SET NX EX 90` to drop duplicates atomically.

**Problem 3 — Multiple Redundant Permissions**
If 3 relay nodes all forward simultaneously, idempotency ensures exactly one transaction executes. Redis is fast path, PostgreSQL `ON CONFLICT DO NOTHING` is safety net.

---

## Security Architecture

Every packet has three cryptographic layers:

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| Payload | AES-256-GCM | Only bank can read |
| Key wrap | RSA-OAEP | AES session key readable only by bank |
| Outer | Ed25519 signature | Anyone verifies, no one can forge |

Packet structure:
```json
{
  "header": {
    "packet_id": "SHA256(sender+recipient+amount+nonce)",
    "ttl_expires_at": 1777412244,
    "nonce": "16-byte random"
  },
  "encrypted_session_key": "RSA-OAEP(bank_pubkey, aes_session_key)",
  "gcm_nonce": "12-byte AES-GCM nonce",
  "encrypted_payload": "AES-256-GCM({sender, recipient, amount_paise, timestamp, nonce})",
  "signature": "Ed25519(sender_privkey, header || ciphertext)"
}
```

---

## Project Structure

mesh-upi/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── api/
│       │   ├── banks.py
│       │   ├── transactions.py
│       │   ├── mesh.py
│       │   ├── demo.py
│       │   └── ws.py
│       ├── core/
│       │   ├── idempotency.py
│       │   ├── idempotency_db.py
│       │   └── idempotency_guard.py
│       ├── models/
│       │   ├── bank.py
│       │   └── transaction.py
│       └── services/
│           └── db.py
├── crypto/
│   ├── keys.py
│   ├── aes.py
│   ├── rsa_wrap.py
│   ├── packet.py
│   └── verifier.py
├── frontend/
│   ├── Dockerfile
│   └── app/
│       ├── page.tsx
│       ├── send/page.tsx
│       ├── result/page.tsx
│       ├── mesh/page.tsx
│       └── history/page.tsx
├── database/
│   └── migrations/
│       └── 001_initial_schema.sql
└── docker-compose.yml
---

## API Endpoints

|Endpoint|Method|Description|
|---|---|---|
|`/health`|GET|Service health check|
|`/api/v1/bank/register`|POST|Register bank with RSA public key|
|`/api/v1/bank/{ifsc_prefix}`|GET|Get bank details|
|`/api/v1/transaction`|POST|Submit encrypted transaction packet|
|`/api/v1/transaction/{packet_id}`|GET|Poll transaction status|
|`/api/v1/balances`|GET|Get test user balances|
|`/api/v1/mesh/health`|GET|Mesh network stats|
|`/api/v1/demo/send`|POST|Demo endpoint — server-side packet builder|
|`/ws/transaction/{packet_id}`|WebSocket|Live status push|

---

## Running Locally

### Prerequisites

- WSL2 Ubuntu
- Python 3.12
- Node.js 22
- Redis running locally

### Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your values
sudo service redis-server start
uvicorn app.main:app --reload --port 8000

### Frontend
cd frontend
npm install
cp .env.local.example .env.local  # fill in your values
npm run dev

### With Docker Compose (local)
docker-compose up --build

---

## Environment Variables

### Backend (`backend/.env`)
DATABASE_URL=postgresql://...
REDIS_URL=rediss://...
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
BANK_PRIV_KEY_PEM=-----BEGIN PRIVATE KEY-----...

### Frontend (`frontend/.env.local`)
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...

---

## Database Schema
```sql
CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upi_id         TEXT UNIQUE NOT NULL,
    ed25519_pubkey TEXT NOT NULL,
    balance_paise  BIGINT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE banks (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ifsc_prefix    TEXT UNIQUE NOT NULL,
    rsa_pubkey_pem TEXT NOT NULL,
    api_endpoint   TEXT NOT NULL,
    online         BOOLEAN DEFAULT TRUE,
    last_seen      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE transactions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    packet_id     TEXT UNIQUE NOT NULL,
    sender_id     UUID REFERENCES users(id),
    recipient_id  UUID REFERENCES users(id),
    bank_id       UUID REFERENCES banks(id),
    amount_paise  BIGINT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'PROCESSING',
    error_code    TEXT,
    relay_node_id TEXT,
    initiated_at  TIMESTAMPTZ DEFAULT NOW(),
    settled_at    TIMESTAMPTZ,
    expires_at    TIMESTAMPTZ
);

CREATE TABLE idempotency_keys (
    key            TEXT PRIMARY KEY,
    transaction_id UUID REFERENCES transactions(id),
    result_status  TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    expires_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE relay_events (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID REFERENCES transactions(id),
    relay_node_id  TEXT NOT NULL,
    action         TEXT NOT NULL,
    had_internet   BOOLEAN DEFAULT FALSE,
    event_at       TIMESTAMPTZ DEFAULT NOW()
);
```

---

## What's Real vs Simulated

|Component|Status|Notes|
|---|---|---|
|Crypto pipeline|Real|Ed25519, AES-GCM, RSA-OAEP fully implemented and tested|
|Idempotency|Real|Redis + PostgreSQL, race-tested with 10 threads|
|FastAPI backend|Real|All endpoints live, Supabase connected|
|Supabase schema|Real|Migrations run, data persisting|
|WebSocket push|Real|Live push verified|
|BLE mesh layer|Simulated|Demo builds packet server-side; production would use BLE via native SDK|
|Multiple banks|Simulated|One bank server, one RSA keypair, labeled clearly|

---

## Test Results
TEST 1: Valid transaction alice → bob ₹100     PASS
TEST 2: Duplicate packet (replay attack)        PASS
TEST 3: Insufficient balance                    PASS
TEST 4: Balance check after transactions        PASS
TEST 5: Status polling                          PASS
WebSocket live push test                        PASS
Crypto verifier (4/4 edge cases)               PASS
Race condition (10 threads, 1 winner)           PASS

---

## Author

**Shrayon Tarafdar** GitHub: [@ShrayonTarafdar](https://github.com/ShrayonTarafdar)
