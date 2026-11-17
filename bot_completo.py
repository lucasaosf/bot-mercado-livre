"""
=============================================================================
🤖 BOT DE OFERTAS MERCADO LIVRE (AFILIADOS + TELEGRAM) - SCRIPT ÚNICO
=============================================================================
Script completo e autocontido para rodar facilmente em painéis Python, VPS ou nuvem.
Dependências necessárias:
    pip install requests curl_cffi beautifulsoup4 urllib3
=============================================================================
"""

import os
import sys
import time
import re
import socket
import sqlite3
import urllib.parse
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List
import requests
import urllib3.util.connection as urllib3_cn
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

# 1. FORÇA RESOLUÇÃO IPV4 (Evita travamentos de conexão com a API do Telegram)
urllib3_cn.allowed_gai_family = lambda: socket.AF_INET

# =============================================================================
# ⚙️ CONFIGURAÇÕES PRINCIPAIS (Preencha aqui ou configure via variáveis de ambiente)
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "SEU_BOT_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")

# Parâmetros de Afiliado Mercado Livre
MATT_TOOL = os.getenv("MATT_TOOL", "SEU_MATT_TOOL_AQUI")
MATT_WORD = os.getenv("MATT_WORD", "SEU_MATT_WORD_AQUI")

# Filtros e Ritmo de Envio
MIN_DISCOUNT_PCT = int(os.getenv("MIN_DISCOUNT_PCT", "20"))      # Desconto mínimo (%)
ACTIVE_SEND_MINUTES = int(os.getenv("ACTIVE_SEND_MINUTES", "5")) # Minutos enviando ofertas sem parar
REST_MINUTES = int(os.getenv("REST_MINUTES", "10"))              # Minutos de descanso
POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "6"))   # Intervalo entre envios (segundos)
REPOST_AFTER_DAYS = int(os.getenv("REPOST_AFTER_DAYS", "3"))     # Dias de carência antes de reenviar o mesmo item

# =============================================================================
# 🗄️ BANCO DE DADOS SQLITE LOCAL (Controle anti-repetição)
# =============================================================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deals.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
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
    cutoff = datetime.now() - timedelta(days=max_days)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM posted_deals WHERE item_id = ? AND posted_at >= ?",
            (item_id, cutoff.isoformat())
        ).fetchone()
        return row is not None

def mark_as_posted(deal) -> None:
    with sqlite3.connect(DB_PATH) as conn:
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
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT COUNT(*) FROM posted_deals").fetchone()
        return row[0] if row else 0

# =============================================================================
# 🕷️ SCRAPER DE OFERTAS DO MERCADO LIVRE
# =============================================================================
@dataclass
class Deal:
    item_id: str
    title: str
    price: float
    original_price: Optional[float]
    discount_pct: int
    image_url: str
    clean_url: str
    affiliate_url: str
    installments: str = ""

class MercadoLivreScraper:
    def __init__(self, matt_tool: str = "", matt_word: str = ""):
        self.matt_tool = matt_tool
        self.matt_word = matt_word
        self.headers = {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def generate_affiliate_link(self, raw_url: str):
        parsed = urllib.parse.urlparse(raw_url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        affiliate_params = {}
        if self.matt_tool:
            affiliate_params["matt_tool"] = self.matt_tool
        if self.matt_word:
            affiliate_params["matt_word"] = self.matt_word
        if affiliate_params:
            query_string = urllib.parse.urlencode(affiliate_params)
            return f"{clean_url}?{query_string}", clean_url
        return clean_url, clean_url

    def _parse_price(self, text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = re.sub(r"[^\d,\.]", "", text).replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def get_mais_vendidos(self, min_discount_pct: int = 20) -> List[Deal]:
        url = "https://www.mercadolivre.com.br/mais-vendidos"
        try:
            res = cffi_requests.get(url, headers=self.headers, impersonate="chrome", timeout=15)
        except Exception as e:
            print(f"[Scraper] Erro ao acessar Mercado Livre: {e}")
            return []

        if res.status_code != 200:
            print(f"[Scraper] Status inesperado: {res.status_code}")
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        cards = soup.select(".poly-card")
        deals = []

        for card in cards:
            title_el = card.select_one(".poly-component__title")
            if not title_el or not title_el.get("href"):
                continue

            title = title_el.text.strip()
            raw_url = title_el["href"]

            id_match = re.search(r"MLB-?(\d+)", raw_url, re.IGNORECASE)
            item_id = f"MLB{id_match.group(1)}" if id_match else raw_url.split("?")[0]

            price_fraction = card.select_one(".poly-price__current .andes-money-amount__fraction")
            price_cents = card.select_one(".poly-price__current .andes-money-amount__cents")
            if not price_fraction:
                continue

            price_str = price_fraction.text.strip()
            if price_cents:
                price_str += "," + price_cents.text.strip()
            price = self._parse_price(price_str)
            if price is None:
                continue

            original_price = None
            discount_pct = 0
            prev_price_el = card.select_one(".andes-money-amount--previous .andes-money-amount__fraction")
            if prev_price_el:
                original_price = self._parse_price(prev_price_el.text.strip())

            disc_el = card.select_one(".andes-money-amount-discount")
            if disc_el:
                disc_match = re.search(r"(\d+)%", disc_el.text)
                if disc_match:
                    discount_pct = int(disc_match.group(1))

            if not discount_pct and original_price and original_price > price:
                discount_pct = int(round(((original_price - price) / original_price) * 100))

            if discount_pct < min_discount_pct:
                continue

            img_el = card.select_one("img.poly-component__picture")
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            installments_el = card.select_one(".poly-price__installments")
            installments = installments_el.text.strip() if installments_el else ""

            affiliate_url, clean_url = self.generate_affiliate_link(raw_url)

            deals.append(Deal(
                item_id=item_id,
                title=title,
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                image_url=image_url,
                clean_url=clean_url,
                affiliate_url=affiliate_url,
                installments=installments
            ))

        deals.sort(key=lambda d: d.discount_pct, reverse=True)
        return deals

# =============================================================================
# 📤 DISPARADOR TELEGRAM
# =============================================================================
def format_caption(deal: Deal) -> str:
    lines = [
        f"🔥 <b>OFERTA IMPERDÍVEL — {deal.discount_pct}% OFF!</b>",
        "",
        f"📦 <b>{deal.title}</b>",
        ""
    ]
    if deal.original_price and deal.original_price > deal.price:
        lines.append(f"❌ De: <s>R$ {deal.original_price:,.2f}</s>".replace(".", "X").replace(",", ".").replace("X", ","))

    lines.append(f"✅ <b>Por apenas: R$ {deal.price:,.2f}</b>".replace(".", "X").replace(",", ".").replace("X", ","))

    if deal.installments:
        lines.append(f"💳 {deal.installments}")

    lines.append("")
    lines.append("🛒 <b>Compre com desconto aqui:</b>")
    lines.append(f"👉 <a href=\"{deal.affiliate_url}\">Clique para ver no Mercado Livre</a>")
    lines.append("")
    lines.append("⚠️ <i>Preços e estoque sujeitos a alteração rápida!</i>")
    return "\n".join(lines)

def send_telegram(deal: Deal) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or "SEU_" in TELEGRAM_BOT_TOKEN:
        print("[Telegram] Bot token ou Chat ID não preenchidos.")
        return False

    caption = format_caption(deal)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "🛒 Ver Oferta no Mercado Livre", "url": deal.affiliate_url}]
            ]
        }
    }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto" if deal.image_url else f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    if not deal.image_url:
        payload["text"] = caption
        payload.pop("caption", None)
    else:
        payload["photo"] = deal.image_url

    try:
        r = requests.post(url, json=payload, timeout=15)
        data = r.json()
        if data.get("ok"):
            print(f"[Telegram] Enviado com sucesso: {deal.title[:40]}...")
            return True
        else:
            print(f"[Telegram] Falha ao enviar: {data.get('description')}")
            return False
    except Exception as e:
        print(f"[Telegram] Erro na requisição: {e}")
        return False

