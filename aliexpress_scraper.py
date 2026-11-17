import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional, List
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
    source: str = "aliexpress"

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
        """Varre os produtos mais vendidos e em super oferta no AliExpress Brasil."""
        if categories is None:
            categories = ["mais-vendidos", "eletronicos", "ferramentas", "relogios"]

        deals: List[Deal] = []
        seen_ids = set()

        for cat in categories:
            url = f"https://pt.aliexpress.com/w/wholesale-{cat}.html"
            try:
                res = requests.get(url, headers=self.headers, impersonate="chrome", timeout=12)
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

if __name__ == "__main__":
    scraper = AliExpressScraper(aff_fsk="_mqTQekn")
    print("Testando busca de Mais Vendidos no AliExpress...")
    items = scraper.get_mais_vendidos(min_discount_pct=20)
    print(f"Total encontrado: {len(items)}")
    for i, it in enumerate(items[:5], 1):
        orig = f" (De R$ {it.original_price:.2f})" if it.original_price else ""
        print(f"#{i} [{it.item_id}] {it.title[:50]} | R$ {it.price:.2f}{orig} -> {it.discount_pct}% OFF")
        print(f"   Foto: {it.image_url}")
        print(f"   Link: {it.affiliate_url}")
