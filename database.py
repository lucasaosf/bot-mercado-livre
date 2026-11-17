import sqlite3
from datetime import datetime, timedelta
import os
from typing import List, Any

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

def is_already_posted(item_id: str, max_hours: float = 12.0) -> bool:
    """Verifica se o item já foi postado nas últimas max_hours horas."""
    cutoff = datetime.now() - timedelta(hours=max_hours)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM posted_deals WHERE item_id = ? AND posted_at >= ?",
            (item_id, cutoff.isoformat())
        ).fetchone()
        return row is not None

def filter_and_rank_deals(deals: List[Any], max_hours: float = 12.0) -> List[Any]:
    """
    Filtra ofertas que ainda não foram postadas nas últimas `max_hours`.
    Se a loja ficar com poucas ofertas (todas já postadas), reaproveita as postadas há mais tempo.
    Isso garante que todas as lojas (Mercado Livre, Amazon, AliExpress) NUNCA fiquem sem produtos,
    mantendo rigorosamente a proporção 1:1:1.
    """
    if not deals:
        return []

    cutoff = (datetime.now() - timedelta(hours=max_hours)).isoformat()
    with get_connection() as conn:
        cursor = conn.execute("SELECT item_id, posted_at FROM posted_deals")
        posted_map = dict(cursor.fetchall())

    fresh_deals = []
    older_deals = []

    for d in deals:
        last_posted = posted_map.get(d.item_id)
        if not last_posted:
            fresh_deals.append(d)
        elif last_posted < cutoff:
            fresh_deals.append(d)
        else:
            older_deals.append((last_posted, d))

    if fresh_deals:
        return fresh_deals

    # Se todas as ofertas da loja foram postadas recentemente no banco,
    # ordena da postada há mais tempo para a mais recente (FIFO)
    older_deals.sort(key=lambda x: x[0])
    return [d for _, d in older_deals]

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

def clear_deals():
    """Limpa a tabela para reset de contagem."""
    with get_connection() as conn:
        conn.execute("DELETE FROM posted_deals")
        conn.commit()

def get_posted_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as total FROM posted_deals").fetchone()
        return row["total"] if row else 0

if __name__ == "__main__":
    init_db()
    print("Banco de dados SQLite inicializado com sucesso!")