# =============================================================================
# 🚀 MOTOR DE EXECUÇÃO EM CICLOS (5min Envio / 10min Descanso)
# =============================================================================
def run_active_window():
    duration_seconds = ACTIVE_SEND_MINUTES * 60
    end_time = time.time() + duration_seconds
    end_dt = datetime.now() + timedelta(seconds=duration_seconds)

    print("=" * 65)
    print(f"🚀 [FASE ATIVA] ENVIANDO LINKS POR {ACTIVE_SEND_MINUTES} MINUTOS SEM PARAR")
    print(f"   Início: {datetime.now().strftime('%H:%M:%S')} | Encerramento previsto: {end_dt.strftime('%H:%M:%S')}")
    print(f"   Desconto mínimo: {MIN_DISCOUNT_PCT}% | Intervalo entre posts: {POST_DELAY_SECONDS}s")
    print(f"   Catalogados no banco: {get_posted_count()} produtos")
    print("=" * 65)

    scraper = MercadoLivreScraper(matt_tool=MATT_TOOL, matt_word=MATT_WORD)
    deals = scraper.get_mais_vendidos(min_discount_pct=MIN_DISCOUNT_PCT)

    if not deals:
        print("⚠️ Nenhuma oferta encontrada nesta busca.")
        return 0

    posted = 0
    seen = set()

    for deal in deals:
        if time.time() >= end_time:
            break

        if deal.item_id in seen or is_already_posted(deal.item_id, max_days=REPOST_AFTER_DAYS):
            continue

        seen.add(deal.item_id)
        rem = max(0, int(end_time - time.time()))
        print(f"\n🎯 [POSTANDO #{posted + 1}] ({deal.discount_pct}% OFF) - Faltam {rem//60:02d}:{rem%60:02d}")
        print(f"   {deal.title[:65]}...")
        print(f"   Preço: R$ {deal.price:.2f} | Link: {deal.affiliate_url}")

        if send_telegram(deal):
            mark_as_posted(deal)
            posted += 1

        wait_sec = min(float(POST_DELAY_SECONDS), max(0.0, end_time - time.time()))
        if wait_sec > 0:
            time.sleep(wait_sec)

    print(f"\n🏁 [FASE ATIVA CONCLUÍDA] {posted} ofertas enviadas com sucesso!")
    return posted

def main():
    init_db()
    print("==================================================================")
    print("   ROBÔ DE OFERTAS MERCADO LIVRE - INICIALIZADO COM SUCESSO       ")
    print(f"   Ciclo: {ACTIVE_SEND_MINUTES}min disparando -> {REST_MINUTES}min descansando")
    print("==================================================================")

    ciclo = 1
    while True:
        try:
            print(f"\n▶️ INICIANDO CICLO #{ciclo}")
            run_active_window()
            next_run = datetime.now() + timedelta(minutes=REST_MINUTES)
            print(f"\n😴 [DESCANSO] Pausa de {REST_MINUTES} minutos até {next_run.strftime('%H:%M:%S')}...")
            time.sleep(REST_MINUTES * 60)
            ciclo += 1
        except KeyboardInterrupt:
            print("\n🛑 Bot interrompido pelo usuário.")
            break
        except Exception as e:
            print(f"\n⚠️ Ocorreu um erro no ciclo #{ciclo}: {e}")
            print(f"Aguardando 1 minuto antes de tentar novamente...")
            time.sleep(60)

if __name__ == "__main__":
    main()
