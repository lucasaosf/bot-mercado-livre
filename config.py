import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

# Credenciais de Afiliado Mercado Livre (obtidas no .env)
MATT_TOOL = os.getenv("MATT_TOOL", "")
MATT_WORD = os.getenv("MATT_WORD", "")

# Credenciais de Afiliado Amazon (obtidas no .env)
AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "")

# Credenciais de Afiliado AliExpress (obtidas no .env)
ALIEXPRESS_AFF_FSK = os.getenv("ALIEXPRESS_AFF_FSK", "_mqTQekn")

# Filtros de Ofertas e Ciclos de Envio
MIN_DISCOUNT_PCT = int(os.getenv("MIN_DISCOUNT_PCT", "20"))  # Desconto mínimo (%)
ACTIVE_SEND_MINUTES = int(os.getenv("ACTIVE_SEND_MINUTES", "5")) # Minutos enviando ofertas sem parar
REST_MINUTES = int(os.getenv("REST_MINUTES", "10"))              # Minutos de descanso antes do próximo ciclo
POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "6"))   # Intervalo entre envios (segundos) para evitar flood
REPOST_AFTER_DAYS = int(os.getenv("REPOST_AFTER_DAYS", "3"))     # Dias antes de poder repostar o mesmo item

# Configuração do Telegram (Opcional - preencher no .env se for usar)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
