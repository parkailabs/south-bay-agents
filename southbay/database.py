"""Database module for storing agents, transactions, and outreach records."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

# Database file location
DB_PATH = Path.home() / ".southbay_agents.db"


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Agents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            brokerage TEXT,
            email TEXT,
            phone TEXT,
            instagram TEXT,
            linkedin TEXT,
            notes TEXT,
            is_team_agent BOOLEAN DEFAULT 0,
            priority TEXT DEFAULT 'normal',
            do_not_contact BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Transactions table (listings and sales)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            city TEXT,
            transaction_type TEXT NOT NULL,
            price INTEGER,
            transaction_date DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)

    # Outreach table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outreach (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            outreach_date DATE NOT NULL,
            method TEXT,
            message_type TEXT,
            notes TEXT,
            response_status TEXT DEFAULT 'no_response',
            follow_up_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)

    conn.commit()
    conn.close()


# --- Agent Functions ---

def add_agent(
    name: str,
    brokerage: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    instagram: Optional[str] = None,
    linkedin: Optional[str] = None,
    notes: Optional[str] = None,
    is_team_agent: bool = False,
    priority: str = "normal"
) -> int:
    """Add a new agent to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO agents (name, brokerage, email, phone, instagram, linkedin, notes, is_team_agent, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, brokerage, email, phone, instagram, linkedin, notes, is_team_agent, priority))
    agent_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return agent_id


def get_agent_by_name(name: str) -> Optional[sqlite3.Row]:
    """Get agent by name (case-insensitive partial match)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM agents WHERE LOWER(name) LIKE LOWER(?)
    """, (f"%{name}%",))
    result = cursor.fetchone()
    conn.close()
    return result


def get_agent_by_id(agent_id: int) -> Optional[sqlite3.Row]:
    """Get agent by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
    result = cursor.fetchone()
    conn.close()
    return result


def list_agents(
    brokerage: Optional[str] = None,
    priority: Optional[str] = None,
    include_dnc: bool = False
) -> list:
    """List all agents with optional filters."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM agents WHERE 1=1"
    params = []

    if not include_dnc:
        query += " AND do_not_contact = 0"

    if brokerage:
        query += " AND LOWER(brokerage) LIKE LOWER(?)"
        params.append(f"%{brokerage}%")

    if priority:
        query += " AND priority = ?"
        params.append(priority)

    query += " ORDER BY name"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


def update_agent(agent_id: int, **kwargs) -> bool:
    """Update agent fields."""
    allowed_fields = ['name', 'brokerage', 'email', 'phone', 'instagram', 'linkedin',
                      'notes', 'is_team_agent', 'priority', 'do_not_contact']

    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
    if not updates:
        return False

    updates['updated_at'] = datetime.now().isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [agent_id]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE agents SET {set_clause} WHERE id = ?", values)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def mark_do_not_contact(agent_id: int, dnc: bool = True) -> bool:
    """Mark an agent as do not contact."""
    return update_agent(agent_id, do_not_contact=dnc)


# --- Transaction Functions ---

def add_transaction(
    agent_id: int,
    address: str,
    transaction_type: str,
    city: Optional[str] = None,
    price: Optional[int] = None,
    transaction_date: Optional[str] = None,
    notes: Optional[str] = None
) -> int:
    """Add a transaction (listing or sale) for an agent."""
    conn = get_connection()
    cursor = conn.cursor()

    if transaction_date is None:
        transaction_date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO transactions (agent_id, address, city, transaction_type, price, transaction_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (agent_id, address, city, transaction_type, price, transaction_date, notes))

    txn_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return txn_id


