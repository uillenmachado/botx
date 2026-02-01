"""
Content Engine - Gera conteúdo na voz do Caco Fakessen
"""
import os
import re
import random
import logging
from typing import List, Dict, Optional
from pathlib import Path
import requests

from ...persona import PERSONA, get_bordao, get_referencia_primeiro_mundo, get_frase_efeito

logger = logging.getLogger(__name__)


class ContentEngine:
    """
    Gera conteúdo na voz do Caco Fakessen.
    
    Características:
    - Humor ácido e elitista
    - Comparações com primeiro mundo
    - Ironia passivo-agressiva
    - Anti-esquerda/woke/vitimismo
    """
    
    def __init__(self, openai_api_key: str = None, anthropic_api_key: str = None):
        self.openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.persona = PERSONA
    
    def _get_system_prompt(self) -> str:
        """Retorna o prompt de sistema para a IA"""
        return f"""Você é {self.persona['nome']}, conhecido como "{self.persona['apelido']}".

BACKGROUND:
- {self.persona['background']['origem']}
- {self.persona['background']['residencia']}
- {self.persona['background']['educacao']}

PERSONALIDADE:
- Tom: {self.persona['personalidade']['tom']}
- Estilo: {self.persona['personalidade']['estilo']}
- Posicionamento: {self.persona['personalidade']['posicionamento']}
- Visão: {self.persona['personalidade']['visao_pobreza']}

VOCÊ ODEIA: {', '.join(self.persona['personalidade']['odeia'])}
VOCÊ ADMIRA: {', '.join(self.persona['personalidade']['admira'])}

COMO VOCÊ FALA:
{chr(10).join('- ' + c for c in self.persona['voz']['caracteristicas'])}

BORDÕES QUE USA:
{chr(10).join('- "' + b + '"' for b in self.persona['voz']['bordoes'][:5])}

CIDADES QUE REFERENCIA: {', '.join(self.persona['referencias_primeiro_mundo'][:8])}

REGRAS:
1. Nunca xingue diretamente - use ironia cortante
2. Seja breve e impactante (máximo 280 caracteres)
3. Use comparações com primeiro mundo quando relevante
4. Mantenha tom de superioridade refinada, não grosseria
5. Evite hashtags
6. Não seja explicitamente político - seja sutil e irônico
7. O humor é a arma principal"""
    
    def generate_post(
        self,
        topic: str = None,
        pilar: str = None,
        max_length: int = 280,
        use_ai: bool = True
    ) -> str:
        """
        Gera um post na voz do Caco.
        
        Args:
            topic: Assunto específico (opcional)
            pilar: Pilar de conteúdo (humor_elitista, tech_ia, financas, produtividade, politica_news)
            max_length: Tamanho máximo
            use_ai: Usar IA para gerar
        
        Returns:
            Post no estilo Caco Fakessen
        """
        # Se não especificou pilar, escolhe baseado nas prioridades
        if not pilar:
            pilar = self._choose_pilar()
        
        if use_ai and (self.openai_key or self.anthropic_key):
            return self._generate_with_ai(topic, pilar, max_length)
        else:
            return self._generate_template(pilar)
    
    def _choose_pilar(self) -> str:
        """Escolhe pilar baseado nas prioridades"""
        pilares = self.persona["pilares"]
        # Criar lista ponderada
        choices = []
        for nome, config in pilares.items():
            choices.extend([nome] * config["prioridade"])
        return random.choice(choices)
    
    def _generate_with_ai(self, topic: str, pilar: str, max_length: int) -> str:
        """Gera conteúdo usando LLM"""
        
        pilar_info = self.persona["pilares"].get(pilar, {})
        exemplos = pilar_info.get("exemplos", [])
        
        prompt = f"""Crie um tweet como Caco Fakessen.

PILAR: {pilar} - {pilar_info.get('descricao', '')}
{'TEMA: ' + topic if topic else 'TEMA: Livre, escolha algo relevante do momento'}

EXEMPLOS DO ESTILO:
{chr(10).join('- ' + e for e in exemplos[:3])}

REGRAS:
- Máximo {max_length} caracteres
- Seja irônico e cortante
- Pode usar comparação com primeiro mundo
- Termine com uma "cortada" ou observação ácida
- NÃO use hashtags
- NÃO seja explícito demais - a graça está na sutileza

Retorne APENAS o tweet, sem explicações."""

        try:
            if self.anthropic_key:
                return self._call_anthropic(prompt)
            elif self.openai_key:
                return self._call_openai(prompt)
        except Exception as e:
            logger.error(f"Erro na geração com IA: {e}")
        
        return self._generate_template(pilar)
    
    def _call_anthropic(self, prompt: str) -> str:
        """Chama API da Anthropic"""
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.anthropic_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 300,
                "system": self._get_system_prompt(),
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"].strip()
    
    def _call_openai(self, prompt: str) -> str:
        """Chama API da OpenAI"""
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 300,
                "temperature": 0.9
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    
    def _generate_template(self, pilar: str) -> str:
        """Gera conteúdo usando templates"""
        pilar_info = self.persona["pilares"].get(pilar, {})
        exemplos = pilar_info.get("exemplos", [])
        
        if exemplos:
            # Usar exemplo como base e variar
            base = random.choice(exemplos)
            # Às vezes adiciona bordão
            if random.random() < 0.3:
                base += f" {get_bordao()}"
            return base
        
        # Fallback: frase de efeito + bordão
        return f"{get_frase_efeito()} {get_bordao()}"
    
    def generate_reply(
        self,
        original_post: str,
        author: str,
        post_sentiment: str = "neutral",
        use_ai: bool = True
    ) -> str:
        """
        Gera reply na voz do Caco.
        
        Args:
            original_post: Texto do post original
            author: Username do autor
            post_sentiment: Sentimento do post (left, right, neutral, viral_tech, viral_economy)
            use_ai: Usar IA
        """
        # Determinar tipo de reply
        if "esquerda" in post_sentiment or "left" in post_sentiment:
            reply_type = "contra_esquerda"
        elif "direita" in post_sentiment or "right" in post_sentiment:
            reply_type = "concordancia_direita"
        elif "tech" in post_sentiment:
            reply_type = "posts_virais_tech"
        elif "econom" in post_sentiment:
            reply_type = "posts_virais_economia"
        else:
            reply_type = "posts_virais_tech"  # Default
        
        if use_ai and (self.openai_key or self.anthropic_key):
            return self._generate_reply_ai(original_post, author, reply_type)
        else:
            return self._generate_reply_template(reply_type)
    
    def _generate_reply_ai(self, original_post: str, author: str, reply_type: str) -> str:
        """Gera reply usando IA"""
        
        reply_config = self.persona["replies"].get(reply_type, {})
        exemplos = reply_config.get("exemplos", [])
        tom = reply_config.get("tom", "irônico")
        
        prompt = f"""Crie uma resposta como Caco Fakessen para este tweet de @{author}:

"{original_post}"

TOM ESPERADO: {tom}

EXEMPLOS DO ESTILO:
{chr(10).join('- ' + e for e in exemplos)}

REGRAS:
- Máximo 200 caracteres
- Seja irônico, não grosseiro
- Uma cortada rápida e elegante
- Não mencione o @ do autor (já está em reply)
- NÃO use hashtags

Retorne APENAS a resposta."""

        try:
            if self.anthropic_key:
                return self._call_anthropic(prompt)
            elif self.openai_key:
                return self._call_openai(prompt)
        except Exception as e:
            logger.error(f"Erro ao gerar reply: {e}")
        
        return self._generate_reply_template(reply_type)
    
    def _generate_reply_template(self, reply_type: str) -> str:
        """Gera reply usando templates"""
        reply_config = self.persona["replies"].get(reply_type, {})
        exemplos = reply_config.get("exemplos", [])
        
        if exemplos:
            return random.choice(exemplos)
        
        return get_bordao()
    
    def generate_thread(
        self,
        topic: str,
        num_tweets: int = 5,
        pilar: str = None
    ) -> List[str]:
        """
        Gera uma thread na voz do Caco.
        """
        if not pilar:
            pilar = self._choose_pilar()
        
        if self.openai_key or self.anthropic_key:
            return self._generate_thread_ai(topic, num_tweets, pilar)
        else:
            return self._generate_thread_template(topic, num_tweets, pilar)
    
    def _generate_thread_ai(self, topic: str, num_tweets: int, pilar: str) -> List[str]:
        """Gera thread usando IA"""
        
        pilar_info = self.persona["pilares"].get(pilar, {})
        
        prompt = f"""Crie uma thread de {num_tweets} tweets como Caco Fakessen sobre: {topic}

PILAR: {pilar} - {pilar_info.get('descricao', '')}

ESTRUTURA:
1/ Hook irônico que prende atenção
2-{num_tweets-1}/ Desenvolvimento com observações ácidas
{num_tweets}/ Conclusão com cortada final

REGRAS:
- Cada tweet máximo 280 caracteres
- Numere os tweets (1/, 2/, etc)
- Mantenha o tom irônico e elitista
- Pode incluir comparações com primeiro mundo
- Termine com observação devastadora
- NÃO use hashtags

Formato:
TWEET_1: [conteúdo]
TWEET_2: [conteúdo]
..."""

        try:
            if self.anthropic_key:
                response = self._call_anthropic(prompt)
            elif self.openai_key:
                response = self._call_openai(prompt)
            
            tweets = []
            for line in response.split("\n"):
                if line.startswith("TWEET_"):
                    content = line.split(":", 1)[1].strip() if ":" in line else ""
                    if content:
                        tweets.append(content)
            
            return tweets if tweets else self._generate_thread_template(topic, num_tweets, pilar)
            
        except Exception as e:
            logger.error(f"Erro ao gerar thread: {e}")
            return self._generate_thread_template(topic, num_tweets, pilar)
    
    def _generate_thread_template(self, topic: str, num_tweets: int, pilar: str) -> List[str]:
        """Gera thread usando templates"""
        tweets = []
        cidade = get_referencia_primeiro_mundo()
        
        tweets.append(f"1/ Thread sobre {topic}. Ou como eu chamo: 'coisas óbvias que o Brasil ainda não entendeu'. 🧵")
        
        pilar_info = self.persona["pilares"].get(pilar, {})
        exemplos = pilar_info.get("exemplos", [])
        
        for i in range(2, num_tweets):
            if exemplos and random.random() < 0.7:
                tweets.append(f"{i}/ {random.choice(exemplos)}")
            else:
                tweets.append(f"{i}/ Em {cidade} isso já foi resolvido há décadas. Mas aqui ainda estamos discutindo o básico.")
        
        tweets.append(f"{num_tweets}/ Resumindo: {get_frase_efeito()} {get_bordao()}")
        
        return tweets
    
    def generate_reaction_to_news(self, news_headline: str, news_topic: str = "geral") -> str:
        """
        Gera reação a uma notícia no estilo Caco.
        
        Útil para aproveitar breaking news e aumentar engajamento.
        """
        if self.openai_key or self.anthropic_key:
            prompt = f"""Como Caco Fakessen, reaja a esta notícia:

"{news_headline}"

REGRAS:
- Máximo 280 caracteres  
- Seja irônico, não partidário explícito
- Pode fazer comparação com primeiro mundo
- Use seu humor ácido característico
- Uma observação cortante sobre a situação
- NÃO use hashtags

Retorne APENAS o tweet."""

            try:
                if self.anthropic_key:
                    return self._call_anthropic(prompt)
                elif self.openai_key:
                    return self._call_openai(prompt)
            except Exception as e:
                logger.error(f"Erro ao reagir a notícia: {e}")
        
        # Fallback
        return f"Mais uma notícia do Brasil. {get_bordao()}"
    
    def generate_comparison_post(self) -> str:
        """
        Gera post comparando Brasil com primeiro mundo.
        
        Tipo de conteúdo que o Caco faz muito bem.
        """
        cidade = get_referencia_primeiro_mundo()
        
        comparacoes = [
            f"Saudades de {cidade}. Lá as pessoas entendem o conceito de fila. Aqui é luta pela sobrevivência.",
            f"Em {cidade}, o transporte público funciona. Aqui é roleta russa. Mas a culpa é sempre do 'sistema', né.",
            f"Voltei de {cidade}. Lá não tem funk no último volume às 3h da manhã. Conceito revolucionário.",
            f"Curioso como em {cidade} as calçadas existem. Aqui é safari urbano.",
            f"Lembrei de {cidade}. Lá você pode andar com celular na mão. Vida de primeiro mundo é outra coisa.",
            f"Em {cidade}, pontualidade é básico. Aqui é virtude rara. Enfim, né.",
        ]
        
        return random.choice(comparacoes)
