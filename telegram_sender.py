import socket
import requests
import urllib3.util.connection as urllib3_cn
from typing import Optional
from scraper import Deal

# Força IPv4 para evitar hang de conexão/SynSent com a API do Telegram em rotas de provedores brasileiros
urllib3_cn.allowed_gai_family = lambda: socket.AF_INET

def format_telegram_caption(deal: Deal) -> str:
    """Formata o texto da mensagem no padrão clássico de canais de promoções."""
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
    lines.append(f"🛒 <b>Compre com desconto aqui:</b>")
    lines.append(f"👉 <a href=\"{deal.affiliate_url}\">Clique para ver no Mercado Livre</a>")
    lines.append("")
    lines.append("⚠️ <i>Preços e estoque sujeitos a alteração rápida!</i>")

    return "\n".join(lines)

def send_deal_to_telegram(bot_token: str, chat_id: str, deal: Deal) -> bool:
    """Envia a oferta (foto + legenda) para um canal ou grupo do Telegram."""
    if not bot_token or not chat_id:
        print("[Telegram] Bot token ou Chat ID não configurados.")
        return False

    caption = format_telegram_caption(deal)

    # Se houver imagem, envia como sendPhoto
    if deal.image_url:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": deal.image_url,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "🛒 Ver Oferta no Mercado Livre", "url": deal.affiliate_url}
                    ]
                ]
            }
        }
    else:
        # Fallback para mensagem de texto
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": caption,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "🛒 Ver Oferta no Mercado Livre", "url": deal.affiliate_url}
                    ]
                ]
            }
        }

    try:
        response = requests.post(url, json=payload, timeout=15)
        res_data = response.json()
        if res_data.get("ok"):
            print(f"[Telegram] Oferta enviada com sucesso: {deal.title[:40]}...")
            return True
        else:
            print(f"[Telegram] Falha ao enviar oferta: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"[Telegram] Erro na requisição: {e}")
        return False
