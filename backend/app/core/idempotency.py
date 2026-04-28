import redis
import logging

logger = logging.getLogger(__name__)

REDIS_URL = "redis://localhost:6379/0"
TTL_SECONDS = 90  # slightly longer than packet TTL (60s) to cover clock skew

def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True)

def acquire(packet_id: str) -> bool:
    """
    Attempt to claim this packet_id.
    Returns True  — first claimant, proceed with transaction.
    Returns False — already claimed, drop this duplicate.

    Uses SET NX EX — atomic in Redis, no race condition possible.
    """
    r = get_redis()
    key = f"idem:{packet_id}"
    result = r.set(key, "processing", nx=True, ex=TTL_SECONDS)
    return result is True

def mark_complete(packet_id: str, tx_status: str) -> None:
    """Update key value to final status — keep TTL so late duplicates still get dropped."""
    r = get_redis()
    key = f"idem:{packet_id}"
    ttl = r.ttl(key)
    if ttl > 0:
        r.set(key, tx_status, ex=ttl)

def get_status(packet_id: str) -> str | None:
    """Check if packet was already processed. Returns status string or None."""
    r = get_redis()
    return r.get(f"idem:{packet_id}")

if __name__ == "__main__":
    import time

    r = get_redis()
    r.ping()
    print("Redis connection : OK")

    test_id = "test_packet_abc123"
    r.delete(f"idem:{test_id}")  # clean slate

    # First acquire — should succeed
    result1 = acquire(test_id)
    print(f"First acquire    : {result1}  <- must be True")

    # Second acquire — should fail (duplicate)
    result2 = acquire(test_id)
    print(f"Second acquire   : {result2}  <- must be False")

    # Third acquire — still fails
    result3 = acquire(test_id)
    print(f"Third acquire    : {result3}  <- must be False")

    # Check TTL is set
    ttl = r.ttl(f"idem:{test_id}")
    print(f"TTL remaining    : {ttl}s  <- must be ~90")

    # Mark complete and check status
    mark_complete(test_id, "SUCCESS")
    status = get_status(test_id)
    print(f"Status after win : {status}  <- must be SUCCESS")

    # Simulate late duplicate arriving after completion
    result4 = acquire(test_id)
    print(f"Late duplicate   : {result4}  <- must be False")

    print("\nAll idempotency checks passed!" if not result2 and not result3 and not result4 and result1 else "\nSOMETHING FAILED")
