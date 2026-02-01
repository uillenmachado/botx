# BotX - Twitter/X Bot

Bot de automação para Twitter/X com interface web para postar tweets, agendar posts e gerar conteúdo automático.

## Stack

- **Backend:** Flask 3.0 + SQLAlchemy + Flask-Login + Flask-RESTX
- **Async:** Celery + Redis
- **Database:** SQLite (padrão) ou qualquer SQL via URI
- **Deploy:** Docker + Gunicorn

## Setup

### 1. Configurar variáveis de ambiente

```bash
cp dotenv_sample .env
# Edite .env com suas credenciais do Twitter
```

**Variáveis obrigatórias:**
- `API_KEY` - Twitter API Key
- `API_KEY_SECRET` - Twitter API Key Secret
- `ACCESS_TOKEN` - Twitter Access Token
- `ACCESS_TOKEN_SECRET` - Twitter Access Token Secret
- `BEARER_TOKEN` - Twitter Bearer Token
- `SECRET_KEY` - Chave secreta para sessões Flask

**Variáveis opcionais:**
- `DATABASE_URI` - URI do banco (default: `sqlite:///bot.db`)
- `REDIS_URL` - URL do Redis (default: `redis://localhost:6379/0`)
- `RATELIMIT` - Limite de posts por janela (default: 25)
- `RATELIMIT_WINDOW` - Janela em segundos (default: 86400 = 24h)
- `ENVIRONMENT` - `development` ou `production`

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Inicializar banco de dados

```bash
flask db init
flask db migrate
flask db upgrade
```

### 4. Rodar a aplicação

**Desenvolvimento:**
```bash
python main.py
```

**Produção (Docker):**
```bash
docker build -t botx .
docker run -p 8000:8000 --env-file .env botx
```

### 5. Rodar o scheduler (em outro terminal)

```bash
python scheduler.py
```

### 6. Rodar o Celery worker (opcional, para posts assíncronos)

```bash
celery -A celery_app.celery worker --loglevel=info
```

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Interface web |
| POST | `/generate` | Gerar post automático |
| POST | `/post` | Postar tweet |
| POST | `/schedule` | Agendar tweet |
| GET | `/scheduled` | Listar agendados (JSON) |
| GET | `/scheduled_view` | Listar agendados (HTML) |
| GET | `/history` | Histórico de tweets |
| POST | `/upload` | Upload de imagem |
| GET | `/docs` | Documentação da API (Swagger) |

## Estrutura

```
botx/
├── app/
│   ├── models/         # SQLAlchemy models
│   ├── routes/         # Flask blueprints
│   ├── services/       # Twitter service, rate limiter
│   ├── static/         # CSS, JS
│   ├── templates/      # HTML templates
│   └── config.py       # Configurações
├── tests/              # Testes unitários
├── scheduler.py        # Daemon de agendamento
├── tasks.py            # Tarefas Celery
├── celery_app.py       # Config do Celery
└── main.py             # Entry point
```

## Rate Limiting

O rate limiter usa Redis para funcionar corretamente com múltiplos workers. Se Redis não estiver disponível, usa fallback em memória (adequado apenas para desenvolvimento single-process).

## Licença

MIT
