# Twitter Sarcastic Bot (v3)

Bot em Flask + Tweepy que gera tweets sarcásticos em português — publica ou agenda de forma segura, robusta e responsiva.

## Principais Recursos
- **Geração de conteúdo**: combina provocações e frases de impacto lidas de arquivos JSON.
- **Publicação & Agendamento**: Rota web simples; agendamentos persistem em `scheduled_posts.json`.
- **Rate Limiting**: Limitador deslizando (25 tweets / 24 h) alinhado à API free do Twitter.
- **Persistência de contagem**: `post_count.json` evita exceder limites após reinício.
- **Reenvio de posts perdidos**: envia tweets agendados que ficaram dentro da janela de 30 min enquanto offline.
- **Retry & Backoff**: Tenta novamente em caso de rate‑limit.
- **Exclusão de agendamentos** e **histórico dos últimos 20 tweets**.
- **Interface web**: contagem de caracteres, notificações animadas, visualização/remoção de agendados e histórico.
- **CSRF Protection** via Flask‑WTF.
- **Logging** com rotação (`bot.log` 1 MB ×5).
- **Deploy‑ready** (Render, PythonAnywhere).

## Atualização de Conteúdo
Edite ou adicione frases em `content/provocacoes.json` e `content/frases_impacto.json`.

## Instalação Rápida
```bash
git clone <repo-url>
cd twitter_bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo -e "API_KEY=...\nAPI_KEY_SECRET=...\nACCESS_TOKEN=...\nACCESS_TOKEN_SECRET=..." > .env
python bot.py
# http://localhost:5000
```

## Deploy (Render)
- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`
- Variáveis de ambiente: mesmas do `.env` + `SECRET_KEY` (opcional).

**Importante**: Revogue imediatamente chaves expostas. Adicione `.env`, `bot.log`, `*.json` ao `.gitignore` (já incluso).

Bom proveito! 🚀