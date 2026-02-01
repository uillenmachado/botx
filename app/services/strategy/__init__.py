"""
Strategy Engine - Define estratégias de posting baseadas no algoritmo do X
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import random

logger = logging.getLogger(__name__)


class StrategyEngine:
    """
    Motor de estratégia para maximizar alcance e monetização.
    
    Baseado no algoritmo do X:
    - Timing de posts (quando postar)
    - Mix de conteúdo (o quê postar)
    - Frequência (quanto postar)
    - Targeting (para quem)
    """
    
    # Horários de pico (UTC-3, Brasil) com scores de engajamento
    PEAK_HOURS = {
        0: {"score": 0.4, "type": "late_night"},
        1: {"score": 0.2, "type": "late_night"},
        2: {"score": 0.1, "type": "dead"},
        3: {"score": 0.1, "type": "dead"},
        4: {"score": 0.1, "type": "dead"},
        5: {"score": 0.2, "type": "early"},
        6: {"score": 0.4, "type": "early"},
        7: {"score": 0.7, "type": "morning"},
        8: {"score": 0.9, "type": "morning"},
        9: {"score": 0.8, "type": "morning"},
        10: {"score": 0.6, "type": "mid_morning"},
        11: {"score": 0.5, "type": "mid_morning"},
        12: {"score": 0.8, "type": "lunch"},
        13: {"score": 0.7, "type": "lunch"},
        14: {"score": 0.5, "type": "afternoon"},
        15: {"score": 0.4, "type": "afternoon"},
        16: {"score": 0.5, "type": "afternoon"},
        17: {"score": 0.6, "type": "late_afternoon"},
        18: {"score": 0.9, "type": "evening"},
        19: {"score": 1.0, "type": "evening"},  # PICO
        20: {"score": 1.0, "type": "evening"},  # PICO
        21: {"score": 0.9, "type": "night"},
        22: {"score": 0.8, "type": "night"},
        23: {"score": 0.6, "type": "late_night"},
    }
    
    # Mix de conteúdo ideal por dia
    DAILY_MIX = {
        "posts": 5,           # Posts originais
        "replies": 25,        # Respostas estratégicas
        "quote_tweets": 3,    # Quote tweets
        "threads": 1,         # Uma thread por dia
    }
    
    # Configurações de nicho
    NICHE_CONFIG = {
        "tech": {
            "keywords": ["IA", "inteligência artificial", "programação", "startup", "tech"],
            "best_hours": [8, 9, 12, 18, 19, 20, 21],
            "tone": "informativo",
            "hashtags": [],  # Algoritmo do X não prioriza hashtags
        },
        "finance": {
            "keywords": ["investimento", "bolsa", "ações", "finanças", "dinheiro"],
            "best_hours": [7, 8, 9, 12, 17, 18],
            "tone": "provocativo",
            "hashtags": [],
        },
        "humor": {
            "keywords": ["meme", "humor", "piada", "zueira"],
            "best_hours": [12, 13, 19, 20, 21, 22, 23],
            "tone": "humor",
            "hashtags": [],
        },
        "news": {
            "keywords": ["notícia", "breaking", "urgente", "política"],
            "best_hours": [7, 8, 9, 12, 18, 19, 20],
            "tone": "informativo",
            "hashtags": [],
        },
        "lifestyle": {
            "keywords": ["produtividade", "hábitos", "mindset", "rotina"],
            "best_hours": [6, 7, 8, 19, 20, 21],
            "tone": "inspiracional",
            "hashtags": [],
        }
    }
    
    def __init__(self, niche: str = "tech", timezone_offset: int = -3):
        """
        Args:
            niche: Nicho de atuação
            timezone_offset: Offset do timezone em horas (Brasil = -3)
        """
        self.niche = niche
        self.tz_offset = timezone_offset
        self.config = self.NICHE_CONFIG.get(niche, self.NICHE_CONFIG["tech"])
        self.state_file = Path(__file__).parent.parent.parent / "data" / "strategy_state.json"
        self.state_file.parent.mkdir(exist_ok=True)
        self._load_state()
    
    def _load_state(self):
        """Carrega estado persistente"""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    self.state = json.load(f)
            else:
                self.state = {
                    "posts_today": 0,
                    "replies_today": 0,
                    "quotes_today": 0,
                    "threads_today": 0,
                    "last_post_time": None,
                    "last_reply_time": None,
                    "date": datetime.now().strftime("%Y-%m-%d")
                }
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
            self.state = {}
    
    def _save_state(self):
        """Salva estado persistente"""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
    
    def _reset_daily_state(self):
        """Reseta contadores diários"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("date") != today:
            self.state = {
                "posts_today": 0,
                "replies_today": 0,
                "quotes_today": 0,
                "threads_today": 0,
                "last_post_time": None,
                "last_reply_time": None,
                "date": today
            }
            self._save_state()
    
    def get_current_hour_local(self) -> int:
        """Retorna hora atual no timezone configurado"""
        utc_now = datetime.utcnow()
        local_hour = (utc_now.hour + self.tz_offset) % 24
        return local_hour
    
    def should_post_now(self) -> Tuple[bool, str]:
        """
        Verifica se é um bom momento para postar.
        
        Returns:
            (should_post, reason)
        """
        self._reset_daily_state()
        
        hour = self.get_current_hour_local()
        hour_data = self.PEAK_HOURS[hour]
        
        # Verificar se já atingiu limite diário
        if self.state["posts_today"] >= self.DAILY_MIX["posts"]:
            return False, "Limite diário de posts atingido"
        
        # Verificar intervalo mínimo entre posts (30 min)
        if self.state["last_post_time"]:
            last = datetime.fromisoformat(self.state["last_post_time"])
            if datetime.now() - last < timedelta(minutes=30):
                return False, "Aguarde 30 minutos entre posts"
        
        # Verificar se é horário de pico
        if hour_data["score"] < 0.5:
            return False, f"Horário de baixo engajamento ({hour_data['type']})"
        
        # Verificar se é horário ideal para o nicho
        if hour in self.config["best_hours"]:
            return True, f"Horário ideal para {self.niche} (score: {hour_data['score']})"
        
        if hour_data["score"] >= 0.7:
            return True, f"Horário de pico geral (score: {hour_data['score']})"
        
        return False, f"Horário mediano (score: {hour_data['score']})"
    
    def should_reply_now(self) -> Tuple[bool, str]:
        """
        Verifica se é um bom momento para fazer replies.
        
        Replies podem ser feitos com mais frequência que posts.
        """
        self._reset_daily_state()
        
        # Verificar limite diário
        if self.state["replies_today"] >= self.DAILY_MIX["replies"]:
            return False, "Limite diário de replies atingido"
        
        # Intervalo mínimo entre replies (5 min)
        if self.state["last_reply_time"]:
            last = datetime.fromisoformat(self.state["last_reply_time"])
            if datetime.now() - last < timedelta(minutes=5):
                return False, "Aguarde 5 minutos entre replies"
        
        return True, "OK para fazer reply"
    
    def get_next_post_time(self) -> datetime:
        """
        Calcula o próximo horário ideal para postar.
        
        Returns:
            Datetime do próximo horário de pico
        """
        now = datetime.utcnow()
        local_hour = self.get_current_hour_local()
        
        # Encontrar próximo horário com score >= 0.7
        for offset in range(1, 25):
            check_hour = (local_hour + offset) % 24
            if self.PEAK_HOURS[check_hour]["score"] >= 0.7:
                # Calcular datetime
                target_hour_utc = (check_hour - self.tz_offset) % 24
                
                next_post = now.replace(
                    hour=target_hour_utc,
                    minute=random.randint(0, 30),  # Aleatorizar minutos
                    second=0,
                    microsecond=0
                )
                
                if next_post <= now:
                    next_post += timedelta(days=1)
                
                return next_post
        
        # Fallback: próxima hora
        return now + timedelta(hours=1)
    
    def get_content_type(self) -> str:
        """
        Decide qual tipo de conteúdo criar agora.
        
        Baseado no mix ideal e no que já foi postado hoje.
        """
        self._reset_daily_state()
        
        # Prioridades baseadas no que falta
        if self.state["threads_today"] < self.DAILY_MIX["threads"]:
            hour = self.get_current_hour_local()
            # Threads funcionam melhor à noite (mais tempo para ler)
            if hour >= 19 or hour <= 8:
                return "thread"
        
        if self.state["quotes_today"] < self.DAILY_MIX["quote_tweets"]:
            if random.random() < 0.3:  # 30% chance
                return "quote"
        
        if self.state["posts_today"] < self.DAILY_MIX["posts"]:
            return "post"
        
        return "reply"  # Default: focar em replies
    
    def record_action(self, action_type: str):
        """
        Registra uma ação realizada.
        
        Args:
            action_type: "post", "reply", "quote", "thread"
        """
        self._reset_daily_state()
        
        now = datetime.now().isoformat()
        
        if action_type == "post":
            self.state["posts_today"] += 1
            self.state["last_post_time"] = now
        elif action_type == "reply":
            self.state["replies_today"] += 1
            self.state["last_reply_time"] = now
        elif action_type == "quote":
            self.state["quotes_today"] += 1
            self.state["last_post_time"] = now
        elif action_type == "thread":
            self.state["threads_today"] += 1
            self.state["last_post_time"] = now
        
        self._save_state()
    
    def get_daily_schedule(self) -> List[Dict]:
        """
        Gera schedule completo para o dia.
        
        Returns:
            Lista de horários com tipo de conteúdo
        """
        schedule = []
        
        # Posts originais - distribuir nos horários de pico
        peak_hours = [h for h in range(24) if self.PEAK_HOURS[h]["score"] >= 0.8]
        for i, hour in enumerate(random.sample(peak_hours, min(self.DAILY_MIX["posts"], len(peak_hours)))):
            schedule.append({
                "time": f"{hour:02d}:{random.randint(0, 45):02d}",
                "type": "post",
                "priority": "high"
            })
        
        # Thread - à noite
        schedule.append({
            "time": f"{random.choice([19, 20, 21]):02d}:{random.randint(0, 30):02d}",
            "type": "thread",
            "priority": "high"
        })
        
        # Replies - distribuir ao longo do dia
        reply_hours = list(range(7, 24))  # Das 7h às 23h
        replies_per_hour = self.DAILY_MIX["replies"] // len(reply_hours)
        
        for hour in reply_hours:
            for _ in range(replies_per_hour):
                schedule.append({
                    "time": f"{hour:02d}:{random.randint(0, 59):02d}",
                    "type": "reply",
                    "priority": "medium"
                })
        
        # Ordenar por horário
        schedule.sort(key=lambda x: x["time"])
        
        return schedule
    
    def get_engagement_targets(self) -> Dict:
        """
        Retorna targets de engajamento baseados no nicho.
        """
        return {
            "keywords": self.config["keywords"],
            "min_followers": 10000,
            "max_followers": 500000,
            "min_likes_viral": 100,
            "min_retweets_viral": 20,
            "max_age_hours": 4,
            "preferred_tone": self.config["tone"]
        }
    
    def calculate_monetization_potential(
        self,
        followers: int,
        avg_impressions: int,
        engagement_rate: float
    ) -> Dict:
        """
        Calcula potencial de monetização.
        
        Requisitos X Premium Revenue Share:
        - X Premium subscription
        - 500+ followers
        - 5M+ impressions últimos 3 meses
        - Conta 3+ meses
        """
        monthly_impressions = avg_impressions * 30
        
        # Estimativa de CPM do X (varia muito, ~$0.50-5.00)
        estimated_cpm = 1.5
        
        return {
            "eligible": followers >= 500 and monthly_impressions * 3 >= 5_000_000,
            "followers_needed": max(0, 500 - followers),
            "monthly_impressions": monthly_impressions,
            "impressions_3m": monthly_impressions * 3,
            "impressions_needed": max(0, 5_000_000 - (monthly_impressions * 3)),
            "engagement_rate": engagement_rate,
            "estimated_monthly_revenue": (monthly_impressions / 1000) * estimated_cpm,
            "estimated_at_5m_impressions": (5_000_000 / 1000 / 3) * estimated_cpm,
        }
