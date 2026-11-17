import os
import sys
import time
from datetime import datetime, timedelta
import argparse

# Configuração de log para funcionar tanto com terminal quanto em segundo plano (pythonw)
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

def run_active_window(preview_only: bool = False):
    """
    Executa a janela ativa de envios:
    Envia links sem parar durante config.ACTIVE_SEND_MINUTES minutos (padrão: 5 minutos).
    """
    duration_seconds = config.ACTIVE_SEND_MINUTES * 60
    start_time = time.time()
    end_time = start_time + duration_seconds
    end_dt = datetime.now() + timedelta(seconds=duration_seconds)

    print("=" * 65)
    print(f"🚀 [FASE ATIVA INICIADA] ENVIANDO LINKS POR {config.ACTIVE_SEND_MINUTES} MINUTOS SEM PARAR")
    print(f"   Início: {datetime.now().strftime('%H:%M:%S')} | Encerramento previsto: {end_dt.strftime('%H:%M:%S')}")
    print(f"   Desconto mínimo: {config.MIN_DISCOUNT_PCT}% | Intervalo entre posts: {config.POST_DELAY_SECONDS}s")
    print(f"   Total já catalogado no banco: {get_posted_count()} produtos")
    print("=" * 65)

    scraper = MercadoLivreScraper(matt_tool=config.MATT_TOOL, matt_word=config.MATT_WORD)
    deals = scraper.get_mais_vendidos(min_discount_pct=config.MIN_DISCOUNT_PCT)

    if not deals:
        print("⚠️ Nenhuma oferta encontrada com os critérios definidos.")
        return 0

    posted_in_window = 0
    skipped_duplicates = 0
    seen_in_window = set()

    deal_index = 0
    while time.time() < end_time and deal_index < len(deals):
        deal = deals[deal_index]
        deal_index += 1

        if deal.item_id in seen_in_window or is_already_posted(deal.item_id, max_days=config.REPOST_AFTER_DAYS):
            skipped_duplicates += 1
            continue

        seen_in_window.add(deal.item_id)
        remaining_seconds = max(0, int(end_time - time.time()))
        rem_min = remaining_seconds // 60
        rem_sec = remaining_seconds % 60

        print(f"\n🎯 [POSTANDO #{posted_in_window + 1}] ({deal.discount_pct}% OFF) - Faltam {rem_min:02d}:{rem_sec:02d}")
        print(f"   Título: {deal.title}")
        orig = f" (De R$ {deal.original_price:.2f})" if deal.original_price else ""
        print(f"   Preço: R$ {deal.price:.2f}{orig}")
        print(f"   Link Afiliado: {deal.affiliate_url}")

        if preview_only:
            posted_in_window += 1
            time.sleep(min(float(config.POST_DELAY_SECONDS), max(0.5, end_time - time.time())))
            continue

        # Envia para o Telegram
        sent = False
        if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            sent = send_deal_to_telegram(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, deal)
        else:
            print("   ℹ️ [Telegram não configurado no .env] Exibido apenas localmente.")
            sent = True

        if sent:
            mark_as_posted(deal)
            posted_in_window += 1
        
        # Pausa entre posts para manter o ritmo sem risco de flood no Telegram
        time_to_wait = min(float(config.POST_DELAY_SECONDS), max(0.0, end_time - time.time()))
        if time_to_wait > 0:
            time.sleep(time_to_wait)

    print("\n" + "=" * 65)
    print(f"🏁 [JANELA ATIVA DE {config.ACTIVE_SEND_MINUTES} MINUTOS CONCLUÍDA]")
    print(f"   Ofertas enviadas com sucesso: {posted_in_window}")
    print(f"   Ofertas ignoradas por repetição: {skipped_duplicates}")
    print("=" * 65)
    return posted_in_window

def main():
    parser = argparse.ArgumentParser(description="Bot de Ofertas Mercado Livre com Ciclos de 5min Envio / 10min Descanso")
    parser.add_argument("--preview", action="store_true", help="Apenas simula os envios no terminal sem gravar no banco ou Telegram")
    parser.add_argument("--once", action="store_true", help="Executa uma única janela ativa (5 minutos) e encerra")
    parser.add_argument("--loop", action="store_true", help="Executa continuamente: 5min enviando e 10min descansando")

    args = parser.parse_args()

    init_db()

    if args.preview:
        run_active_window(preview_only=True)
    elif args.loop:
        print(f"🚀 Bot iniciado em modo contínuo de ciclos!")
        print(f"   Ritmo: {config.ACTIVE_SEND_MINUTES} minutos enviando sem parar -> {config.REST_MINUTES} minutos descansando.")
        print(f"   Pressione Ctrl + C para parar a qualquer momento.\n")
        try:
            ciclo = 1
            while True:
                print(f"\n==================== [CICLO #{ciclo}] ====================")
                run_active_window(preview_only=False)

                proxima_rodada = datetime.now() + timedelta(minutes=config.REST_MINUTES)
                print(f"\n😴 [FASE DE DESCANSO] Pausando por {config.REST_MINUTES} minutos...")
                print(f"   Próxima rodada de envios começará exatamente às: {proxima_rodada.strftime('%H:%M:%S')}")
                
                time.sleep(config.REST_MINUTES * 60)
                ciclo += 1
        except KeyboardInterrupt:
            print("\n🛑 Bot interrompido pelo usuário.")
            sys.exit(0)
    else:
        # Padrão: loop contínuo
        print(f"🚀 Bot iniciado em modo de ciclos contínuos...")
        try:
            ciclo = 1
            while True:
                print(f"\n==================== [CICLO #{ciclo}] ====================")
                run_active_window(preview_only=False)
                proxima_rodada = datetime.now() + timedelta(minutes=config.REST_MINUTES)
                print(f"\n😴 [FASE DE DESCANSO] Pausando por {config.REST_MINUTES} minutos...")
                print(f"   Próxima rodada começará às: {proxima_rodada.strftime('%H:%M:%S')}")
                time.sleep(config.REST_MINUTES * 60)
                ciclo += 1
        except KeyboardInterrupt:
            print("\n🛑 Bot encerrado.")
            sys.exit(0)

if __name__ == "__main__":
    main()
