# 🛒 Bot de Melhores Ofertas do Mercado Livre (com Afiliados)

Este bot monitora automaticamente os **produtos mais vendidos e com maiores descontos** do Mercado Livre, filtra as melhores ofertas e publica automaticamente cards promocionais com foto, preço, cálculo de desconto e tags de afiliado em canais ou grupos do **Telegram**.

---

## 🔑 Configuração de Afiliado

Para que as comissões sejam atribuídas à sua conta de afiliado do Mercado Livre, basta preencher as suas credenciais no arquivo `.env`:

- **`MATT_TOOL`**: ID da sua ferramenta de afiliado
- **`MATT_WORD`**: Seu identificador ou palavra-chave de afiliado

Todos os links gerados pelo bot receberão automaticamente a terminação:
`?matt_tool=SEU_MATT_TOOL&matt_word=SEU_MATT_WORD`

---

## 🚀 Como Funciona

1. **Coleta Inteligente**: Acessa a lista de produtos mais vendidos do Mercado Livre em tempo real simulando navegação segura (`curl_cffi` com TLS Fingerprint do Chrome, sem bloqueio de robô).
2. **Cálculo de Desconto Real**: Compara o preço anterior ("De:") com o promocional ("Por:") e calcula o `% OFF` exato.
3. **Filtro de Qualidade**: Somente envia produtos com desconto acima do mínimo estipulado (padrão: 25% de desconto).
4. **Anti-Duplicação**: Banco de dados SQLite local (`deals.db`) para garantir que o mesmo produto não seja enviado repetidamente.
5. **Divulgação Automática**: Pronto para enviar para Canais/Grupos do **Telegram** com foto em alta qualidade, botão de compra e texto formatado.

---

## 📦 Instalação e Execução

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Modos de Uso

#### A. Apenas visualizar as ofertas no terminal (Modo Preview):
Mostra as melhores ofertas encontradas no momento sem salvar no banco de dados e sem disparar para o Telegram:
```bash
python bot.py --preview
```

#### B. Executar um único ciclo:
```bash
python bot.py --once
```

#### C. Executar em modo contínuo de ciclos (Recomendado):
O bot enviará ofertas durante 5 minutos sem parar e descansará por 10 minutos antes de repetir o ciclo:
```bash
python bot.py --loop
```

---

## 📲 Como Conectar ao Telegram (Opcional)

Se quiser que o bot poste automaticamente em um Canal ou Grupo do Telegram:

1. Abra o Telegram e converse com o **@BotFather**.
2. Digite `/newbot` e siga as instruções para criar o seu bot. Ele te dará um **Token** (ex: `123456789:ABCdefGhIJKlmNo...`).
3. Crie seu Canal/Grupo no Telegram e **adicione o seu bot como Administrador**.
4. Abra o arquivo `.env` na pasta do projeto e preencha:
   ```env
   TELEGRAM_BOT_TOKEN="seu_token_aqui"
   TELEGRAM_CHAT_ID="@nomedoseucanal" # ou o ID numérico do grupo (ex: -100xxxxxxxxxx)
   ```
5. Execute `python bot.py --loop`.

---

## ⚙️ Ajuste de Preferências (`.env`)

Você pode alterar o ritmo e filtros a qualquer momento no arquivo `.env`:

- `MIN_DISCOUNT_PCT`: Desconto mínimo para postar (ex: `20` para produtos com 20%+ OFF).
- `ACTIVE_SEND_MINUTES`: Duração da janela ativa de envios sem parar (padrão: `5` minutos).
- `REST_MINUTES`: Tempo de descanso antes de iniciar o próximo ciclo (padrão: `10` minutos).
- `POST_DELAY_SECONDS`: Intervalo entre mensagens no Telegram para manter o ritmo sem risco de bloqueio (padrão: `6` segundos).
- `REPOST_AFTER_DAYS`: Dias que o bot deve esperar antes de permitir reenviar o mesmo produto caso continue em oferta (padrão: `3`).
