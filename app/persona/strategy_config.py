"""
Configuração de Estratégia específica para Caco Fakessen

Define:
- Keywords de busca para cada pilar
- Alvos de engajamento
- Horários otimizados
- Mix de conteúdo diário
"""

STRATEGY_CONFIG = {
    # Mix diário de conteúdo
    "daily_mix": {
        "posts_originais": 6,      # Posts com conteúdo próprio
        "replies_estrategicos": 30, # Replies em posts virais/relevantes
        "comparacoes_1mundo": 2,    # Posts comparando Brasil x 1º mundo
        "reacoes_noticias": 3,      # Reagir a notícias do momento
        "threads": 1,               # Uma thread por dia
    },
    
    # Keywords de busca por pilar
    "search_keywords": {
        "politica_direita": [
            "Lula", "PT", "governo", "imposto", "STF",
            "esquerda", "socialismo", "comunismo",
            "MST", "MTST", "Boulos", "PSOL",
        ],
        "economia": [
            "inflação", "dólar", "Selic", "investimento",
            "bolsa", "mercado", "PIB", "recessão",
            "B3", "ações", "FIIs", "cripto",
        ],
        "tech": [
            "IA", "inteligência artificial", "ChatGPT", "OpenAI",
            "programação", "startup", "tech", "inovação",
            "Elon Musk", "Apple", "Google", "Microsoft",
        ],
        "comportamento": [
            "geração Z", "jovens", "millennial",
            "woke", "cancelamento", "pronome",
            "coach", "curso", "mentoria",
        ],
        "brasil": [
            "Brasil", "brasileiro", "São Paulo", "Rio",
            "trânsito", "segurança", "educação pública",
            "SUS", "corrupção", "político",
        ],
    },
    
    # Contas para monitorar e engajar
    "accounts_to_engage": {
        "aliados_potenciais": [
            # Contas de direita/liberais que o Caco concordaria
            # (preencher com @usernames reais)
        ],
        "alvos_para_ironizar": [
            # Contas de esquerda para replies irônicos
            # (preencher com @usernames reais)
        ],
        "perfis_virais": [
            # Contas com muito alcance para pegar carona
            # (preencher com @usernames reais)
        ],
    },
    
    # Horários otimizados para o público do Caco
    # (empresários, investidores, público 30+)
    "horarios_pico": {
        "manha_cedo": {
            "inicio": 6,
            "fim": 8,
            "score": 0.8,
            "tipo_conteudo": ["produtividade", "financas"],
            "nota": "Empresários acordando, checando mercado",
        },
        "manha": {
            "inicio": 8,
            "fim": 10,
            "score": 0.9,
            "tipo_conteudo": ["tech_ia", "financas", "noticias"],
            "nota": "Pico de atividade profissional",
        },
        "almoco": {
            "inicio": 12,
            "fim": 14,
            "score": 0.85,
            "tipo_conteudo": ["humor_elitista", "politica"],
            "nota": "Pausa, pessoas scrollando",
        },
        "tarde": {
            "inicio": 14,
            "fim": 17,
            "score": 0.5,
            "tipo_conteudo": ["replies"],
            "nota": "Menor engajamento, focar em replies",
        },
        "fim_tarde": {
            "inicio": 17,
            "fim": 19,
            "score": 0.7,
            "tipo_conteudo": ["financas", "noticias"],
            "nota": "Fechamento mercado, análises",
        },
        "noite": {
            "inicio": 19,
            "fim": 22,
            "score": 1.0,
            "tipo_conteudo": ["humor_elitista", "threads", "comparacoes"],
            "nota": "PICO MÁXIMO - Conteúdo principal aqui",
        },
        "noite_tarde": {
            "inicio": 22,
            "fim": 24,
            "score": 0.75,
            "tipo_conteudo": ["humor_elitista", "reflexoes"],
            "nota": "Público mais engajado scrollando",
        },
    },
    
    # Triggers para reagir a notícias
    "news_triggers": {
        "alta_prioridade": [
            "Lula", "PT", "governo", "STF", "impeachment",
            "corrupção", "escândalo", "prisão", "CPI",
            "dólar dispara", "inflação", "Selic",
        ],
        "media_prioridade": [
            "educação", "saúde", "segurança", "violência",
            "startup", "investimento", "IPO", "unicórnio",
        ],
        "oportunidade": [
            "viral", "trending", "polêmica", "cancelado",
            "geração Z", "jovens", "millennial",
        ],
    },
    
    # Estratégia de replies
    "reply_strategy": {
        "posts_virais": {
            "min_likes": 500,
            "max_age_minutes": 60,
            "prioridade": "alta",
            "objetivo": "Aparecer no feed de muita gente",
        },
        "posts_polemicos": {
            "keywords": ["discordo", "absurdo", "vergonha", "inaceitável"],
            "prioridade": "media",
            "objetivo": "Gerar discussão e engagement",
        },
        "posts_esquerda": {
            "keywords": ["desigualdade", "capitalismo", "elite", "privilégio"],
            "prioridade": "media",
            "objetivo": "Ironizar com classe",
        },
        "posts_tech": {
            "keywords": ["IA", "ChatGPT", "futuro", "inovação"],
            "prioridade": "alta",
            "objetivo": "Se posicionar como voz de autoridade",
        },
    },
    
    # Métricas de sucesso
    "metas": {
        "diario": {
            "impressoes": 10000,
            "likes": 100,
            "replies": 20,
            "novos_seguidores": 10,
        },
        "semanal": {
            "impressoes": 100000,
            "likes": 1000,
            "replies": 200,
            "novos_seguidores": 100,
        },
        "mensal": {
            "impressoes": 500000,
            "seguidores_total": 1000,
            "engagement_rate": 3.0,  # %
        },
        "monetizacao": {
            "seguidores_minimo": 500,
            "impressoes_3meses": 5000000,
            "idade_conta_dias": 90,
        },
    },
    
    # Conteúdo a evitar (para não ser banido/shadowbanned)
    "evitar": [
        "Xingamentos diretos",
        "Ameaças",
        "Discurso de ódio explícito",
        "Desinformação factual",
        "Spam repetitivo",
        "Menção a violência",
        "Informações pessoais de terceiros",
    ],
    
    # Dicas de otimização para o algoritmo
    "otimizacao_algoritmo": {
        "aumenta_score": [
            "Posts com perguntas (geram replies)",
            "Imagens e vídeos (maior dwell time)",
            "Threads (muito engajamento)",
            "Responder próprios replies (thread conversation)",
            "Postar nos horários de pico",
        ],
        "diminui_score": [
            "Links externos (X não gosta)",
            "Muitas hashtags (parece spam)",
            "Posts idênticos repetidos",
            "Muitos replies em pouco tempo",
            "Conteúdo que gera blocks/mutes",
        ],
    },
}


