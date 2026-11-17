"""
=============================================================================
🤖 BOT DE OFERTAS MULTI-LOJAS (MERCADO LIVRE + AMAZON + ALIEXPRESS) - ARQUIVO ÚNICO
=============================================================================
Script completo e autocontido para rodar facilmente em painéis Python, VPS ou nuvem.
Lojas integradas:
  1. Mercado Livre (Afiliado Mercado Livre - matt_tool / matt_word)
  2. Amazon Brasil (Afiliado Amazon - tag / linkCode)
  3. AliExpress (Afiliado AliExpress - aff_fsk / short key)

Dependências necessárias:
    pip install requests curl_cffi beautifulsoup4 urllib3 python-dotenv
=============================================================================
"""

import os
import sys
import time
import re
import socket
import sqlite3
import json
import urllib.parse
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List
import requests
import urllib3.util.connection as urllib3_cn
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

# 1. FORÇA RESOLUÇÃO IPV4 (Evita travamentos de rota/SynSent com a API do Telegram)
urllib3_cn.allowed_gai_family = lambda: socket.AF_INET

# =============================================================================
# ⚙️ CONFIGURAÇÕES PRINCIPAIS (Preencha aqui ou configure via variáveis de ambiente/.env)
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "SEU_BOT_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")

# Parâmetros de Afiliado Mercado Livre
MATT_TOOL = os.getenv("MATT_TOOL", "58522050")
MATT_WORD = os.getenv("MATT_WORD", "lucasaosf")

# Tag de Afiliado Amazon
AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "pedro01fdf-20")

# Código de Afiliado AliExpress (FSK / Short Key)
ALIEXPRESS_AFF_FSK = os.getenv("ALIEXPRESS_AFF_FSK", "_mqTQekn")

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
        row = conn.execute("SELECT COUNT(*) as total FROM posted_deals").fetchone()
        return row[0] if row else 0

# =============================================================================
# 📦 MODELO DE DADOS
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
    source: str = "mercadolivre"

# =============================================================================
# 🔍 1. SCRAPER MERCADO LIVRE
# =============================================================================
class MercadoLivreScraper:
    def __init__(self, matt_tool: str = "", matt_word: str = ""):
        self.matt_tool = matt_tool
        self.matt_word = matt_word
        self.headers = {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def generate_affiliate_link(self, raw_url: str) -> tuple:
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

    def _parse_price_text(self, text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = re.sub(r"[^\d,\.]", "", text).replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def get_mais_vendidos(self, min_discount_pct: int = 15) -> List[Deal]:
        url = "https://www.mercadolivre.com.br/mais-vendidos"
        try:
            res = cffi_requests.get(url, headers=self.headers, impersonate="chrome", timeout=15)
        except Exception as e:
            print(f"[Mercado Livre] Erro: {e}")
            return []

        if res.status_code != 200:
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
            price = self._parse_price_text(price_str)
            if price is None:
                continue

            original_price = None
            discount_pct = 0
            prev_price_el = card.select_one(".andes-money-amount--previous .andes-money-amount__fraction")
            if prev_price_el:
                original_price = self._parse_price_text(prev_price_el.text.strip())

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
            image_url = img_el.get("src") or img_el.get("data-src") or "" if img_el else ""

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
                installments=installments,
                source="mercadolivre"
            ))

        deals.sort(key=lambda d: d.discount_pct, reverse=True)
        return deals

