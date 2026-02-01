# BotX - Máquina de Monetização no X

Bot de automação para construir perfis no X com máximo potencial de monetização, baseado no algoritmo oficial do X.

## 🎯 Funcionalidades

### 1. Geração de Conteúdo Otimizado
- Hooks que prendem atenção
- CTAs que aumentam engajamento
- Integração com IA (OpenAI/Anthropic) para conteúdo único
- Templates por nicho (tech, finanças, humor, news, lifestyle)

### 2. Engajamento Estratégico
- Encontra posts virais automaticamente
- Replies inteligentes que adicionam valor
- Quote tweets de conteúdo trending
- Threads que maximizam dwell time

### 3. Strategy Engine
- Horários otimizados por nicho
- Mix de conteúdo ideal (posts/replies/threads)
- Rate limiting para evitar spam detection
- Delays humanizados

### 4. Analytics
- Tracking de impressões e engagement
- Progresso para monetização
- Análise de conteúdo que performa melhor
- Snapshots diários para tendências

## 🧠 Baseado no Algoritmo do X

O sistema é otimizado para maximizar o score do algoritmo:

```
Score = Σ (weight × P(action))
```

**Ações Positivas:**
- `P(favorite)` - Likes
- `P(reply)` - Respostas
- `P(repost)` - Reposts
- `P(dwell)` - Tempo na postagem
- `P(follow_author)` - Novos seguidores

**Ações Negativas (evitar):**
- `P(not_interested)`
- `P(block_author)`
- `P(mute_author)`
- `P(report)`

## 📦 Instalação

### 1. Clone o repositório
```bash
git clone https://github.com/uillenmachado/botx.git
cd botx
```

### 2. Configure o ambiente
```bash
cp dotenv_sample .env
# Edite .env com suas credenciais
```

### 3. Instale dependências
```bash
pip install -r requirements.txt
```

### 4. Inicialize o banco
```bash
flask db init
flask db migrate
flask db upgrade
```

## ⚙️ Configuração

### Variáveis de Ambiente

**Twitter API (obrigatório):**
```env
API_KEY=sua_api_key
API_KEY_SECRET=sua_api_secret
ACCESS_TOKEN=seu_access_token
ACCESS_TOKEN_SECRET=seu_access_secret
BEARER_TOKEN=seu_bearer_token
```

**Aplicação:**
```env
SECRET_KEY=chave_secreta_flask
ENVIRONMENT=development
```

**Bot (opcional):**
```env
BOT_NICHE=tech          # tech, finance, humor, news, lifestyle
BOT_INTERVAL=15         # Intervalo em minutos
OPENAI_API_KEY=sk-...   # Para geração com IA
ANTHROPIC_API_KEY=...   # Alternativa ao OpenAI
```

**Infraestrutura:**
```env
DATABASE_URI=sqlite:///bot.db
REDIS_URL=redis://localhost:6379/0
```

## 🚀 Uso

### Modo Web (API)
```bash
# Desenvolvimento
python main.py

# Produção
gunicorn -w 3 -b 0.0.0.0:8000 main:app
```

### Modo Daemon (Automação)
```bash
# Rodar continuamente
python bot_daemon.py --niche tech --interval 15

# Executar um ciclo
python bot_daemon.py --once
```

### Docker
```bash
docker build -t botx .
docker run -p 8000:8000 --env-file .env botx
```

## 🔌 API Endpoints

### Status & Analytics

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/bot/status` | GET | Status completo do bot |
| `/bot/analytics` | GET | Analytics detalhados |
| `/bot/monetization` | GET | Progresso para monetização |
| `/bot/schedule` | GET | Schedule do dia |

### Ações

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/bot/post` | POST | Criar post original |
| `/bot/reply` | POST | Criar reply estratégico |
| `/bot/thread` | POST | Criar thread |
| `/bot/quote` | POST | Criar quote tweet |
| `/bot/cycle` | POST | Executar ciclo completo |

### Discovery

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/bot/viral` | GET | Encontrar posts virais |
| `/bot/generate` | POST | Gerar conteúdo (preview) |

### Exemplos de Uso

**Criar post:**
```bash
curl -X POST http://localhost:8000/bot/post \
  -H "Content-Type: application/json" \
  -d '{"topic": "inteligência artificial", "style": "informativo"}'
```

**Preview de conteúdo:**
```bash
curl -X POST http://localhost:8000/bot/generate \
  -H "Content-Type: application/json" \
  -d '{"type": "post", "topic": "produtividade", "dry_run": true}'
```

**Encontrar posts virais:**
```bash
curl "http://localhost:8000/bot/viral?query=tech&min_likes=100"
```

## 📊 Requisitos para Monetização

Para ser elegível ao X Premium Revenue Share:

| Requisito | Status |
|-----------|--------|
| X Premium | Assinatura ativa |
| Seguidores | 500+ |
| Impressões | 5M+ (3 meses) |
| Idade da conta | 90+ dias |

O bot mostra seu progresso em `/bot/monetization`.

## 🎯 Nichos Suportados

| Nicho | Keywords | Melhor Horário |
|-------|----------|----------------|
| tech | IA, programação, startup | 8-9h, 18-21h |
| finance | investimento, ações, dinheiro | 7-9h, 17-18h |
| humor | meme, piada, zueira | 12-13h, 19-23h |
| news | notícia, política | 7-9h, 18-20h |
| lifestyle | produtividade, hábitos | 6-8h, 19-21h |

## 📁 Estrutura

```
botx/
├── app/
│   ├── models/              # SQLAlchemy models
│   ├── routes/              # Flask blueprints
│   │   ├── core.py          # Rotas básicas
│   │   ├── auth.py          # Autenticação
│   │   └── bot_routes.py    # API do bot
│   ├── services/
│   │   ├── twitter_service.py   # Client Twitter
│   │   ├── bot_engine.py        # Motor principal
│   │   ├── engagement/          # Finder de posts virais
│   │   ├── content/             # Geração de conteúdo
│   │   ├── strategy/            # Timing e mix
│   │   └── analytics/           # Métricas
│   ├── templates/           # HTML
│   └── static/              # CSS/JS
├── data/                    # Dados persistentes
│   └── analytics/           # Snapshots diários
├── bot_daemon.py            # Daemon de automação
├── scheduler.py             # Scheduler de posts
├── main.py                  # Entry point
└── requirements.txt
```

## ⚠️ Avisos

1. **Rate Limits:** O bot respeita os limites da API do X. Não tente burlar.

2. **ToS do X:** Use com responsabilidade. Automação excessiva pode resultar em suspensão.

3. **Conteúdo:** O bot gera conteúdo, mas você é responsável pelo que publica.

4. **Credenciais:** Nunca commite suas credenciais. Use `.env`.

## 📈 Métricas de Sucesso

| Fase | Seguidores | Impressões/mês | Posts/dia |
|------|------------|----------------|-----------|
| Início | 0-500 | 0-100K | 3-5 |
| Crescimento | 500-5K | 100K-1M | 5-10 |
| Escala | 5K-50K | 1M-5M | 10-15 |
| Monetização | 50K+ | 5M+ | 15+ |

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Add nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📄 Licença

MIT
