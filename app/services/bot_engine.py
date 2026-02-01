"""
Bot Engine - Motor principal de automação para monetização no X
"""
import os
import time
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional
import tweepy

from .twitter_service import TwitterService
from .engagement import EngagementFinder
from .content import ContentEngine
from .strategy import StrategyEngine
from .analytics import AnalyticsEngine

logger = logging.getLogger(__name__)


class BotEngine:
    """
    Motor principal do bot de monetização.
    
    Integra todos os componentes:
    - EngagementFinder: Encontra posts para engajar
    - ContentEngine: Gera conteúdo otimizado
    - StrategyEngine: Define timing e mix
    - AnalyticsEngine: Monitora performance
    - TwitterService: Executa ações no X
    """
    
    def __init__(
        self,
        niche: str = "tech",
        openai_key: str = None,
        anthropic_key: str = None
    ):
        """
        Inicializa o bot engine.
        
        Args:
            niche: Nicho de atuação (tech, finance, humor, news, lifestyle)
            openai_key: API key da OpenAI (opcional)
            anthropic_key: API key da Anthropic (opcional)
        """
        # Configurar cliente Twitter
        self.client = tweepy.Client(
            bearer_token=os.getenv("BEARER_TOKEN"),
            consumer_key=os.getenv("API_KEY"),
            consumer_secret=os.getenv("API_KEY_SECRET"),
            access_token=os.getenv("ACCESS_TOKEN"),
            access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
            wait_on_rate_limit=True
        )
        
        # Inicializar componentes
        self.engagement = EngagementFinder(self.client)
        self.content = ContentEngine(openai_key, anthropic_key)
        self.strategy = StrategyEngine(niche=niche)
        self.analytics = AnalyticsEngine(self.client)
        
        self.niche = niche
        
        logger.info(f"BotEngine inicializado para nicho: {niche}")
    
    def run_cycle(self) -> Dict:
        """
        Executa um ciclo completo de automação.
        
        Returns:
            Resultado do ciclo
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "actions": [],
            "errors": []
        }
        
        try:
            # 1. Verificar se deve postar
            should_post, reason = self.strategy.should_post_now()
            
            if should_post:
                content_type = self.strategy.get_content_type()
                
                if content_type == "thread":
                    action_result = self._post_thread()
                elif content_type == "post":
                    action_result = self._post_original()
                elif content_type == "quote":
                    action_result = self._post_quote()
                else:
                    action_result = {"skipped": True, "reason": "Tipo não implementado"}
                
                result["actions"].append({
                    "type": content_type,
                    "result": action_result
                })
            
            # 2. Fazer replies estratégicos
            should_reply, reply_reason = self.strategy.should_reply_now()
            
            if should_reply:
                reply_result = self._do_strategic_reply()
                result["actions"].append({
                    "type": "reply",
                    "result": reply_result
                })
            
            # 3. Salvar snapshot de analytics (1x por dia)
            hour = self.strategy.get_current_hour_local()
            if hour == 23:  # Às 23h
                self.analytics.save_daily_snapshot()
            
        except Exception as e:
            logger.error(f"Erro no ciclo: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def _post_original(self) -> Dict:
        """Posta conteúdo original"""
        try:
            targets = self.strategy.get_engagement_targets()
            
            # Gerar conteúdo
            topic = random.choice(targets["keywords"])
            content = self.content.generate_post(
                topic=topic,
                style=targets["preferred_tone"],
                include_hook=True,
                include_cta=True
            )
            
            # Postar
            response = self.client.create_tweet(text=content)
            
            # Registrar ação
            self.strategy.record_action("post")
            
            logger.info(f"Post criado: {response.data['id']}")
            
            return {
                "success": True,
                "tweet_id": response.data["id"],
                "content": content[:50] + "..."
            }
            
        except Exception as e:
            logger.error(f"Erro ao postar: {e}")
            return {"success": False, "error": str(e)}
    
    def _post_thread(self) -> Dict:
        """Posta uma thread"""
        try:
            targets = self.strategy.get_engagement_targets()
            topic = random.choice(targets["keywords"])
            
            # Gerar thread
            tweets = self.content.generate_thread(
                topic=topic,
                num_tweets=5,
                style=targets["preferred_tone"]
            )
            
            if not tweets:
                return {"success": False, "error": "Falha ao gerar thread"}
            
            # Postar primeiro tweet
            first_response = self.client.create_tweet(text=tweets[0])
            thread_ids = [first_response.data["id"]]
            
            # Postar resto da thread como replies
            previous_id = first_response.data["id"]
            for tweet_text in tweets[1:]:
                time.sleep(random.uniform(2, 5))  # Delay humano
                response = self.client.create_tweet(
                    text=tweet_text,
                    in_reply_to_tweet_id=previous_id
                )
                thread_ids.append(response.data["id"])
                previous_id = response.data["id"]
            
            # Registrar ação
            self.strategy.record_action("thread")
            
            logger.info(f"Thread criada: {len(thread_ids)} tweets")
            
            return {
                "success": True,
                "thread_ids": thread_ids,
                "num_tweets": len(thread_ids)
            }
            
        except Exception as e:
            logger.error(f"Erro ao postar thread: {e}")
            return {"success": False, "error": str(e)}
    
    def _post_quote(self) -> Dict:
        """Posta quote tweet de um post viral"""
        try:
            targets = self.strategy.get_engagement_targets()
            
            # Encontrar post para quotar
            viral_posts = self.engagement.find_viral_posts(
                query=" OR ".join(targets["keywords"][:2]),
                min_likes=targets["min_likes_viral"],
                max_age_hours=targets["max_age_hours"],
                limit=10
            )
            
            if not viral_posts:
                return {"success": False, "error": "Nenhum post viral encontrado"}
            
            # Escolher um post
            post = random.choice(viral_posts[:5])
            
            # Gerar comentário para quote
            quote_text = self.content.generate_reply(
                original_post=post["text"],
                author=post["author_username"],
                tone="agreeable",
                add_value=True
            )
            
            # Postar quote tweet
            response = self.client.create_tweet(
                text=quote_text,
                quote_tweet_id=post["id"]
            )
            
            # Registrar ação
            self.strategy.record_action("quote")
            
            logger.info(f"Quote criado: {response.data['id']}")
            
            return {
                "success": True,
                "tweet_id": response.data["id"],
                "quoted_post": post["id"],
                "content": quote_text[:50] + "..."
            }
            
        except Exception as e:
            logger.error(f"Erro ao fazer quote: {e}")
            return {"success": False, "error": str(e)}
    
    def _do_strategic_reply(self) -> Dict:
        """Faz reply estratégico em post viral"""
        try:
            targets = self.strategy.get_engagement_targets()
            
            # Encontrar posts virais para responder
            viral_posts = self.engagement.find_viral_posts(
                query=" OR ".join(targets["keywords"][:2]),
                min_likes=50,  # Threshold menor para replies
                min_retweets=10,
                max_age_hours=2,  # Posts bem recentes
                limit=20
            )
            
            if not viral_posts:
                return {"success": False, "error": "Nenhum post para reply"}
            
            # Escolher post (priorizar os mais recentes com boa velocity)
            post = viral_posts[0]  # Já ordenado por velocity
            
            # Gerar reply
            reply_text = self.content.generate_reply(
                original_post=post["text"],
                author=post["author_username"],
                tone=random.choice(["agreeable", "curious", "supportive"]),
                add_value=True
            )
            
            # Postar reply
            response = self.client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=post["id"]
            )
            
            # Registrar ação
            self.strategy.record_action("reply")
            
            logger.info(f"Reply criado em {post['id']}: {response.data['id']}")
            
            return {
                "success": True,
                "reply_id": response.data["id"],
                "original_post": post["id"],
                "original_author": post["author_username"],
                "content": reply_text[:50] + "..."
            }
            
        except Exception as e:
            logger.error(f"Erro ao fazer reply: {e}")
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> Dict:
        """Retorna status completo do bot"""
        try:
            account = self.analytics.get_account_stats()
            monetization = self.analytics.calculate_monetization_progress()
            content_analysis = self.analytics.analyze_best_performing_content(days=7)
            
            return {
                "account": account,
                "monetization": monetization,
                "content_analysis": content_analysis,
                "strategy": {
                    "niche": self.niche,
                    "daily_mix": self.strategy.DAILY_MIX,
                    "state": self.strategy.state,
                },
                "next_post_time": self.strategy.get_next_post_time().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter status: {e}")
            return {"error": str(e)}
    
    def run_once(self, action_type: str, **kwargs) -> Dict:
        """
        Executa uma ação específica uma vez.
        
        Args:
            action_type: "post", "reply", "thread", "quote", "analyze"
            **kwargs: Argumentos específicos da ação
        """
        if action_type == "post":
            topic = kwargs.get("topic", random.choice(self.strategy.config["keywords"]))
            content = self.content.generate_post(
                topic=topic,
                style=kwargs.get("style", self.strategy.config["tone"]),
                include_hook=kwargs.get("include_hook", True),
                include_cta=kwargs.get("include_cta", True)
            )
            
            if kwargs.get("dry_run", False):
                return {"dry_run": True, "content": content}
            
            response = self.client.create_tweet(text=content)
            self.strategy.record_action("post")
            return {"success": True, "tweet_id": response.data["id"], "content": content}
        
        elif action_type == "reply":
            post_id = kwargs.get("post_id")
            if not post_id:
                return self._do_strategic_reply()
            
            # Reply para post específico
            tweet = self.client.get_tweet(post_id, tweet_fields=["author_id"])
            author = self.client.get_user(id=tweet.data.author_id)
            
            reply_text = self.content.generate_reply(
                original_post=tweet.data.text,
                author=author.data.username,
                tone=kwargs.get("tone", "agreeable"),
                add_value=True
            )
            
            if kwargs.get("dry_run", False):
                return {"dry_run": True, "content": reply_text}
            
            response = self.client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=post_id
            )
            self.strategy.record_action("reply")
            return {"success": True, "reply_id": response.data["id"], "content": reply_text}
        
        elif action_type == "thread":
            return self._post_thread()
        
        elif action_type == "quote":
            return self._post_quote()
        
        elif action_type == "analyze":
            return self.get_status()
        
        elif action_type == "find_viral":
            query = kwargs.get("query", " OR ".join(self.strategy.config["keywords"][:2]))
            return {
                "viral_posts": self.engagement.find_viral_posts(
                    query=query,
                    min_likes=kwargs.get("min_likes", 100),
                    max_age_hours=kwargs.get("max_age_hours", 6),
                    limit=kwargs.get("limit", 20)
                )
            }
        
        else:
            return {"error": f"Ação desconhecida: {action_type}"}


def create_bot(niche: str = "tech") -> BotEngine:
    """Factory function para criar instância do bot"""
    return BotEngine(
        niche=niche,
        openai_key=os.getenv("OPENAI_API_KEY"),
        anthropic_key=os.getenv("ANTHROPIC_API_KEY")
    )