# =============================================================================
# 🔍 2. SCRAPER AMAZON BRASIL
# =============================================================================
class AmazonScraper:
    def __init__(self, affiliate_tag: str = ""):
        self.affiliate_tag = affiliate_tag
        self.headers = {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def generate_affiliate_link(self, asin: str) -> tuple:
        clean_url = f"https://www.amazon.com.br/dp/{asin}"
        if self.affiliate_tag:
            return f"{clean_url}?tag={self.affiliate_tag}&linkCode=as4", clean_url
        return clean_url, clean_url

    def _parse_price(self, text: str) -> Optional[float]:
        if not text:
            return None
        match = re.search(r"R\$\s*([\d\.,]+)", text)
        if not match:
            return None
        cleaned = match.group(1).replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def get_mais_vendidos(self, categories: Optional[List[str]] = None) -> List[Deal]:
        if categories is None:
            categories = ["", "computers", "electronics", "kitchen", "automotive", "hi"]

        deals: List[Deal] = []
        seen_asins = set()

        for cat in categories:
            url = f"https://www.amazon.com.br/gp/bestsellers/{cat}".rstrip("/")
            try:
                res = cffi_requests.get(url, headers=self.headers, impersonate="chrome", timeout=12)
            except Exception as e:
                print(f"[Amazon] Erro ao acessar {url}: {e}")
                continue

            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            cards = soup.select("[data-asin]")

            for card in cards:
                asin = card.get("data-asin")
                if not asin or len(asin) != 10 or asin in seen_asins:
                    continue

                seen_asins.add(asin)

                t_el = card.select_one(".p13n-sc-truncate, ._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y, ._cDEzb_p13n-sc-css-line-clamp-2_EWgtZ")
                img_el = card.select_one("img")
                title = t_el.text.strip() if t_el else (img_el.get("alt") if img_el else "")
                if not title or len(title) < 5:
                    continue

                img_url = img_el.get("src") if img_el else ""

                price_el = card.select_one("._cDEzb_p13n-sc-price_3mJ9Z, .a-price .a-offscreen, .a-color-price")
                price_str = price_el.text.strip() if price_el else ""
                price = self._parse_price(price_str)
                if not price or price <= 0:
                    continue

                original_price = None
                discount_pct = 0
                prev_price_el = card.select_one(".a-text-price .a-offscreen")
                if prev_price_el:
                    original_price = self._parse_price(prev_price_el.text.strip())
                    if original_price and original_price > price:
                        discount_pct = int(round(((original_price - price) / original_price) * 100))

                affiliate_url, clean_url = self.generate_affiliate_link(asin)

                deals.append(Deal(
                    item_id=asin,
                    title=title,
                    price=price,
                    original_price=original_price,
                    discount_pct=discount_pct,
                    image_url=img_url,
                    clean_url=clean_url,
                    affiliate_url=affiliate_url,
                    source="amazon"
                ))

        return deals

# =============================================================================
# 🔍 3. SCRAPER ALIEXPRESS
# =============================================================================
class AliExpressScraper:
    def __init__(self, aff_fsk: str = "_mqTQekn"):
        self.aff_fsk = aff_fsk
        self.headers = {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def generate_affiliate_link(self, item_id: str) -> tuple:
        clean_url = f"https://pt.aliexpress.com/item/{item_id}.html"
        if self.aff_fsk:
            encoded_target = urllib.parse.quote(clean_url, safe="")
            affiliate_url = f"https://s.click.aliexpress.com/deep_link.htm?aff_short_key={self.aff_fsk}&dl_target_url={encoded_target}"
            return affiliate_url, clean_url
        return clean_url, clean_url

    def get_mais_vendidos(self, categories: Optional[List[str]] = None, min_discount_pct: int = 15) -> List[Deal]:
        if categories is None:
            categories = ["mais-vendidos", "eletronicos", "ferramentas", "relogios"]

        deals: List[Deal] = []
        seen_ids = set()

        for cat in categories:
            url = f"https://pt.aliexpress.com/w/wholesale-{cat}.html"
            try:
                res = cffi_requests.get(url, headers=self.headers, impersonate="chrome", timeout=12)
            except Exception as e:
                print(f"[AliExpress] Erro ao acessar {url}: {e}")
                continue

            if res.status_code != 200:
                continue

            start_tag = "window._dida_config_._init_data_="
            start_pos = res.text.find(start_tag)
            if start_pos == -1:
                continue

            raw = res.text[start_pos + len(start_tag):]
            end_tag = "/*!-->init-data-end--*/"
            end_pos = raw.find(end_tag)
            if end_pos == -1:
                continue

            raw_snippet = raw[:end_pos].strip().rstrip(";")
            first_brace = raw_snippet.find("{", raw_snippet.find("data:"))
            last_brace = raw_snippet.rfind("}")
            if first_brace == -1 or last_brace == -1:
                continue

            try:
                inner_candidate = raw_snippet[first_brace:last_brace].strip()
                data = json.loads(inner_candidate)
                items = data.get("data", {}).get("root", {}).get("fields", {}).get("mods", {}).get("itemList", {}).get("content", [])
            except Exception as e:
                print(f"[AliExpress] Erro no parsing JSON de {cat}: {e}")
                continue

            for it in items:
                item_id = str(it.get("productId") or it.get("redirectedId") or "")
                if not item_id or item_id in seen_ids:
                    continue

                title = it.get("title", {}).get("displayTitle", "").strip()
                if not title or len(title) < 5:
                    continue

                prices = it.get("prices", {})
                sale_price_obj = prices.get("salePrice", {})
                price = sale_price_obj.get("minPrice")
                if not price or float(price) <= 0:
                    continue
                price = float(price)

                discount_pct = int(sale_price_obj.get("discount", 0))
                if discount_pct < min_discount_pct:
                    continue

                original_price = None
                if discount_pct > 0 and discount_pct < 100:
                    original_price = round(price / (1.0 - (discount_pct / 100.0)), 2)

                img_url = it.get("image", {}).get("imgUrl", "")
                if img_url.startswith("//"):
                    img_url = "https:" + img_url

                seen_ids.add(item_id)
                affiliate_url, clean_url = self.generate_affiliate_link(item_id)

                deals.append(Deal(
                    item_id=f"ALI_{item_id}",
                    title=title,
                    price=price,
                    original_price=original_price,
                    discount_pct=discount_pct,
                    image_url=img_url,
                    clean_url=clean_url,
                    affiliate_url=affiliate_url,
                    source="aliexpress"
                ))

        deals.sort(key=lambda d: d.discount_pct, reverse=True)
        return deals

# =============================================================================
# 📤 DISPARADOR TELEGRAM UNIFICADO
# =============================================================================
def format_caption(deal: Deal) -> str:
    source = deal.source
    if source == "amazon":
        header = f"📦 <b>ACHADO NA AMAZON — {deal.discount_pct}% OFF!</b>" if deal.discount_pct else "📦 <b>MAIS VENDIDOS DA AMAZON!</b>"
        store_name = "Amazon"
    elif source == "aliexpress":
        header = f"🛍️ <b>ACHADO NO ALIEXPRESS — {deal.discount_pct}% OFF!</b>" if deal.discount_pct else "🛍️ <b>MAIS VENDIDOS DO ALIEXPRESS!</b>"
        store_name = "AliExpress"
    else:
        header = f"🔥 <b>OFERTA MERCADO LIVRE — {deal.discount_pct}% OFF!</b>" if deal.discount_pct else "🔥 <b>MAIS VENDIDOS DO MERCADO LIVRE!</b>"
        store_name = "Mercado Livre"

    lines = [
        header,
        "",
        f"🏷️ <b>{deal.title}</b>",
        ""
    ]
    if deal.original_price and deal.original_price > deal.price:
        lines.append(f"❌ De: <s>R$ {deal.original_price:,.2f}</s>".replace(".", "X").replace(",", ".").replace("X", ","))

    lines.append(f"✅ <b>Por apenas: R$ {deal.price:,.2f}</b>".replace(".", "X").replace(",", ".").replace("X", ","))

    if deal.installments:
        lines.append(f"💳 {deal.installments}")

    lines.append("")
    lines.append("🛒 <b>Compre com desconto aqui:</b>")
    lines.append(f"👉 <a href=\"{deal.affiliate_url}\">Clique para ver na {store_name}</a>")
    lines.append("")
    lines.append("⚠️ <i>Preços e estoque sujeitos a alteração rápida!</i>")
    return "\n".join(lines)

def send_telegram(deal: Deal) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or "SEU_" in TELEGRAM_BOT_TOKEN:
        print("[Telegram] Bot token ou Chat ID não preenchidos.")
        return False

    caption = format_caption(deal)
    source = deal.source
    if source == "amazon":
        btn_text = "🛒 Ver Oferta na Amazon"
    elif source == "aliexpress":
        btn_text = "🛒 Ver Oferta no AliExpress"
    else:
        btn_text = "🛒 Ver Oferta no Mercado Livre"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": btn_text, "url": deal.affiliate_url}]
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
            print(f"[Telegram] Enviado com sucesso ({deal.source.upper()}): {deal.title[:40]}...")
            return True
        else:
            print(f"[Telegram] Falha ao enviar: {data.get('description')}")
            return False
    except Exception as e:
        print(f"[Telegram] Erro na requisição: {e}")
        return False

# =============================================================================
# 🚀 MOTOR DO CICLO (5min Envio / 10min Descanso)
# =============================================================================
def run_active_window():
    duration_seconds = ACTIVE_SEND_MINUTES * 60
    end_time = time.time() + duration_seconds
    end_dt = datetime.now() + timedelta(seconds=duration_seconds)

    print("=" * 65)
    print(f"🚀 [FASE ATIVA] ENVIANDO LINKS POR {ACTIVE_SEND_MINUTES} MINUTOS SEM PARAR")
    print(f"   Início: {datetime.now().strftime('%H:%M:%S')} | Encerramento: {end_dt.strftime('%H:%M:%S')}")
    print(f"   Fontes: Mercado Livre (Lucas) + Amazon (Pedro) + AliExpress")
    print(f"   Catalogados no banco: {get_posted_count()} produtos")
    print("=" * 65)

    # 1. Coleta Mercado Livre
    meli_scraper = MercadoLivreScraper(matt_tool=MATT_TOOL, matt_word=MATT_WORD)
    meli_deals = meli_scraper.get_mais_vendidos(min_discount_pct=MIN_DISCOUNT_PCT)
    print(f"📦 [Mercado Livre] {len(meli_deals)} ofertas coletadas.")

    # 2. Coleta Amazon
    amazon_scraper = AmazonScraper(affiliate_tag=AMAZON_AFFILIATE_TAG)
    amazon_deals = amazon_scraper.get_mais_vendidos()
    print(f"📦 [Amazon] {len(amazon_deals)} mais vendidos coletados.")

    # 3. Coleta AliExpress
    ali_scraper = AliExpressScraper(aff_fsk=ALIEXPRESS_AFF_FSK)
    ali_deals = ali_scraper.get_mais_vendidos(min_discount_pct=MIN_DISCOUNT_PCT)
    print(f"📦 [AliExpress] {len(ali_deals)} ofertas coletadas.")

    # 4. Intercala as ofertas das 3 plataformas
    combined_deals = []
    max_len = max(len(meli_deals), len(amazon_deals), len(ali_deals))
    for i in range(max_len):
        if i < len(meli_deals):
            combined_deals.append(meli_deals[i])
        if i < len(amazon_deals):
            combined_deals.append(amazon_deals[i])
        if i < len(ali_deals):
            combined_deals.append(ali_deals[i])

    if not combined_deals:
        print("⚠️ Nenhuma oferta encontrada nesta busca.")
        return 0

    posted = 0
    seen = set()

    for deal in combined_deals:
        if time.time() >= end_time:
            break

        if deal.item_id in seen or is_already_posted(deal.item_id, max_days=REPOST_AFTER_DAYS):
            continue

        seen.add(deal.item_id)
        rem = max(0, int(end_time - time.time()))
        print(f"\n🎯 [POSTANDO #{posted + 1} - {deal.source.upper()}] - Faltam {rem//60:02d}:{rem%60:02d}")
        print(f"   {deal.title[:65]}...")
        orig = f" (De R$ {deal.original_price:.2f})" if deal.original_price else ""
        print(f"   Preço: R$ {deal.price:.2f}{orig} -> {deal.discount_pct}% OFF")
        print(f"   Link Afiliado: {deal.affiliate_url}")

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
    print("   ROBÔ DE OFERTAS MULTI-LOJAS (MERCADO LIVRE + AMAZON + ALIEXPRESS)  ")
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
            print("Aguardando 1 minuto antes de tentar novamente...")
            time.sleep(60)

if __name__ == "__main__":
    main()
