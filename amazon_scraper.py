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
    source: str = "amazon"

class AmazonScraper:
    def __init__(self, affiliate_tag: str = ""):
        self.affiliate_tag = affiliate_tag
        self.headers = {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def generate_affiliate_link(self, asin: str) -> str:
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
        """Varre os produtos mais vendidos da Amazon Brasil em categorias populares."""
        if categories is None:
            categories = ["", "computers", "electronics", "kitchen", "automotive", "hi"]

        deals: List[Deal] = []
        seen_asins = set()

        for cat in categories:
            url = f"https://www.amazon.com.br/gp/bestsellers/{cat}".rstrip("/")
            try:
                res = requests.get(url, headers=self.headers, impersonate="chrome", timeout=12)
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

                # Título
                t_el = card.select_one(".p13n-sc-truncate, ._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y, ._cDEzb_p13n-sc-css-line-clamp-2_EWgtZ")
                img_el = card.select_one("img")
                title = t_el.text.strip() if t_el else (img_el.get("alt") if img_el else "")
                if not title or len(title) < 5:
                    continue

                # Imagem
                img_url = img_el.get("src") if img_el else ""

                # Preço
                price_el = card.select_one("._cDEzb_p13n-sc-price_3mJ9Z, .a-price .a-offscreen, .a-color-price")
                price_str = price_el.text.strip() if price_el else ""
                price = self._parse_price(price_str)
                if not price or price <= 0:
                    continue

                # Desconto (se houver indicação ou preço riscado)
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

if __name__ == "__main__":
    scraper = AmazonScraper(affiliate_tag="pedro01fdf-20")
    print("Testando busca de Mais Vendidos na Amazon...")
    items = scraper.get_mais_vendidos()
    print(f"Total encontrado: {len(items)}")
    for i, it in enumerate(items[:5], 1):
        print(f"#{i} [{it.item_id}] {it.title[:50]} | R$ {it.price:.2f}")
        print(f"   Link: {it.affiliate_url}")
