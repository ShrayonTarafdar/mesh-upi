import asyncio
import json
import time
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# Active WebSocket connections keyed by packet_id
# { packet_id: [WebSocket, ...] }
CONNECTIONS: dict[str, list[WebSocket]] = {}

async def notify(packet_id: str, result: dict) -> None:
    """
    Called by the transaction endpoint after completing a transaction.
    Pushes result to all WebSocket clients waiting on this packet_id.
    """
    sockets = CONNECTIONS.get(packet_id, [])
    dead = []
    for ws in sockets:
        try:
            await ws.send_text(json.dumps(result))
        except Exception:
            dead.append(ws)
    # Clean up dead connections
    for ws in dead:
        sockets.remove(ws)

@router.websocket("/ws/transaction/{packet_id}")
async def transaction_ws(websocket: WebSocket, packet_id: str):
    """
    Client connects here with a packet_id immediately after broadcasting.
    Server pushes the result when the bank processes it.
    Times out after 90s (packet TTL) if no result arrives.
    """
    await websocket.accept()
    logger.info(f"WS client connected for packet {packet_id}")

    # Register this connection
    if packet_id not in CONNECTIONS:
        CONNECTIONS[packet_id] = []
    CONNECTIONS[packet_id].append(websocket)

    # Check if already processed (client reconnecting after brief disconnect)
    from app.api.transactions import TRANSACTIONS
    if packet_id in TRANSACTIONS:
        await websocket.send_text(json.dumps(TRANSACTIONS[packet_id]))
        await websocket.close()
        return

    try:
        # Wait up to 90s for a result push from notify()
        # Heartbeat every 5s so client knows connection is alive
        deadline = time.time() + 90
        while time.time() < deadline:
            await asyncio.sleep(5)
            # Check if result arrived
            if packet_id in TRANSACTIONS:
                await websocket.send_text(json.dumps(TRANSACTIONS[packet_id]))
                break
            # Send heartbeat
            try:
                await websocket.send_text(json.dumps({"status": "WAITING", "packet_id": packet_id}))
            except Exception:
                break
        else:
            await websocket.send_text(json.dumps({
                "status": "TIMEOUT",
                "packet_id": packet_id,
                "reason": "No relay node with internet found within 90s"
            }))
    except WebSocketDisconnect:
        logger.info(f"WS client disconnected for packet {packet_id}")
    finally:
        if packet_id in CONNECTIONS:
            try:
                CONNECTIONS[packet_id].remove(websocket)
            except ValueError:
                pass
