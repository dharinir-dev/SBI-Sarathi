"""
SBI Sarathi — Database and Persistence Layer
Handles SQLite storage for conversation memory and human RM escalations.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "sarathi.db"


def get_db_path() -> Path:
    """Return the configured SQLite database path."""
    return Path(os.environ.get("SARATHI_DB_PATH", DEFAULT_DB_PATH))


def get_db_connection() -> sqlite3.Connection:
    """Establish and return a connection to the SQLite database."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite tables for memory and escalations if they don't exist."""
    with get_db_connection() as conn:
        # Create memory table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                customer_id TEXT PRIMARY KEY,
                conversation_history TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)
        # Create escalations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS escalations (
                ticket_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                assigned_to TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def get_memory(customer_id: str) -> Optional[dict[str, Any]]:
    """Retrieve conversation memory for a customer."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT conversation_history, current_stage, last_updated FROM memory WHERE customer_id = ?",
            (customer_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            "customer_id": customer_id,
            "conversation_history": json.loads(row["conversation_history"]),
            "current_stage": row["current_stage"],
            "last_updated": row["last_updated"]
        }


def save_memory(customer_id: str, history: list[dict[str, Any]], stage: str) -> dict[str, Any]:
    """Save/update conversation memory for a customer."""
    init_db()
    now_iso = datetime.utcnow().isoformat() + "Z"
    history_json = json.dumps(history)
    
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO memory (customer_id, conversation_history, current_stage, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
                conversation_history = excluded.conversation_history,
                current_stage = excluded.current_stage,
                last_updated = excluded.last_updated
            """,
            (customer_id, history_json, stage, now_iso)
        )
        conn.commit()
        
    return {
        "customer_id": customer_id,
        "conversation_history": history,
        "current_stage": stage,
        "last_updated": now_iso
    }


def create_escalation(customer_id: str, reason: str) -> dict[str, Any]:
    """Create a new human RM escalation ticket for a customer."""
    init_db()
    now_iso = datetime.utcnow().isoformat() + "Z"
    
    with get_db_connection() as conn:
        # Generate ticket_id: RM-XXXX
        cursor = conn.execute("SELECT COUNT(*) as count FROM escalations")
        count = cursor.fetchone()["count"]
        ticket_id = f"RM-{count + 1:04d}"
        
        assigned_to = "Relationship Manager"
        status = "created"
        
        conn.execute(
            """
            INSERT INTO escalations (ticket_id, customer_id, reason, assigned_to, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO NOTHING
            """,
            (ticket_id, customer_id, reason, assigned_to, status, now_iso)
        )
        conn.commit()
        
    return {
        "ticket_id": ticket_id,
        "status": status,
        "assigned_to": assigned_to,
        "reason": reason,
        "created_at": now_iso
    }


def get_escalation(customer_id: str) -> Optional[dict[str, Any]]:
    """Retrieve escalation ticket for a customer if one exists."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT ticket_id, status, assigned_to, reason, created_at FROM escalations WHERE customer_id = ? ORDER BY created_at DESC LIMIT 1",
            (customer_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            "ticket_id": row["ticket_id"],
            "status": row["status"],
            "assigned_to": row["assigned_to"],
            "reason": row["reason"],
            "created_at": row["created_at"]
        }
