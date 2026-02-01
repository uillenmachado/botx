"""
Content Engine - Gera conteúdo otimizado para o algoritmo do X
"""
import os
import re
import json
import random
import logging
from typing import List, Dict, Optional
from pathlib import Path
import requests

logger = logging.getLogger(__name__)


class ContentEngine:
    """
    Gera conteúdo otimizado para maximizar engajamento no X.
    
    Baseado no algoritmo do X:
    - Hooks fortes no início (aumenta dwell time)
    - CTAs para replies (aumenta P(reply))
    - Conteúdo emocional (aumenta P(like), P(repost))
    - Perguntas (aumenta P(reply))
    """
    
    # Templates de hooks que funcionam
    HOOKS = [
        "🚨 Isso vai mudar tudo:",
        "A verdade que ninguém conta:",
        "Você não vai acreditar, mas...",
        "Segredo revelado:",
        "THREAD importante 🧵",
        "Preciso compartilhar isso:",
        "Descobri algo incrível:",
        "Atenção, isso é sério:",
        "O que ninguém te fala sobre",
        "Acabei de perceber uma coisa:",
    ]
    
    # CTAs para aumentar replies
    CTAS = [
        "Concorda? 👇",
        "O que você acha?",
        "Comenta aí sua opinião 👇",
        "Discorda? Me conta por quê",
        "RT se você também pensa assim",
        "Salva esse tweet 📌",
        "Marca quem precisa ver isso",
        "Conta sua experiência 👇",
        "Qual sua visão sobre isso?",
        "Você já passou por isso?",
    ]
    
    # Emojis estratégicos (aumentam CTR)
    EMOJIS = {
        "alert": ["🚨", "⚠️", "🔥", "💥", "❗"],
        "positive": ["✅", "💪", "🚀", "⭐", "💡", "🎯"],
        "thinking": ["🤔", "💭", "🧠", "👀"],
        "money": ["💰", "💵", "📈", "💎"],
        "tech": ["🤖", "💻", "📱", "⚡"],
    }
    
    def __init__(self, openai_api_key: str = None, anthropic_api_key: str = None):
        self.openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.content_dir = Path(__file__).parent.parent.parent / "content"
        self.content_dir.mkdir(exist_ok=True)
    
    def generate_post(
        self,
        topic: str,
        style: str = "informativo",
        include_hook: bool = True,
        include_cta: bool = True,
        max_length: int = 280,
        use_ai: bool = True
    ) -> str:
        """
        Gera um post otimizado para o algoritmo.
        
        Args:
            topic: Assunto do post
            style: Estilo (informativo, provocativo, humor, inspiracional)
            include_hook: Incluir hook no início
            include_cta: Incluir CTA no final
            max_length: Tamanho máximo (280 para tweet normal)
            use_ai: Usar IA para gerar conteúdo
        
        Returns:
            Post formatado e otimizado
        """
        if use_ai and (self.openai_key or self.anthropic_key):
            return self._generate_with_ai(topic, style, include_hook, include_cta, max_length)
        else:
            return self._generate_template(topic, style, include_hook, include_cta, max_length)
    
    def _generate_with_ai(
        self,
        topic: str,
        style: str,
        include_hook: bool,
        include_cta: bool,
        max_length: int
    ) -> str:
        """Gera conteúdo usando LLM"""
        
        prompt = f"""Crie um tweet viral sobre: {topic}

Estilo: {style}
{'Comece com um hook forte que prenda atenção.' if include_hook else ''}
{'Termine com um CTA que incentive comentários.' if include_cta else ''}

Regras:
- Máximo {max_length} caracteres
- Use 1-2 emojis estrategicamente
- Seja direto e impactante
- Evite hashtags (algoritmo do X não prioriza mais)
- Foque em gerar engajamento (replies, likes, reposts)

Retorne APENAS o tweet, sem explicações."""

        try:
            if self.anthropic_key:
                return self._call_anthropic(prompt)
            elif self.openai_key:
                return self._call_openai(prompt)
        except Exception as e:
            logger.error(f"Erro na geração com IA: {e}")
        
        return self._generate_template(topic, style, include_hook, include_cta, max_length)
    
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
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.8
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    
    def _generate_template(
        self,
        topic: str,
        style: str,
        include_hook: bool,
        include_cta: bool,
        max_length: int
    ) -> str:
        """Gera conteúdo usando templates"""
        parts = []
        
        if include_hook:
            parts.append(random.choice(self.HOOKS))
        
        # Corpo baseado no estilo
        body = self._get_body_template(topic, style)
        parts.append(body)
        
        if include_cta:
            parts.append(random.choice(self.CTAS))
        
        result = "\n\n".join(parts)
        
        # Truncar se necessário
        if len(result) > max_length:
            result = result[:max_length-3] + "..."
        
        return result
    
    def _get_body_template(self, topic: str, style: str) -> str:
        """Retorna template de corpo baseado no estilo"""
        templates = {
            "informativo": [
                f"Sobre {topic}:\n\nA maioria das pessoas não sabe disso, mas é fundamental entender.",
                f"{topic} - o que você precisa saber:\n\n1. É mais simples do que parece\n2. Os resultados vêm com consistência",
            ],
            "provocativo": [
                f"Vou ser direto: {topic} é uma mentira que te contaram.\n\nA realidade é bem diferente.",
                f"Chega de {topic}.\n\nTá na hora de encarar a verdade.",
            ],
            "humor": [
                f"Eu tentando entender {topic}:\n\n🤡 <- eu\n\nMas pelo menos é divertido.",
                f"{topic} be like:\n\n- Promete muito\n- Entrega pouco\n- Todo mundo finge que funciona",
            ],
            "inspiracional": [
                f"{topic} mudou minha vida.\n\nNão foi fácil, mas valeu cada segundo de dedicação.",
                f"Se eu consegui com {topic}, você também consegue.\n\nÉ só começar.",
            ]
        }
        
        style_templates = templates.get(style, templates["informativo"])
        return random.choice(style_templates)
    
    def generate_reply(
        self,
        original_post: str,
        author: str,
        tone: str = "agreeable",
        add_value: bool = True
    ) -> str:
        """
        Gera uma resposta inteligente para um post.
        
        Estratégia do algoritmo:
        - Replies que adicionam valor têm mais visibilidade
        - Concordar parcialmente gera mais discussão
        - Perguntas aumentam P(reply) do autor original
        
        Args:
            original_post: Texto do post original
            author: Username do autor
            tone: Tom da resposta (agreeable, contrarian, curious, supportive)
            add_value: Se deve adicionar informação extra
        """
        if self.openai_key or self.anthropic_key:
            return self._generate_reply_ai(original_post, author, tone, add_value)
        else:
            return self._generate_reply_template(original_post, author, tone)
    
    def _generate_reply_ai(
        self,
        original_post: str,
        author: str,
        tone: str,
        add_value: bool
    ) -> str:
        """Gera reply usando IA"""
        
        tone_instructions = {
            "agreeable": "Concorde e adicione uma perspectiva complementar",
            "contrarian": "Discorde educadamente com um ponto de vista diferente",
            "curious": "Faça uma pergunta inteligente sobre o tema",
            "supportive": "Apoie a ideia e compartilhe uma experiência relacionada"
        }
        
        prompt = f"""Crie uma resposta para este tweet de @{author}:

"{original_post}"

Instruções:
- Tom: {tone_instructions.get(tone, tone_instructions['agreeable'])}
- {'Adicione um fato ou insight extra que enriqueça a discussão' if add_value else 'Seja breve e direto'}
- Máximo 200 caracteres
- Não use hashtags
- Seja genuíno, evite parecer bot
- Pode mencionar @{author} se fizer sentido

Retorne APENAS a resposta, sem explicações."""

        try:
            if self.anthropic_key:
                return self._call_anthropic(prompt)
            elif self.openai_key:
                return self._call_openai(prompt)
        except Exception as e:
            logger.error(f"Erro ao gerar reply com IA: {e}")
        
        return self._generate_reply_template(original_post, author, tone)
    
    def _generate_reply_template(
        self,
        original_post: str,
        author: str,
        tone: str
    ) -> str:
        """Gera reply usando templates"""
        
        templates = {
            "agreeable": [
                "Exatamente isso! 👏",
                "Concordo 100%. Mais pessoas precisam entender isso.",
                f"@{author} falou tudo. Sem mais.",
                "Isso resume perfeitamente. 🎯",
            ],
            "contrarian": [
                "Interessante perspectiva, mas discordo em um ponto...",
                "Entendo o raciocínio, mas já pensou por outro ângulo?",
                "Respeito a visão, mas minha experiência foi diferente.",
            ],
            "curious": [
                "Interessante! Você poderia elaborar mais sobre isso?",
                "Faz sentido. Mas como isso funciona na prática?",
                "Boa reflexão. O que te levou a essa conclusão?",
            ],
            "supportive": [
                "Passei por algo parecido. Fico feliz que mais gente fale disso! 💪",
                "Precisamos de mais conteúdo assim. Valeu por compartilhar!",
                f"@{author} sempre trazendo conteúdo de qualidade. 🔥",
            ]
        }
        
        return random.choice(templates.get(tone, templates["agreeable"]))
    
    def generate_thread(
        self,
        topic: str,
        num_tweets: int = 5,
        style: str = "informativo"
    ) -> List[str]:
        """
        Gera uma thread completa.
        
        Threads têm alto P(dwell) e P(repost) quando bem feitas.
        """
        if self.openai_key or self.anthropic_key:
            return self._generate_thread_ai(topic, num_tweets, style)
        else:
            return self._generate_thread_template(topic, num_tweets)
    
    def _generate_thread_ai(
        self,
        topic: str,
        num_tweets: int,
        style: str
    ) -> List[str]:
        """Gera thread usando IA"""
        
        prompt = f"""Crie uma thread de {num_tweets} tweets sobre: {topic}

Estilo: {style}

Estrutura:
1. Tweet 1: Hook forte + promessa do que vem
2. Tweets 2-{num_tweets-1}: Conteúdo principal, um ponto por tweet
3. Tweet {num_tweets}: Resumo + CTA forte

Regras:
- Cada tweet máximo 280 caracteres
- Numere os tweets (1/, 2/, etc)
- Use emojis estrategicamente
- Termine com CTA para retweet/follow
- Cada tweet deve fazer sentido sozinho mas conectar com o próximo

Formato de resposta:
TWEET_1: [conteúdo]
TWEET_2: [conteúdo]
...etc"""

        try:
            if self.anthropic_key:
                response = self._call_anthropic(prompt)
            elif self.openai_key:
                response = self._call_openai(prompt)
            
            # Parse response
            tweets = []
            for line in response.split("\n"):
                if line.startswith("TWEET_"):
                    content = line.split(":", 1)[1].strip() if ":" in line else ""
                    if content:
                        tweets.append(content)
            
            return tweets if tweets else self._generate_thread_template(topic, num_tweets)
            
        except Exception as e:
            logger.error(f"Erro ao gerar thread com IA: {e}")
            return self._generate_thread_template(topic, num_tweets)
    
    def _generate_thread_template(self, topic: str, num_tweets: int) -> List[str]:
        """Gera thread usando templates"""
        tweets = [
            f"🧵 THREAD: Tudo sobre {topic}\n\nVou explicar de forma simples. Bora? 👇",
        ]
        
        for i in range(2, num_tweets):
            tweets.append(f"{i}/ Ponto importante sobre {topic}:\n\n[Desenvolver conteúdo aqui]")
        
        tweets.append(
            f"{num_tweets}/ Resumindo:\n\n{topic} é mais simples do que parece.\n\n"
            "Gostou? RT para ajudar mais pessoas! 🔄\n\n"
            "Me segue para mais conteúdo assim 👊"
        )
        
        return tweets
    
    def optimize_for_algorithm(self, text: str) -> str:
        """
        Otimiza um texto para o algoritmo do X.
        
        Ajustes baseados no que o algoritmo prioriza:
        - Remove hashtags excessivas (não ajudam mais)
        - Adiciona line breaks (aumenta dwell time)
        - Verifica comprimento ideal
        """
        # Remover hashtags (algoritmo do X não prioriza mais)
        text = re.sub(r'#\w+', '', text)
        
        # Limpar espaços múltiplos
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Adicionar quebras de linha para legibilidade
        if len(text) > 100 and '\n' not in text:
            # Quebrar em frases
            sentences = text.replace('. ', '.\n\n')
            text = sentences
        
        return text.strip()
