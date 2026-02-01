#!/usr/bin/env python3
"""
CACO FAKESSEN - Daemon 24/7 de Monetização

Funcionalidades:
- Posta conteúdo original nos horários certos
- Encontra posts virais e comenta
- Curte posts relevantes  
- Segue contas estratégicas
- Monitora trending topics
- Roda 24/7 com rate limiting inteligente

Uso:
    python caco_daemon.py
    
    # Com nohup (background):
    nohup python caco_daemon.py > caco.log 2>&1 &
"""
import os
import sys
import time
import random
import signal
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import tweepy

# Configurar logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"caco_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger('caco_daemon')

# Flag para shutdown graceful
running = True


def signal_handler(signum, frame):
    global running
    logger.info(f"🛑 Sinal {signum} recebido. Encerrando graciosamente...")
    running = False


class CacoDaemon:
    """
    Daemon principal do Caco Fakessen.
    
    Gerencia todas as ações automáticas para maximizar monetização.
    """
    
    def __init__(self):
        # Configurar cliente Twitter
        self.client = tweepy.Client(
            bearer_token=os.getenv("BEARER_TOKEN"),
            consumer_key=os.getenv("API_KEY"),
            consumer_secret=os.getenv("API_KEY_SECRET"),
            access_token=os.getenv("ACCESS_TOKEN"),
            access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
            wait_on_rate_limit=True
        )
        
        # Carregar componentes
        from app.services.content import ContentEngine
        from app.persona import PERSONA
        from app.persona.strategy_config import STRATEGY_CONFIG, get_current_content_type
        
        self.content = ContentEngine()
        self.persona = PERSONA
        self.strategy = STRATEGY_CONFIG
        self.get_content_type = get_current_content_type
        
        # Estado persistente
        self.state_file = Path(__file__).parent / "data" / "caco_state.json"
        self.state_file.parent.mkdir(exist_ok=True)
        self._load_state()
        
        # Rate limiting (ações por hora)
        self.limits = {
            "posts": {"max": 3, "count": 0, "reset": None},
            "likes": {"max": 50, "count": 0, "reset": None},
            "replies": {"max": 20, "count": 0, "reset": None},
            "follows": {"max": 10, "count": 0, "reset": None},
        }
        
        # Obter info da conta
        me = self.client.get_me()
        self.user_id = me.data.id
        self.username = me.data.username
        
        logger.info(f"🎭 Caco Daemon iniciado como @{self.username}")
    
    def _load_state(self):
        """Carrega estado do arquivo"""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    self.state = json.load(f)
            else:
                self.state = {
                    "posts_today": 0,
                    "likes_today": 0,
                    "replies_today": 0,
                    "follows_today": 0,
                    "last_post": None,
                    "last_like": None,
                    "last_reply": None,
                    "liked_tweets": [],
                    "replied_tweets": [],
                    "date": datetime.now().strftime("%Y-%m-%d"),
                }
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
            self.state = {}
    
    def _save_state(self):
        """Salva estado no arquivo"""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
    
    def _reset_daily_counters(self):
        """Reseta contadores diários"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("date") != today:
            logger.info("📅 Novo dia - resetando contadores")
            self.state = {
                "posts_today": 0,
                "likes_today": 0,
                "replies_today": 0,
                "follows_today": 0,
                "last_post": None,
                "last_like": None,
                "last_reply": None,
                "liked_tweets": [],
                "replied_tweets": [],
                "date": today,
            }
            self._save_state()
    
    def _check_rate_limit(self, action: str) -> bool:
        """Verifica se pode executar ação"""
        now = datetime.now()
        limit = self.limits.get(action)
        
        if not limit:
            return True
        
        # Reset horário
        if limit["reset"] is None or now >= limit["reset"]:
            limit["count"] = 0
            limit["reset"] = now + timedelta(hours=1)
        
        return limit["count"] < limit["max"]
    
    def _record_action(self, action: str):
        """Registra ação executada"""
        self.limits[action]["count"] += 1
        self.state[f"{action}_today"] = self.state.get(f"{action}_today", 0) + 1
        self.state[f"last_{action[:-1] if action.endswith('s') else action}"] = datetime.now().isoformat()
        self._save_state()
    
    def get_hour(self) -> int:
        """Retorna hora atual em UTC-3 (Brasil)"""
        return (datetime.utcnow().hour - 3) % 24
    
    def should_post(self) -> tuple:
        """Verifica se deve postar agora"""
        self._reset_daily_counters()
        
        hour = self.get_hour()
        daily_limit = self.strategy["daily_mix"]["posts_originais"]
        
        # Verificar limite diário
        if self.state["posts_today"] >= daily_limit:
            return False, "Limite diário atingido"
        
        # Verificar rate limit horário
        if not self._check_rate_limit("posts"):
            return False, "Rate limit horário"
        
        # Verificar intervalo mínimo (2 horas entre posts)
        if self.state["last_post"]:
            last = datetime.fromisoformat(self.state["last_post"])
            if datetime.now() - last < timedelta(hours=2):
                return False, "Aguardando intervalo entre posts"
        
        # Verificar horário de pico
        for periodo, config in self.strategy["horarios_pico"].items():
            if config["inicio"] <= hour < config["fim"]:
                if config["score"] >= 0.7:
                    return True, f"Horário de pico: {periodo}"
        
        return False, "Fora do horário de pico"
    
    def should_engage(self) -> bool:
        """Verifica se deve engajar (like/reply)"""
        hour = self.get_hour()
        
        # Evitar horário morto (2-6h)
        if 2 <= hour < 6:
            return False
        
        return True
    
    def post_content(self) -> Dict:
        """Posta conteúdo original"""
        try:
            hour = self.get_hour()
            content_types = self.get_content_type(hour)
            
            # Escolher pilar baseado no horário
            pilar_map = {
                "humor_elitista": "humor_elitista",
                "produtividade": "produtividade",
                "financas": "financas",
                "tech_ia": "tech_ia",
                "noticias": "politica_news",
                "comparacoes": "humor_elitista",
                "reflexoes": "produtividade",
            }
            
            pilar = None
            for ct in content_types:
                if ct in pilar_map:
                    pilar = pilar_map[ct]
                    break
            
            if not pilar:
                pilar = random.choice(["humor_elitista", "tech_ia", "financas"])
            
            # Gerar conteúdo
            content = self.content.generate_post(pilar=pilar, use_ai=False)
            
            # Postar
            response = self.client.create_tweet(text=content)
            tweet_id = response.data["id"]
            
            self._record_action("posts")
            
            logger.info(f"📝 POST #{self.state['posts_today']}: {content[:50]}...")
            logger.info(f"   🔗 https://twitter.com/{self.username}/status/{tweet_id}")
            
            return {
                "success": True,
                "tweet_id": tweet_id,
                "content": content,
                "pilar": pilar
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao postar: {e}")
            return {"success": False, "error": str(e)}
    
    def find_viral_posts(self, limit: int = 10) -> List[Dict]:
        """Encontra posts virais para engajar"""
        try:
            # Queries variadas para encontrar conteúdo
            queries = [
                "Brasil -is:retweet lang:pt",
                "IA OR inteligência artificial -is:retweet lang:pt",
                "investimento OR bolsa -is:retweet lang:pt",
                "tecnologia OR startup -is:retweet lang:pt",
                "Lula OR governo -is:retweet lang:pt",
                "São Paulo OR Rio -is:retweet lang:pt",
            ]
            
            query = random.choice(queries)
            
            tweets = self.client.search_recent_tweets(
                query=query,
                max_results=min(limit * 2, 50),
                tweet_fields=["created_at", "public_metrics", "author_id"],
                expansions=["author_id"],
                user_fields=["public_metrics", "username"]
            )
            
            if not tweets.data:
                return []
            
            users = {u.id: u for u in (tweets.includes.get("users", []) or [])}
            
            viral = []
            for tweet in tweets.data:
                # Pular se já interagiu
                if str(tweet.id) in self.state.get("liked_tweets", []):
                    continue
                if str(tweet.id) in self.state.get("replied_tweets", []):
                    continue
                
                metrics = tweet.public_metrics
                author = users.get(tweet.author_id)
                
                # Filtrar por engajamento mínimo
                if metrics["like_count"] < 10:
                    continue
                
                viral.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "author": author.username if author else "unknown",
                    "author_followers": author.public_metrics["followers_count"] if author else 0,
                    "likes": metrics["like_count"],
                    "retweets": metrics["retweet_count"],
                    "replies": metrics["reply_count"],
                })
            
            # Ordenar por likes
            viral.sort(key=lambda x: x["likes"], reverse=True)
            return viral[:limit]
            
        except Exception as e:
            logger.error(f"Erro ao buscar virais: {e}")
            return []
    
    def like_tweet(self, tweet_id: str) -> bool:
        """Curte um tweet"""
        try:
            if not self._check_rate_limit("likes"):
                return False
            
            self.client.like(tweet_id)
            
            # Registrar
            self._record_action("likes")
            if "liked_tweets" not in self.state:
                self.state["liked_tweets"] = []
            self.state["liked_tweets"].append(str(tweet_id))
            # Manter só últimos 500
            self.state["liked_tweets"] = self.state["liked_tweets"][-500:]
            self._save_state()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao curtir: {e}")
            return False
    
    def reply_to_tweet(self, tweet_id: str, original_text: str, author: str) -> Dict:
        """Responde a um tweet"""
        try:
            if not self._check_rate_limit("replies"):
                return {"success": False, "error": "Rate limit"}
            
            # Determinar sentimento/tipo
            text_lower = original_text.lower()
            
            if any(kw in text_lower for kw in ["lula", "pt", "esquerda", "governo", "socialismo"]):
                sentiment = "left"
            elif any(kw in text_lower for kw in ["ia", "chatgpt", "tech", "programação"]):
                sentiment = "tech"
            elif any(kw in text_lower for kw in ["dólar", "investimento", "bolsa", "mercado"]):
                sentiment = "economy"
            else:
                sentiment = "neutral"
            
            # Gerar reply
            reply_text = self.content.generate_reply(
                original_post=original_text,
                author=author,
                post_sentiment=sentiment,
                use_ai=False
            )
            
            # Postar reply
            response = self.client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=tweet_id
            )
            
            # Registrar
            self._record_action("replies")
            if "replied_tweets" not in self.state:
                self.state["replied_tweets"] = []
            self.state["replied_tweets"].append(str(tweet_id))
            self.state["replied_tweets"] = self.state["replied_tweets"][-500:]
            self._save_state()
            
            logger.info(f"💬 REPLY para @{author}: {reply_text[:50]}...")
            
            return {
                "success": True,
                "reply_id": response.data["id"],
                "content": reply_text
            }
            
        except Exception as e:
            logger.error(f"Erro ao responder: {e}")
            return {"success": False, "error": str(e)}
    
    def engagement_cycle(self):
        """Ciclo de engajamento: encontra posts, curte e comenta"""
        if not self.should_engage():
            return
        
        logger.info("🔍 Buscando posts para engajar...")
        
        viral_posts = self.find_viral_posts(limit=15)
        
        if not viral_posts:
            logger.info("   Nenhum post encontrado")
            return
        
        logger.info(f"   Encontrados {len(viral_posts)} posts")
        
        likes_done = 0
        replies_done = 0
        
        for post in viral_posts:
            # Delay entre ações (parecer humano)
            time.sleep(random.uniform(3, 8))
            
            # Like
            if self._check_rate_limit("likes") and likes_done < 5:
                if self.like_tweet(post["id"]):
                    logger.info(f"   ❤️ Curtiu: @{post['author']} ({post['likes']} likes)")
                    likes_done += 1
            
            # Reply (menos frequente)
            if self._check_rate_limit("replies") and replies_done < 3:
                # Só responde posts com likes razoáveis (visibilidade)
                if post["likes"] >= 50:
                    result = self.reply_to_tweet(post["id"], post["text"], post["author"])
                    if result["success"]:
                        replies_done += 1
                        time.sleep(random.uniform(10, 20))  # Delay maior após reply
        
        logger.info(f"   ✅ Engajamento: {likes_done} likes, {replies_done} replies")
    
    def run(self):
        """Loop principal do daemon"""
        global running
        
        logger.info("=" * 50)
        logger.info("🎭 CACO FAKESSEN - DAEMON DE MONETIZAÇÃO")
        logger.info("=" * 50)
        logger.info(f"📍 Conta: @{self.username}")
        logger.info(f"⏰ Horário atual (BR): {self.get_hour()}h")
        logger.info("=" * 50)
        
        cycle_count = 0
        
        while running:
            try:
                cycle_count += 1
                hour = self.get_hour()
                
                logger.info(f"\n🔄 Ciclo #{cycle_count} - {datetime.now().strftime('%H:%M:%S')} (BR: {hour}h)")
                
                # 1. Verificar se deve postar
                should_post, reason = self.should_post()
                if should_post:
                    result = self.post_content()
                    if result["success"]:
                        logger.info(f"   ✅ Post criado com sucesso")
                else:
                    logger.info(f"   ⏳ Não postou: {reason}")
                
                # 2. Ciclo de engajamento
                self.engagement_cycle()
                
                # 3. Status
                logger.info(f"   📊 Hoje: {self.state['posts_today']} posts, "
                           f"{self.state['likes_today']} likes, "
                           f"{self.state['replies_today']} replies")
                
                # Intervalo entre ciclos (5-10 min)
                sleep_time = random.uniform(300, 600)
                logger.info(f"   💤 Próximo ciclo em {int(sleep_time/60)} minutos")
                
                # Sleep em intervalos para permitir shutdown graceful
                for _ in range(int(sleep_time)):
                    if not running:
                        break
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Erro no ciclo: {e}")
                time.sleep(60)
        
        logger.info("🛑 Daemon encerrado")
        self._save_state()


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    daemon = CacoDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
