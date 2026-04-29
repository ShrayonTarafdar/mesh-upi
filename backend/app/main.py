import sys
import os
sys.path.insert(0, os.path.dirname(__file__) + "/core")
sys.path.insert(0, os.path.dirname(__file__) + "/../../crypto")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import banks, transactions, mesh

app = FastAPI(
    title="Mesh UPI",
    description="Offline-first UPI via BLE mesh with hybrid cryptography",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(banks.router,        prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(mesh.router,         prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "ok", "service": "mesh-upi-backend"}