def get_agent_transactions(agent_id: int, days: Optional[int] = None) -> list:
    """Get transactions for an agent, optionally filtered by recency."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM transactions WHERE agent_id = ?"
    params = [agent_id]

    if days:
        query += " AND transaction_date >= date('now', ?)"
        params.append(f"-{days} days")

    query += " ORDER BY transaction_date DESC"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


def get_recent_transactions(days: int = 30, city: Optional[str] = None) -> list:
    """Get all recent transactions across agents."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT t.*, a.name as agent_name, a.brokerage
        FROM transactions t
        JOIN agents a ON t.agent_id = a.id
        WHERE t.transaction_date >= date('now', ?)
    """
    params = [f"-{days} days"]

    if city:
        query += " AND LOWER(t.city) LIKE LOWER(?)"
        params.append(f"%{city}%")

    query += " ORDER BY t.transaction_date DESC"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


def count_agent_transactions(agent_id: int, days: int = 30) -> int:
    """Count transactions for an agent in the given period."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE agent_id = ? AND transaction_date >= date('now', ?)
    """, (agent_id, f"-{days} days"))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# --- Outreach Functions ---

def log_outreach(
    agent_id: int,
    method: str,
    message_type: Optional[str] = None,
    notes: Optional[str] = None,
    response_status: str = "no_response",
    follow_up_date: Optional[str] = None,
    outreach_date: Optional[str] = None
) -> int:
    """Log an outreach attempt."""
    conn = get_connection()
    cursor = conn.cursor()

    if outreach_date is None:
        outreach_date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO outreach (agent_id, outreach_date, method, message_type, notes, response_status, follow_up_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (agent_id, outreach_date, method, message_type, notes, response_status, follow_up_date))

    outreach_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return outreach_id


def get_last_outreach(agent_id: int) -> Optional[sqlite3.Row]:
    """Get the most recent outreach for an agent."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM outreach
        WHERE agent_id = ?
        ORDER BY outreach_date DESC
        LIMIT 1
    """, (agent_id,))
    result = cursor.fetchone()
    conn.close()
    return result


def get_agent_outreach_history(agent_id: int) -> list:
    """Get all outreach history for an agent."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM outreach
        WHERE agent_id = ?
        ORDER BY outreach_date DESC
    """, (agent_id,))
    results = cursor.fetchall()
    conn.close()
    return results


def get_due_followups(as_of_date: Optional[str] = None) -> list:
    """Get agents with follow-ups due."""
    conn = get_connection()
    cursor = conn.cursor()

    if as_of_date is None:
        as_of_date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT o.*, a.name as agent_name, a.brokerage, a.email, a.phone
        FROM outreach o
        JOIN agents a ON o.agent_id = a.id
        WHERE o.follow_up_date <= ?
        AND o.response_status NOT IN ('positive', 'not_interested')
        AND a.do_not_contact = 0
        AND o.id = (
            SELECT MAX(o2.id) FROM outreach o2 WHERE o2.agent_id = o.agent_id
        )
        ORDER BY o.follow_up_date
    """, (as_of_date,))

    results = cursor.fetchall()
    conn.close()
    return results


def update_outreach_response(outreach_id: int, response_status: str, notes: Optional[str] = None) -> bool:
    """Update the response status of an outreach."""
    conn = get_connection()
    cursor = conn.cursor()

    if notes:
        cursor.execute("""
            UPDATE outreach SET response_status = ?, notes = notes || ' | Response: ' || ?
            WHERE id = ?
        """, (response_status, notes, outreach_id))
    else:
        cursor.execute("""
            UPDATE outreach SET response_status = ? WHERE id = ?
        """, (response_status, outreach_id))

    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


# --- Reporting Functions ---

def get_hot_agents(min_transactions: int = 3, days: int = 30) -> list:
    """Get agents with high recent activity."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, COUNT(t.id) as transaction_count,
               MAX(t.transaction_date) as latest_transaction
        FROM agents a
        JOIN transactions t ON a.id = t.agent_id
        WHERE t.transaction_date >= date('now', ?)
        AND a.do_not_contact = 0
        GROUP BY a.id
        HAVING COUNT(t.id) >= ?
        ORDER BY transaction_count DESC, latest_transaction DESC
    """, (f"-{days} days", min_transactions))
    results = cursor.fetchall()
    conn.close()
    return results


def get_agents_needing_outreach(min_days_since_contact: int = 30) -> list:
    """Get agents with recent activity who haven't been contacted recently."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*,
               COUNT(t.id) as recent_transactions,
               MAX(t.transaction_date) as latest_transaction,
               (SELECT MAX(o.outreach_date) FROM outreach o WHERE o.agent_id = a.id) as last_outreach
        FROM agents a
        JOIN transactions t ON a.id = t.agent_id
        WHERE t.transaction_date >= date('now', '-30 days')
        AND a.do_not_contact = 0
        GROUP BY a.id
        HAVING last_outreach IS NULL
           OR last_outreach <= date('now', ?)
        ORDER BY recent_transactions DESC
    """, (f"-{min_days_since_contact} days",))
    results = cursor.fetchall()
    conn.close()
    return results


def get_agent_stats(agent_id: int) -> dict:
    """Get comprehensive stats for an agent."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total transactions
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE agent_id = ?", (agent_id,))
    total_txns = cursor.fetchone()[0]

    # Last 30 days
    cursor.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE agent_id = ? AND transaction_date >= date('now', '-30 days')
    """, (agent_id,))
    recent_txns = cursor.fetchone()[0]

    # Last 12 months
    cursor.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE agent_id = ? AND transaction_date >= date('now', '-365 days')
    """, (agent_id,))
    yearly_txns = cursor.fetchone()[0]

    # Total outreach
    cursor.execute("SELECT COUNT(*) FROM outreach WHERE agent_id = ?", (agent_id,))
    total_outreach = cursor.fetchone()[0]

    # Last outreach
    cursor.execute("""
        SELECT outreach_date, response_status FROM outreach
        WHERE agent_id = ? ORDER BY outreach_date DESC LIMIT 1
    """, (agent_id,))
    last_outreach = cursor.fetchone()

    conn.close()

    return {
        "total_transactions": total_txns,
        "transactions_30d": recent_txns,
        "transactions_yearly": yearly_txns,
        "total_outreach": total_outreach,
        "last_outreach_date": last_outreach["outreach_date"] if last_outreach else None,
        "last_outreach_status": last_outreach["response_status"] if last_outreach else None,
    }


# Initialize database on import
init_db()
