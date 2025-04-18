# Twitter Sarcastic Bot

Pequeno bot em Flask + Tweepy que gera tweets sarcásticos em português, publica imediatamente ou agenda para horários específicos.

## 🚀 Funcionalidades

- **Geração de tweets** no estilo "Lutador Estoico e Sarcástico"
- **Publicação instantânea** ou **agendamento diário**
- **Persistência** dos agendamentos em `scheduled_posts.json`
- **Página web** com contagem de caracteres e listagem de posts agendados
- **Tratamento de erros** e limite diário de 25 tweets (ajustável)
- Rota `/scheduled` retorna JSON de posts pendentes

## 🛡️ Segurança

- Credenciais são carregadas via variáveis de ambiente.
- Adicione `.env` ao `.gitignore` para evitar leaks.
- Revogue imediatamente chaves expostas.

Exemplo de `.env`:

```
API_KEY=...
API_KEY_SECRET=...
ACCESS_TOKEN=...
ACCESS_TOKEN_SECRET=...
PORT=5000
```

## 📦 Instalação

```bash
git clone <repo-url>
cd twitter_bot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 💻 Uso local

```bash
python bot.py
# Visite http://localhost:5000
```

## ⏫ Deploy rápido

### Render

1. Crie um novo serviço Web.
2. Selecione Python, apontando para `bot.py` como *start command* (`python bot.py`).
3. Adicione variáveis de ambiente na aba **Environment**.
4. Defina o *Build Command* como `pip install -r requirements.txt`.

### PythonAnywhere (free)

1. Suba os arquivos pelo painel ou Git.
2. Crie um **Web App** apontando para `flask` (WSGI).
3. Edite o arquivo WSGI para importar `app` de `bot`.
4. Adicione variáveis no *Virtualenv* ou no painel **Environment Variables**.

> **Limitação da API grátis**: atualmente permite ~150 tweets por 24 h.  
> Este projeto impõe limite de 25 por segurança.

## 🎯 Exemplo de fluxo

1. Abra a página e digite um contexto (ou deixe em branco).
2. Clique em “Gerar Post” → texto é criado e contagem de caracteres aparece.
3. **Postar Agora** publica imediatamente ou  
   defina um horário e clique em **Agendar**.
4. Em “Ver Posts Agendados” veja a lista de tweets pendentes.

Boa diversão! 🎉