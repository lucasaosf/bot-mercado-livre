import os
from dotenv import load_dotenv

load_dotenv()

# Credenciais de Afiliado Mercado Livre (obtidas no .env)
MATT_TOOL = os.getenv("MATT_TOOL", "")
MATT_WORD = os.getenv("MATT_WORD", "")

# Filtros de Ofertas
MIN_DISCOUNT_PCT = int(os.getenv("MIN_DISCOUNT_PCT", "25"))  # Desconto mínimo (%)
MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "5")) # Quantidade de ofertas postadas por ciclo
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60")) # Intervalo entre verificações
REPOST_AFTER_DAYS = int(os.getenv("REPOST_AFTER_DAYS", "3")) # Dias antes de poder repostar o mesmo item

# Configuração do Telegram (Opcional - preencher no .env se for usar)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
