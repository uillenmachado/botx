import tweepy
import os
from dotenv import load_dotenv
import logging
import schedule
import time
import random

# Configura o logging para ver o que o bot está fazendo
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Carrega as chaves do arquivo .env
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

# Autentica com a API do X
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_KEY_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# Função para buscar tendências globais
def get_trends():
    try:
        # Autentica para usar a API v1.1 (necessária para tendências)
        auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)
        # Busca tendências globais (WOEID 1 é global)
        trends = api.get_place_trends(id=1)
        if trends and trends[0] and "trends" in trends[0]:
            trend_list = [trend["name"] for trend in trends[0]["trends"]][:5]  # Pega as 5 primeiras
            return trend_list
        else:
            logging.error("Nenhuma tendência encontrada.")
            return ["Nenhuma tendência disponível"]
    except Exception as e:
        logging.error(f"Erro ao buscar tendências: {e}")
        return ["Erro ao buscar tendências"]

# Função para postar um tweet sobre uma tendência
def post_trend_tweet():
    try:
        trends = get_trends()
        trend = random.choice(trends)  # Escolhe uma tendência aleatória
        texto = f"Assunto do momento: {trend}! O que você acha disso? #Tendencias"
        client.create_tweet(text=texto)
        logging.info(f"Post publicado: {texto}")
    except Exception as e:
        logging.error(f"Erro ao postar: {e}")

# Agenda o post para diariamente às 10:00
schedule.every().day.at("10:00").do(post_trend_tweet)

# Mantém o bot rodando
logging.info("Bot iniciado. Aguardando horário de postagem...")
while True:
    schedule.run_pending()
    time.sleep(60)  # Verifica a cada minuto