def get_keywords_for_search(categoria: str = None) -> list:
    """Retorna keywords para busca"""
    if categoria and categoria in STRATEGY_CONFIG["search_keywords"]:
        return STRATEGY_CONFIG["search_keywords"][categoria]
    
    # Retorna todas se não especificou
    all_keywords = []
    for kws in STRATEGY_CONFIG["search_keywords"].values():
        all_keywords.extend(kws)
    return list(set(all_keywords))


def get_current_content_type(hour: int) -> list:
    """Retorna tipos de conteúdo recomendados para a hora atual"""
    for periodo, config in STRATEGY_CONFIG["horarios_pico"].items():
        if config["inicio"] <= hour < config["fim"]:
            return config["tipo_conteudo"]
    return ["replies"]  # Default


def should_react_to_news(headline: str) -> tuple:
    """Verifica se deve reagir a uma notícia"""
    headline_lower = headline.lower()
    
    for trigger in STRATEGY_CONFIG["news_triggers"]["alta_prioridade"]:
        if trigger.lower() in headline_lower:
            return True, "alta"
    
    for trigger in STRATEGY_CONFIG["news_triggers"]["media_prioridade"]:
        if trigger.lower() in headline_lower:
            return True, "media"
    
    for trigger in STRATEGY_CONFIG["news_triggers"]["oportunidade"]:
        if trigger.lower() in headline_lower:
            return True, "oportunidade"
    
    return False, None
