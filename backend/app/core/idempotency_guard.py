import logging
from idempotency import acquire as redis_acquire, mark_complete, get_status
from idempotency_db import acquire_db, mark_complete_db, init_db

logger = logging.getLogger(__name__)

def claim(packet_id: str) -> bool:
    """
    Full idempotency claim with Redis → DB fallback.

    Redis is the fast path (microsecond).
    DB is the safety net if Redis is down or flaps.
    Both must agree — if Redis says yes but DB says no, we reject.
    """
    try:
        redis_ok = redis_acquire(packet_id)
        if not redis_ok:
            logger.debug(f"Redis rejected duplicate: {packet_id}")
            return False
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}), falling back to DB only")
        redis_ok = None  # Redis is down — proceed to DB check

    db_ok = acquire_db(packet_id)
    if not db_ok:
        logger.debug(f"DB rejected duplicate: {packet_id}")
        return False

    return True

def complete(packet_id: str, status: str) -> None:
    """Mark transaction complete in both stores."""
    try:
        mark_complete(packet_id, status)
    except Exception:
        pass  # Redis down is fine — DB is source of truth for status
    mark_complete_db(packet_id, status)


if __name__ == "__main__":
    import sys
    import time
    import threading
    sys.path.insert(0, "backend/app/core")

    init_db()

    # ── Test 1: basic combined flow ───────────────────────────────────────────
    print("=" * 50)
    print("TEST 1: Basic combined claim")
    print("=" * 50)

    test_id = "race_test_packet_001"

    # Clean slate in both stores
    import redis as _r
    import sqlite3
    _r.from_url("redis://localhost:6379/0").delete(f"idem:{test_id}")
    conn = sqlite3.connect("/tmp/mesh_upi_test.db")
    conn.execute("DELETE FROM idempotency_keys WHERE key = ?", (f"idem:{test_id}",))
    conn.commit(); conn.close()

    r1 = claim(test_id)
    print(f"First claim      : {r1}  <- must be True")
    r2 = claim(test_id)
    print(f"Second claim     : {r2}  <- must be False")

    complete(test_id, "SUCCESS")
    r3 = claim(test_id)
    print(f"Post-complete    : {r3}  <- must be False")

    # ── Test 2: race simulation — 10 threads, same packet_id ─────────────────
    print("\n" + "=" * 50)
    print("TEST 2: Race simulation — 10 threads, 1 winner")
    print("=" * 50)

    race_id = "race_test_packet_002"
    _r.from_url("redis://localhost:6379/0").delete(f"idem:{race_id}")
    conn = sqlite3.connect("/tmp/mesh_upi_test.db")
    conn.execute("DELETE FROM idempotency_keys WHERE key = ?", (f"idem:{race_id}",))
    conn.commit(); conn.close()

    winners = []
    losers  = []
    lock    = threading.Lock()

    def try_claim(thread_num):
        result = claim(race_id)
        with lock:
            if result:
                winners.append(thread_num)
                print(f"  Thread {thread_num:02d}       : WON")
            else:
                losers.append(thread_num)
                print(f"  Thread {thread_num:02d}       : lost (duplicate blocked)")

    threads = [threading.Thread(target=try_claim, args=(i,)) for i in range(10)]

    # Start all threads as close together as possible
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"\nWinners          : {len(winners)}  <- must be exactly 1")
    print(f"Losers           : {len(losers)}   <- must be exactly 9")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Basic claim      : {'PASS' if r1 and not r2 and not r3 else 'FAIL'}")
    print(f"Race condition   : {'PASS' if len(winners) == 1 and len(losers) == 9 else 'FAIL'}")
