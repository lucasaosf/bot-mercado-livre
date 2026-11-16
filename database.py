import sqlite3
from datetime import datetime, timedelta
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "deals.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT UNIQUE,
                title TEXT,
                price REAL,
                original_price REAL,
                discount_pct INTEGER,
                affiliate_url TEXT,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def is_already_posted(item_id: str, max_days: int = 3) -> bool:
    """Verifica se o item já foi postado nos últimos max_days dias."""
    cutoff = datetime.now() - timedelta(days=max_days)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM posted_deals WHERE item_id = ? AND posted_at >= ?",
            (item_id, cutoff.isoformat())
        ).fetchone()
        return row is not None

def mark_as_posted(deal) -> None:
    """Registra o item como postado para evitar repetição."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO posted_deals (item_id, title, price, original_price, discount_pct, affiliate_url, posted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            deal.item_id,
            deal.title,
            deal.price,
            deal.original_price,
            deal.discount_pct,
            deal.affiliate_url,
            datetime.now().isoformat()
        ))
        conn.commit()

def get_posted_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as total FROM posted_deals").fetchone()
        return row["total"] if row else 0

if __name__ == "__main__":
    init_db()
    print("Banco de dados SQLite inicializado com sucesso!")
