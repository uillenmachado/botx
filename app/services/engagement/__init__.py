"""
Engagement Engine - Encontra posts virais e oportunidades de engajamento
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import tweepy

logger = logging.getLogger(__name__)


class EngagementFinder:
    """
    Encontra posts com alto potencial de viralização para comentar.
    
    Estratégia baseada no algoritmo do X:
    - Posts recentes com crescimento rápido de engajamento
    - Contas com muitos seguidores
    - Trending topics
    - Posts de contas do mesmo nicho
    """
    
    def __init__(self, client: tweepy.Client):
        self.client = client
        
    def find_viral_posts(
        self,
        query: str,
        min_likes: int = 100,
        min_retweets: int = 20,
        max_age_hours: int = 6,
        limit: int = 20
    ) -> List[Dict]:
        """
        Encontra posts virais recentes para comentar.
        
        Args:
            query: Termo de busca (hashtag, palavra-chave, etc)
            min_likes: Mínimo de likes para considerar viral
            min_retweets: Mínimo de retweets
            max_age_hours: Idade máxima do post em horas
            limit: Número máximo de posts a retornar
        
        Returns:
            Lista de posts com potencial de engajamento
        """
        try:
            # Buscar tweets recentes
            tweets = self.client.search_recent_tweets(
                query=f"{query} -is:retweet -is:reply lang:pt",
                max_results=min(limit * 2, 100),  # Buscar mais para filtrar
                tweet_fields=[
                    "created_at",
                    "public_metrics",
                    "author_id",
                    "conversation_id"
                ],
                expansions=["author_id"],
                user_fields=["public_metrics", "username", "verified"]
            )
            
            if not tweets.data:
                return []
            
            # Criar mapa de usuários
            users = {u.id: u for u in (tweets.includes.get("users", []) or [])}
            
            # Filtrar e rankear posts
            viral_posts = []
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            for tweet in tweets.data:
                metrics = tweet.public_metrics
                author = users.get(tweet.author_id)
                
                # Filtrar por métricas mínimas
                if metrics["like_count"] < min_likes:
                    continue
                if metrics["retweet_count"] < min_retweets:
                    continue
                    
                # Filtrar por idade
                if tweet.created_at.replace(tzinfo=None) < cutoff_time:
                    continue
                
                # Calcular score de viralidade
                # Baseado no algoritmo do X: engajamento rápido = alta relevância
                age_hours = (datetime.utcnow() - tweet.created_at.replace(tzinfo=None)).total_seconds() / 3600
                velocity = (metrics["like_count"] + metrics["retweet_count"] * 2) / max(age_hours, 0.1)
                
                # Bonus para contas verificadas ou com muitos seguidores
                author_boost = 1.0
                if author:
                    if author.verified:
                        author_boost = 1.5
                    if author.public_metrics["followers_count"] > 100000:
                        author_boost *= 1.3
                
                viral_posts.append({
                    "id": tweet.id,
                    "text": tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text,
                    "author_id": tweet.author_id,
                    "author_username": author.username if author else None,
                    "author_followers": author.public_metrics["followers_count"] if author else 0,
                    "likes": metrics["like_count"],
                    "retweets": metrics["retweet_count"],
                    "replies": metrics["reply_count"],
                    "created_at": tweet.created_at.isoformat(),
                    "age_hours": round(age_hours, 1),
                    "velocity": round(velocity * author_boost, 2),
                    "conversation_id": tweet.conversation_id
                })
            
            # Ordenar por velocity (engajamento por hora)
            viral_posts.sort(key=lambda x: x["velocity"], reverse=True)
            
            return viral_posts[:limit]
            
        except Exception as e:
            logger.error(f"Erro ao buscar posts virais: {e}")
            return []
    
    def find_trending_topics(self, woeid: int = 23424768) -> List[Dict]:
        """
        Busca trending topics.
        
        Args:
            woeid: Where On Earth ID (23424768 = Brasil)
        
        Returns:
            Lista de trending topics
        """
        try:
            # Nota: Esta API requer acesso elevado
            # Por enquanto retornamos uma lista vazia
            # TODO: Implementar com scraping ou API alternativa
            logger.warning("Trending topics API requer acesso elevado")
            return []
        except Exception as e:
            logger.error(f"Erro ao buscar trending: {e}")
            return []
    
    def find_niche_accounts(
        self,
        niche_keywords: List[str],
        min_followers: int = 10000,
        max_followers: int = 1000000,
        limit: int = 50
    ) -> List[Dict]:
        """
        Encontra contas relevantes no nicho para engajar.
        
        Estratégia: Engajar com contas médias (10k-1M seguidores)
        pois têm boa visibilidade mas respondem mais.
        """
        try:
            accounts = []
            
            for keyword in niche_keywords[:3]:  # Limitar queries
                users = self.client.search_users(
                    query=keyword,
                    max_results=20,
                    user_fields=["public_metrics", "description", "verified"]
                )
                
                if not users.data:
                    continue
                
                for user in users.data:
                    followers = user.public_metrics["followers_count"]
                    
                    if followers < min_followers or followers > max_followers:
                        continue
                    
                    # Calcular engagement rate
                    tweets = user.public_metrics.get("tweet_count", 1)
                    engagement = (
                        user.public_metrics.get("listed_count", 0) * 10 +
                        followers
                    ) / max(tweets, 1)
                    
                    accounts.append({
                        "id": user.id,
                        "username": user.username,
                        "followers": followers,
                        "description": user.description[:100] if user.description else "",
                        "verified": user.verified,
                        "engagement_score": round(engagement, 2)
                    })
            
            # Remover duplicatas e ordenar
            seen = set()
            unique_accounts = []
            for acc in accounts:
                if acc["id"] not in seen:
                    seen.add(acc["id"])
                    unique_accounts.append(acc)
            
            unique_accounts.sort(key=lambda x: x["engagement_score"], reverse=True)
            return unique_accounts[:limit]
            
        except Exception as e:
            logger.error(f"Erro ao buscar contas do nicho: {e}")
            return []
    
    def get_post_for_reply(
        self,
        account_id: str,
        max_age_hours: int = 2
    ) -> Optional[Dict]:
        """
        Pega o post mais recente de uma conta para responder.
        
        Estratégia: Responder posts recentes de contas relevantes
        aumenta chance de aparecer no feed dos seguidores delas.
        """
        try:
            tweets = self.client.get_users_tweets(
                id=account_id,
                max_results=5,
                tweet_fields=["created_at", "public_metrics"],
                exclude=["retweets", "replies"]
            )
            
            if not tweets.data:
                return None
            
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            for tweet in tweets.data:
                if tweet.created_at.replace(tzinfo=None) > cutoff:
                    return {
                        "id": tweet.id,
                        "text": tweet.text,
                        "metrics": tweet.public_metrics,
                        "created_at": tweet.created_at.isoformat()
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar post para reply: {e}")
            return None
