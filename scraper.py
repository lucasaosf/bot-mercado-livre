import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional, List
from bs4 import BeautifulSoup
from curl_cffi import requests

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

    def generate_affiliate_link(self, raw_url: str) -> str:
        """Limpa parâmetros irrelevantes e injeta os parâmetros de afiliado configurados."""
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
        # Remove R$, espaços, pontos de milhar e troca vírgula por ponto
        cleaned = re.sub(r"[^\d,\.]", "", text).replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def get_mais_vendidos(self, min_discount_pct: int = 15) -> List[Deal]:
        """Pega as melhores ofertas da página de Mais Vendidos."""
        url = "https://www.mercadolivre.com.br/mais-vendidos"
        try:
            response = requests.get(url, headers=self.headers, impersonate="chrome")
        except Exception as e:
            print(f"Erro ao acessar Mercado Livre: {e}")
            return []

        if response.status_code != 200:
            print(f"Status inesperado: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select(".poly-card")
        deals = []

        for card in cards:
            title_el = card.select_one(".poly-component__title")
            if not title_el or not title_el.get("href"):
                continue

            title = title_el.text.strip()
            raw_url = title_el["href"]

            # Extração de ID do produto
            id_match = re.search(r"MLB-?(\d+)", raw_url, re.IGNORECASE)
            item_id = f"MLB{id_match.group(1)}" if id_match else raw_url.split("?")[0]

            # Preço atual
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

            # Preço anterior (se houver desconto)
            original_price = None
            discount_pct = 0
            prev_price_el = card.select_one(".andes-money-amount--previous .andes-money-amount__fraction")
            if prev_price_el:
                original_price = self._parse_price_text(prev_price_el.text.strip())

            # Elemento de desconto explícito ou cálculo
            disc_el = card.select_one(".andes-money-amount-discount")
            if disc_el:
                disc_match = re.search(r"(\d+)%", disc_el.text)
                if disc_match:
                    discount_pct = int(disc_match.group(1))

            if not discount_pct and original_price and original_price > price:
                discount_pct = int(round(((original_price - price) / original_price) * 100))

            # Filtro por desconto mínimo
            if discount_pct < min_discount_pct:
                continue

            # Imagem em alta resolução
            img_el = card.select_one("img.poly-component__picture")
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            # Parcelamento
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

        # Ordena pelas melhores ofertas (maior desconto primeiro)
        deals.sort(key=lambda d: d.discount_pct, reverse=True)
        return deals

if __name__ == "__main__":
    scraper = MercadoLivreScraper()
    print("Buscando as melhores ofertas dos mais vendidos...")
    deals = scraper.get_mais_vendidos(min_discount_pct=30)
    print(f"\nEncontradas {len(deals)} ofertas com mais de 30% de desconto:\n")
    for i, d in enumerate(deals[:5], 1):
        print(f"🔥 #{i} - {d.title}")
        orig = f" (De R$ {d.original_price:.2f})" if d.original_price else ""
        print(f"   Preço: R$ {d.price:.2f}{orig} -> {d.discount_pct}% OFF")
        if d.installments:
            print(f"   Condição: {d.installments}")
        print(f"   Link Afiliado: {d.affiliate_url}")
        print()
