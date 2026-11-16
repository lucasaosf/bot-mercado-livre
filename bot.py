import os
import sys
import time
import argparse

# Configuração de log para funcionar com terminal e também em segundo plano (pythonw)
class DualLogger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8", buffering=1)

    def write(self, message):
        if self.terminal:
            try:
                self.terminal.write(message)
            except Exception:
                pass
        self.log.write(message)

    def flush(self):
        if self.terminal:
            try:
                self.terminal.flush()
            except Exception:
                pass
        self.log.flush()

log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.log")
sys.stdout = DualLogger(log_file_path)
sys.stderr = sys.stdout

from scraper import MercadoLivreScraper
from database import init_db, is_already_posted, mark_as_posted, get_posted_count
import config
from telegram_sender import send_deal_to_telegram

def run_cycle(preview_only: bool = False):
    print("=" * 60)
    print(f"🔍 Iniciando varredura das melhores ofertas do Mercado Livre...")
    print(f"   Tag de Afiliado: matt_word={config.MATT_WORD} | matt_tool={config.MATT_TOOL}")
    print(f"   Desconto Mínimo: {config.MIN_DISCOUNT_PCT}%")
    print(f"   Itens já catalogados no banco: {get_posted_count()}")
    print("=" * 60)

    scraper = MercadoLivreScraper(matt_tool=config.MATT_TOOL, matt_word=config.MATT_WORD)
    deals = scraper.get_mais_vendidos(min_discount_pct=config.MIN_DISCOUNT_PCT)

    if not deals:
        print("⚠️ Nenhuma oferta encontrada com os critérios definidos.")
        return

    posted_now = 0
    skipped_duplicates = 0
    seen_in_cycle = set()

    for deal in deals:
        if posted_now >= config.MAX_POSTS_PER_RUN:
            print(f"\nLimite de {config.MAX_POSTS_PER_RUN} ofertas atingido para este ciclo.")
            break

        if deal.item_id in seen_in_cycle or is_already_posted(deal.item_id, max_days=config.REPOST_AFTER_DAYS):
            skipped_duplicates += 1
            continue

        seen_in_cycle.add(deal.item_id)

        print(f"\n🎯 [NOVA OFERTA ENCONTRADA] ({deal.discount_pct}% OFF)")
        print(f"   Título: {deal.title}")
        orig = f" (De R$ {deal.original_price:.2f})" if deal.original_price else ""
        print(f"   Preço: R$ {deal.price:.2f}{orig}")
        print(f"   Link Afiliado: {deal.affiliate_url}")

        if preview_only:
            # Modo apenas visualização: não envia para Telegram nem grava no banco
            posted_now += 1
            continue

        # Envia para o Telegram se configurado
        sent = False
        if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            sent = send_deal_to_telegram(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, deal)
        else:
            print("   ℹ️ [Telegram não configurado] O produto foi exibido aqui. Para enviar automaticamente ao Telegram, configure o arquivo .env")
            sent = True

        if sent:
            mark_as_posted(deal)
            posted_now += 1
            # Pausa breve para evitar flood
            time.sleep(2)

    print("\n" + "=" * 60)
    print(f"✅ Ciclo concluído!")
    print(f"   Novas ofertas processadas: {posted_now}")
    print(f"   Ofertas ignoradas por repetição recente: {skipped_duplicates}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Bot de Ofertas Mais Vendidas do Mercado Livre com Link de Afiliado")
    parser.add_argument("--preview", action="store_true", help="Apenas exibe as ofertas no terminal sem enviar ou gravar no banco")
    parser.add_argument("--once", action="store_true", help="Executa uma única verificação e encerra")
    parser.add_argument("--loop", action="store_true", help="Executa continuamente respeitando o intervalo configurado")

    args = parser.parse_args()

    # Inicializa banco de dados
    init_db()

    if args.preview:
        run_cycle(preview_only=True)
    elif args.loop:
        print(f"🚀 Bot iniciado em modo contínuo (intervalo de {config.CHECK_INTERVAL_MINUTES} minutos).")
        print("Pressione Ctrl + C para parar.\n")
        try:
            while True:
                run_cycle(preview_only=False)
                print(f"\n⏳ Aguardando {config.CHECK_INTERVAL_MINUTES} minutos até a próxima verificação...")
                time.sleep(config.CHECK_INTERVAL_MINUTES * 60)
        except KeyboardInterrupt:
            print("\n🛑 Bot interrompido pelo usuário.")
            sys.exit(0)
    else:
        # Padrão: executa uma vez
        run_cycle(preview_only=False)

if __name__ == "__main__":
    main()
