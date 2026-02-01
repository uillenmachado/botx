"""
Analytics Engine - Monitora performance e otimiza estratégia
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import tweepy

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Motor de analytics para monitorar e otimizar performance.
    
    Métricas chave para monetização:
    - Impressões (principal métrica do X Premium)
    - Engagement rate
    - Crescimento de seguidores
    - Performance por tipo de conteúdo
    """
    
    def __init__(self, client: tweepy.Client, user_id: str = None):
        self.client = client
        self.user_id = user_id
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "analytics"
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_user_id(self) -> str:
        """Obtém ID do usuário se não configurado"""
        if not self.user_id:
            me = self.client.get_me()
            self.user_id = me.data.id
        return self.user_id
    
    def get_account_stats(self) -> Dict:
        """
        Obtém estatísticas gerais da conta.
        """
        try:
            me = self.client.get_me(
                user_fields=[
                    "public_metrics",
                    "created_at",
                    "description",
                    "verified"
                ]
            )
            
            metrics = me.data.public_metrics
            created = me.data.created_at
            account_age = (datetime.utcnow() - created.replace(tzinfo=None)).days
            
            return {
                "user_id": me.data.id,
                "username": me.data.username,
                "followers": metrics["followers_count"],
                "following": metrics["following_count"],
                "tweets": metrics["tweet_count"],
                "listed": metrics.get("listed_count", 0),
                "verified": me.data.verified,
                "account_age_days": account_age,
                "bio": me.data.description,
                "created_at": created.isoformat(),
                # Requisitos de monetização
                "monetization_eligible": {
                    "followers_500": metrics["followers_count"] >= 500,
                    "account_90_days": account_age >= 90,
                }
            }
        except Exception as e:
            logger.error(f"Erro ao obter stats da conta: {e}")
            return {}
    
    def get_recent_tweets_performance(
        self,
        days: int = 7,
        max_tweets: int = 100
    ) -> Dict:
        """
        Analisa performance dos tweets recentes.
        
        Returns:
            Estatísticas agregadas e por tweet
        """
        try:
            user_id = self._get_user_id()
            
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=min(max_tweets, 100),
                tweet_fields=[
                    "created_at",
                    "public_metrics",
                    "possibly_sensitive",
                    "reply_settings"
                ],
                start_time=(datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
            )
            
            if not tweets.data:
                return {"tweets": [], "summary": {}}
            
            tweet_stats = []
            total_impressions = 0
            total_likes = 0
            total_retweets = 0
            total_replies = 0
            total_quotes = 0
            
            for tweet in tweets.data:
                metrics = tweet.public_metrics
                impressions = metrics.get("impression_count", 0)
                likes = metrics["like_count"]
                retweets = metrics["retweet_count"]
                replies = metrics["reply_count"]
                quotes = metrics.get("quote_count", 0)
                
                # Calcular engagement rate
                engagement = likes + retweets + replies + quotes
                eng_rate = (engagement / impressions * 100) if impressions > 0 else 0
                
                tweet_stats.append({
                    "id": tweet.id,
                    "text": tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text,
                    "created_at": tweet.created_at.isoformat(),
                    "impressions": impressions,
                    "likes": likes,
                    "retweets": retweets,
                    "replies": replies,
                    "quotes": quotes,
                    "engagement_rate": round(eng_rate, 2),
                    "is_reply": tweet.text.startswith("@"),
                    "is_thread": "/1" in tweet.text or "🧵" in tweet.text,
                })
                
                total_impressions += impressions
                total_likes += likes
                total_retweets += retweets
                total_replies += replies
                total_quotes += quotes
            
            # Calcular médias
            num_tweets = len(tweet_stats)
            total_engagement = total_likes + total_retweets + total_replies + total_quotes
            avg_eng_rate = (total_engagement / total_impressions * 100) if total_impressions > 0 else 0
            
            return {
                "tweets": tweet_stats,
                "summary": {
                    "period_days": days,
                    "total_tweets": num_tweets,
                    "total_impressions": total_impressions,
                    "total_likes": total_likes,
                    "total_retweets": total_retweets,
                    "total_replies": total_replies,
                    "total_quotes": total_quotes,
                    "total_engagement": total_engagement,
                    "avg_impressions": round(total_impressions / num_tweets) if num_tweets else 0,
                    "avg_likes": round(total_likes / num_tweets, 1) if num_tweets else 0,
                    "avg_engagement_rate": round(avg_eng_rate, 2),
                    "best_tweet": max(tweet_stats, key=lambda x: x["impressions"]) if tweet_stats else None,
                    "worst_tweet": min(tweet_stats, key=lambda x: x["impressions"]) if tweet_stats else None,
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao analisar tweets: {e}")
            return {"tweets": [], "summary": {}}
    
    def calculate_monetization_progress(self) -> Dict:
        """
        Calcula progresso para monetização.
        
        Requisitos X Premium:
        - 500 seguidores
        - 5M impressões em 3 meses
        - Conta com 3+ meses
        """
        try:
            account = self.get_account_stats()
            performance = self.get_recent_tweets_performance(days=30)
            
            followers = account.get("followers", 0)
            monthly_impressions = performance["summary"].get("total_impressions", 0)
            projected_3m_impressions = monthly_impressions * 3
            account_age = account.get("account_age_days", 0)
            
            # Calcular o que falta
            followers_needed = max(0, 500 - followers)
            impressions_needed = max(0, 5_000_000 - projected_3m_impressions)
            days_needed = max(0, 90 - account_age)
            
            # Progresso percentual
            followers_progress = min(100, (followers / 500) * 100)
            impressions_progress = min(100, (projected_3m_impressions / 5_000_000) * 100)
            age_progress = min(100, (account_age / 90) * 100)
            
            overall_progress = (followers_progress + impressions_progress + age_progress) / 3
            
            # Estimativa de quando vai atingir
            if performance["summary"].get("total_tweets", 0) > 0:
                avg_impressions_per_tweet = monthly_impressions / performance["summary"]["total_tweets"]
                tweets_needed = impressions_needed / avg_impressions_per_tweet if avg_impressions_per_tweet > 0 else float('inf')
            else:
                tweets_needed = float('inf')
            
            return {
                "eligible": followers >= 500 and projected_3m_impressions >= 5_000_000 and account_age >= 90,
                "progress": {
                    "overall": round(overall_progress, 1),
                    "followers": round(followers_progress, 1),
                    "impressions": round(impressions_progress, 1),
                    "account_age": round(age_progress, 1),
                },
                "current": {
                    "followers": followers,
                    "monthly_impressions": monthly_impressions,
                    "projected_3m_impressions": projected_3m_impressions,
                    "account_age_days": account_age,
                },
                "needed": {
                    "followers": followers_needed,
                    "impressions_3m": impressions_needed,
                    "days": days_needed,
                    "tweets_estimated": round(tweets_needed) if tweets_needed != float('inf') else "N/A",
                },
                "estimated_revenue": {
                    "current_monthly": round((monthly_impressions / 1000) * 1.5, 2),  # $1.50 CPM estimate
                    "at_eligibility": round((5_000_000 / 3 / 1000) * 1.5, 2),
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular progresso: {e}")
            return {}
    
    def analyze_best_performing_content(self, days: int = 30) -> Dict:
        """
        Analisa qual tipo de conteúdo performa melhor.
        """
        try:
            performance = self.get_recent_tweets_performance(days=days)
            tweets = performance.get("tweets", [])
            
            if not tweets:
                return {}
            
            # Classificar tweets
            posts = [t for t in tweets if not t["is_reply"] and not t["is_thread"]]
            replies = [t for t in tweets if t["is_reply"]]
            threads = [t for t in tweets if t["is_thread"]]
            
            def calc_avg(tweet_list, field):
                if not tweet_list:
                    return 0
                return sum(t[field] for t in tweet_list) / len(tweet_list)
            
            return {
                "posts": {
                    "count": len(posts),
                    "avg_impressions": round(calc_avg(posts, "impressions")),
                    "avg_engagement_rate": round(calc_avg(posts, "engagement_rate"), 2),
                    "total_impressions": sum(t["impressions"] for t in posts),
                },
                "replies": {
                    "count": len(replies),
                    "avg_impressions": round(calc_avg(replies, "impressions")),
                    "avg_engagement_rate": round(calc_avg(replies, "engagement_rate"), 2),
                    "total_impressions": sum(t["impressions"] for t in replies),
                },
                "threads": {
                    "count": len(threads),
                    "avg_impressions": round(calc_avg(threads, "impressions")),
                    "avg_engagement_rate": round(calc_avg(threads, "engagement_rate"), 2),
                    "total_impressions": sum(t["impressions"] for t in threads),
                },
                "recommendation": self._get_content_recommendation(posts, replies, threads)
            }
            
        except Exception as e:
            logger.error(f"Erro ao analisar conteúdo: {e}")
            return {}
    
    def _get_content_recommendation(
        self,
        posts: List[Dict],
        replies: List[Dict],
        threads: List[Dict]
    ) -> str:
        """Gera recomendação baseada na performance"""
        
        def avg_eng(lst):
            if not lst:
                return 0
            return sum(t["engagement_rate"] for t in lst) / len(lst)
        
        post_eng = avg_eng(posts)
        reply_eng = avg_eng(replies)
        thread_eng = avg_eng(threads)
        
        best = max(
            [("posts", post_eng), ("replies", reply_eng), ("threads", thread_eng)],
            key=lambda x: x[1]
        )
        
        recommendations = {
            "posts": "Posts originais estão performando bem. Continue criando conteúdo único.",
            "replies": "Replies estratégicos estão gerando bom engajamento. Foque em responder posts virais.",
            "threads": "Threads estão tendo boa performance. Crie mais conteúdo longo e aprofundado."
        }
        
        return recommendations.get(best[0], "Continue testando diferentes tipos de conteúdo.")
    
    def save_daily_snapshot(self):
        """
        Salva snapshot diário para tracking histórico.
        """
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            
            snapshot = {
                "date": today,
                "timestamp": datetime.now().isoformat(),
                "account": self.get_account_stats(),
                "performance_7d": self.get_recent_tweets_performance(days=7)["summary"],
                "monetization": self.calculate_monetization_progress(),
            }
            
            # Salvar snapshot
            snapshot_file = self.data_dir / f"snapshot_{today}.json"
            with open(snapshot_file, "w") as f:
                json.dump(snapshot, f, indent=2)
            
            logger.info(f"Snapshot salvo: {snapshot_file}")
            return snapshot
            
        except Exception as e:
            logger.error(f"Erro ao salvar snapshot: {e}")
            return {}
    
    def get_growth_trend(self, days: int = 30) -> Dict:
        """
        Analisa tendência de crescimento baseado em snapshots históricos.
        """
        try:
            snapshots = []
            
            for i in range(days):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                snapshot_file = self.data_dir / f"snapshot_{date}.json"
                
                if snapshot_file.exists():
                    with open(snapshot_file) as f:
                        snapshots.append(json.load(f))
            
            if len(snapshots) < 2:
                return {"error": "Dados insuficientes para análise de tendência"}
            
            # Ordenar por data
            snapshots.sort(key=lambda x: x["date"])
            
            first = snapshots[0]
            last = snapshots[-1]
            
            followers_growth = last["account"]["followers"] - first["account"]["followers"]
            
            return {
                "period_days": len(snapshots),
                "followers_growth": followers_growth,
                "followers_growth_rate": round((followers_growth / first["account"]["followers"]) * 100, 2) if first["account"]["followers"] > 0 else 0,
                "avg_daily_followers": round(followers_growth / len(snapshots), 1),
                "first_snapshot": first["date"],
                "last_snapshot": last["date"],
            }
            
        except Exception as e:
            logger.error(f"Erro ao analisar tendência: {e}")
            return {}
