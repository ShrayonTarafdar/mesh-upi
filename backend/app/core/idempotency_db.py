import sqlite3
import os
import time

# In production this will be psycopg2 + Supabase PostgreSQL.
# The SQL is identical — only the connection changes.
DB_PATH = "/tmp/mesh_upi_test.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None  # autocommit — each statement is its own transaction
    return conn

def init_db():
    """Create idempotency table if not exists. Migrations handle this in prod."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            key          TEXT PRIMARY KEY,
            tx_id        TEXT,
            result_status TEXT,
            created_at   INTEGER NOT NULL,
            expires_at   INTEGER NOT NULL
        )
    """)
    # This index makes the PRIMARY KEY lookup O(log n) — important under load
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_idem_key ON idempotency_keys(key)
    """)
    conn.close()

def acquire_db(packet_id: str) -> bool:
    """
    DB-level idempotency claim.
    INSERT OR IGNORE is SQLite's equivalent of PostgreSQL's ON CONFLICT DO NOTHING.
    Returns True if this process is the first claimant, False otherwise.
    """
    conn = get_conn()
    now = int(time.time())
    expires = now + 90
    key = f"idem:{packet_id}"
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO idempotency_keys (key, result_status, created_at, expires_at)
        VALUES (?, 'processing', ?, ?)
        """,
        (key, now, expires)
    )
    conn.close()
    return cursor.rowcount == 1  # 1 = inserted (winner), 0 = already existed (duplicate)

def mark_complete_db(packet_id: str, status: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE idempotency_keys SET result_status = ? WHERE key = ?",
        (status, f"idem:{packet_id}")
    )
    conn.close()

def get_status_db(packet_id: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT result_status FROM idempotency_keys WHERE key = ?",
        (f"idem:{packet_id}",)
    ).fetchone()
    conn.close()
    return row[0] if row else None

if __name__ == "__main__":
    init_db()
    print("DB init          : OK")

    test_id = "db_test_packet_xyz"

    # Clean slate
    conn = get_conn()
    conn.execute("DELETE FROM idempotency_keys WHERE key = ?", (f"idem:{test_id}",))
    conn.close()

    result1 = acquire_db(test_id)
    print(f"First acquire    : {result1}  <- must be True")

    result2 = acquire_db(test_id)
    print(f"Second acquire   : {result2}  <- must be False")

    result3 = acquire_db(test_id)
    print(f"Third acquire    : {result3}  <- must be False")

    mark_complete_db(test_id, "SUCCESS")
    status = get_status_db(test_id)
    print(f"Status after win : {status}  <- must be SUCCESS")

    result4 = acquire_db(test_id)
    print(f"Late duplicate   : {result4}  <- must be False")

    print("\nAll DB idempotency checks passed!" if result1 and not result2 and not result3 and not result4 else "\nSOMETHING FAILED")
