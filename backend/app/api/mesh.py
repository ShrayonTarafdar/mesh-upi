import time
from fastapi import APIRouter
from app.api.transactions import TRANSACTIONS, BALANCES
from app.api.banks import get_bank_registry

router = APIRouter(tags=["mesh"])

# Simulated relay node registry
# In prod this is populated by BLE discovery + relay node self-registration
RELAY_NODES: dict = {
    "relay_node_A": {"had_internet": True,  "last_seen": int(time.time()), "packets_relayed": 0},
    "relay_node_B": {"had_internet": False, "last_seen": int(time.time()), "packets_relayed": 0},
    "relay_node_C": {"had_internet": True,  "last_seen": int(time.time()), "packets_relayed": 0},
}

@router.get("/mesh/health")
def mesh_health():
    """
    Network stats for the mesh monitor screen.
    Shows relay node count, transaction stats, bank registry status.
    """
    now = int(time.time())
    total_tx     = len(TRANSACTIONS)
    success_tx   = sum(1 for t in TRANSACTIONS.values() if t["status"] == "SUCCESS")
    failed_tx    = sum(1 for t in TRANSACTIONS.values() if t["status"] == "FAILED")
    online_nodes = sum(1 for n in RELAY_NODES.values() if n["had_internet"])
    total_nodes  = len(RELAY_NODES)
    banks        = get_bank_registry()

    return {
        "timestamp": now,
        "relay_nodes": {
            "total":          total_nodes,
            "internet_capable": online_nodes,
            "offline_only":   total_nodes - online_nodes,
            "nodes":          RELAY_NODES,
        },
        "transactions": {
            "total":   total_tx,
            "success": success_tx,
            "failed":  failed_tx,
            "success_rate": f"{(success_tx/total_tx*100):.1f}%" if total_tx > 0 else "N/A",
        },
        "banks": {
            "registered": len(banks),
            "online":     sum(1 for b in banks.values() if b["online"]),
        },
        "balances": {
            upi: {"paise": bal, "rupees": bal/100}
            for upi, bal in BALANCES.items()
        },
    }

@router.post("/mesh/node/{node_id}/ping")
def ping_node(node_id: str, had_internet: bool = True):
    """Relay node self-registers or updates its status."""
    RELAY_NODES[node_id] = {
        "had_internet":    had_internet,
        "last_seen":       int(time.time()),
        "packets_relayed": RELAY_NODES.get(node_id, {}).get("packets_relayed", 0),
    }
    return {"node_id": node_id, "registered": True}
