"""
Bot para X (Twitter) - Postagem Manual com Aprovação e Dashboard

Este script implementa um bot que permite ao usuário criar postagens manualmente,
se inspirando em tendências globais, aprovar cada uma, e agendá-las ou postar imediatamente no X.
O bot publica até 16 posts por dia, maximizando o limite da API (500 posts/mês no nível do app).

Configuração:
- Requer um arquivo .env com as credenciais da API do X
- Usa um arquivo posts.json para gerenciar postagens pendentes, aprovadas e agendadas
- Posta até 16 vezes por dia, das 08:00 às 23:00, a cada 60 minutos

Autor: Uillen Machado
Repositório: github.com/uillenmachado/botx
"""

import tweepy
import os
import json
from dotenv import load_dotenv
import logging
import schedule
import time
from datetime import datetime, timedelta
from functools import wraps
from inputimeout import inputimeout, TimeoutOccurred

# Configurações
WOEID_GLOBAL = 1  # ID para tendências globais
NUM_TRENDS = 5    # Número de tendências para buscar
DAILY_POST_LIMIT = 16  # Máximo de posts por dia (para usar o limite da API)
MONTHLY_POST_LIMIT = 500  # Limite mensal da API (nível do app)
START_HOUR = "08:00"  # Horário de início dos posts
END_HOUR = "23:00"    # Horário de fim dos posts
POST_INTERVAL_MINUTES = 60  # Intervalo entre posts (60 minutos)
POSTS_FILE = "posts.json"  # Arquivo para gerenciar postagens

# Variáveis globais
monthly_posts = 0
daily_posts = 0
posts_data = {"pending": [], "approved": [], "scheduled": []}
trends_list = []

# Configura o logging
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

# Função para retry com backoff
def retry_with_backoff(max_retries=3, initial_backoff=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            backoff = initial_backoff
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logging.error(f"Falha após {max_retries} tentativas: {e}")
                        raise
                    logging.warning(f"Tentativa {retries} falhou: {e}. Tentando novamente em {backoff} segundos.")
                    time.sleep(backoff)
                    backoff *= 2  # Backoff exponencial
            return wrapper
        return decorator

# Valida as credenciais
def validate_credentials():
    """
    Verifica se todas as credenciais necessárias estão presentes no arquivo .env.
    Returns:
        bool: True se todas as credenciais estão presentes, False caso contrário.
    """
    required_keys = ["API_KEY", "API_KEY_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET", "BEARER_TOKEN"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    if missing_keys:
        missing_list = ", ".join(missing_keys)
        logging.error(f"Credenciais ausentes no arquivo .env: {missing_list}")
        return False
    return True

# Busca tendências globais
@retry_with_backoff()
def get_trends():
    """
    Busca as tendências globais do X usando a API v1.1.
    Returns:
        list: Lista com as 5 principais tendências globais.
              Retorna uma lista com uma mensagem de erro em caso de falha.
    """
    try:
        auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)
        trends = api.get_place_trends(id=WOEID_GLOBAL)
        if trends and len(trends) > 0 and isinstance(trends[0], dict) and "trends" in trends[0]:
            trend_list = [trend["name"] for trend in trends[0]["trends"]][:NUM_TRENDS]
            return trend_list
        else:
            logging.error("Nenhuma tendência encontrada.")
            return ["Nenhuma tendência disponível"]
    except Exception as e:
        logging.error(f"Erro ao buscar tendências: {e}")
        return ["Erro ao buscar tendências"]

# Atualiza as tendências
def update_trends():
    """
    Atualiza a lista de tendências globais.
    """
    global trends_list
    trends_list = get_trends()
    logging.info("Tendências atualizadas: " + ", ".join(trends_list))

# Carrega ou inicializa o arquivo de postagens
def load_posts():
    """
    Carrega as postagens do arquivo posts.json ou inicializa um novo.
    """
    global posts_data
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, "r") as f:
            posts_data = json.load(f)
    else:
        with open(POSTS_FILE, "w") as f:
            json.dump(posts_data, f, indent=4)

# Salva as postagens no arquivo
def save_posts():
    """
    Salva as postagens no arquivo posts.json.
    """
    with open(POSTS_FILE, "w") as f:
        json.dump(posts_data, f, indent=4)

# Cria uma nova postagem
def create_post():
    """
    Permite ao usuário criar uma nova postagem e adicioná-la à lista de pendentes.
    Mostra as tendências globais para inspiração.
    """
    print("\n=== Criar Nova Postagem ===")
    print("Tendências globais para inspiração:")
    for i, trend in enumerate(trends_list, 1):
        print(f"{i}. {trend}")
    print("\nDigite sua postagem (você pode usar as tendências acima ou criar algo novo).")

    texto = input("Digite o texto da postagem (máximo 280 caracteres): ")
    if len(texto) > 280:
        print("Erro: O texto excede o limite de 280 caracteres.")
        return

    horario = input("Digite o horário para postagem (formato HH:MM, entre 08:00 e 23:00, ou deixe em branco para postar agora): ")
    if horario:
        try:
            horario_dt = datetime.strptime(horario, "%H:%M")
            start_dt = datetime.strptime(START_HOUR, "%H:%M")
            end_dt = datetime.strptime(END_HOUR, "%H:%M")
            if not (start_dt <= horario_dt <= end_dt):
                print("Erro: O horário deve estar entre 08:00 e 23:00.")
                return
        except ValueError:
            print("Erro: Formato de horário inválido. Use HH:MM (ex.: 14:30).")
            return
    else:
        horario = "now"

    post = {"text": texto, "time": horario, "status": "pending"}
    posts_data["pending"].append(post)
    save_posts()
    print(f"Postagem criada e adicionada à lista de pendentes: {texto} às {horario}")

# Aprova postagens pendentes
def approve_posts():
    """
    Permite ao usuário aprovar ou rejeitar postagens pendentes, com opção de postar agora ou agendar.
    """
    if not posts_data["pending"]:
        print("Nenhuma postagem pendente para aprovar.")
        return

    print("\n=== Aprovar Postagens ===")
    for i, post in enumerate(posts_data["pending"]):
        print(f"\nPostagem {i + 1}:")
        print(f"Texto: {post['text']}")
        print(f"Horário: {post['time']}")
        try:
            choice = inputimeout(
                prompt="Aprovar esta postagem? (s/n) [Timeout em 30s]: ",
                timeout=30
            ).lower()
            if choice == "s":
                if post["time"] == "now":
                    action = input("Postar agora (1) ou agendar para outro horário (2)? ")
                    if action == "1":
                        post["status"] = "approved"
                        post_now(post["text"])
                        print("Postagem publicada imediatamente!")
                    else:
                        new_time = input("Digite o novo horário (formato HH:MM, entre 08:00 e 23:00): ")
                        try:
                            horario_dt = datetime.strptime(new_time, "%H:%M")
                            start_dt = datetime.strptime(START_HOUR, "%H:%M")
                            end_dt = datetime.strptime(END_HOUR, "%H:%M")
                            if not (start_dt <= horario_dt <= end_dt):
                                print("Erro: O horário deve estar entre 08:00 e 23:00.")
                                continue
                            post["time"] = new_time
                        except ValueError:
                            print("Erro: Formato de horário inválido. Postagem mantida como pendente.")
                            continue
                        post["status"] = "approved"
                        posts_data["approved"].append(post)
                        print("Postagem aprovada e pronta para agendamento!")
                else:
                    post["status"] = "approved"
                    posts_data["approved"].append(post)
                    print("Postagem aprovada e pronta para agendamento!")
            else:
                print("Postagem rejeitada.")
        except TimeoutOccurred:
            print("Tempo esgotado. Postagem mantida como pendente.")
    posts_data["pending"] = [p for p in posts_data["pending"] if p["status"] == "pending"]
    save_posts()

# Publica um tweet imediatamente
@retry_with_backoff()
def post_now(text):
    """
    Publica um tweet imediatamente.
    Args:
        text (str): Texto do tweet a ser publicado.
    """
    global monthly_posts, daily_posts
    try:
        if monthly_posts >= MONTHLY_POST_LIMIT:
            logging.warning("Limite mensal de postagens atingido. Pulando postagem.")
            return
        if daily_posts >= DAILY_POST_LIMIT:
            logging.warning("Limite diário de postagens atingido. Pulando postagem.")
            return

        client.create_tweet(text=text)
        monthly_posts += 1
        daily_posts += 1
        logging.info(f"Post publicado imediatamente: {text}. Total mensal: {monthly_posts}/{MONTHLY_POST_LIMIT}, Diário: {daily_posts}/{DAILY_POST_LIMIT}")
    except Exception as e:
        logging.error(f"Erro ao postar: {e}")

# Agenda postagens aprovadas
def schedule_posts():
    """
    Agenda as postagens aprovadas para os horários definidos.
    """
    for post in posts_data["approved"]:
        if post["time"] != "now":
            schedule.every().day.at(post["time"]).do(post_tweet, post["text"])
            post["status"] = "scheduled"
            posts_data["scheduled"].append(post)
    posts_data["approved"] = [p for p in posts_data["approved"] if p["status"] != "scheduled"]
    save_posts()
    logging.info("Postagens aprovadas foram agendadas.")

# Publica um tweet agendado
@retry_with_backoff()
def post_tweet(text):
    """
    Publica um tweet agendado.
    Args:
        text (str): Texto do tweet a ser publicado.
    """
    global monthly_posts, daily_posts
    try:
        if monthly_posts >= MONTHLY_POST_LIMIT:
            logging.warning("Limite mensal de postagens atingido. Pulando postagem.")
            return
        if daily_posts >= DAILY_POST_LIMIT:
            logging.warning("Limite diário de postagens atingido. Pulando postagem.")
            return

        client.create_tweet(text=text)
        monthly_posts += 1
        daily_posts += 1
        logging.info(f"Post publicado: {text}. Total mensal: {monthly_posts}/{MONTHLY_POST_LIMIT}, Diário: {daily_posts}/{DAILY_POST_LIMIT}")
    except Exception as e:
        logging.error(f"Erro ao postar: {e}")

# Reseta contadores diários
def reset_daily_counters():
    """
    Reseta o contador diário de postagens e atualiza o mensal no início de cada mês.
    """
    global daily_posts, monthly_posts
    current_date = datetime.now()
    if current_date.day == 1 and current_date.hour == 0 and current_date.minute == 0:
        monthly_posts = 0
        logging.info("Contador mensal resetado.")
    daily_posts = 0
    logging.info("Contador diário resetado.")

# Função principal
def main():
    """
    Função principal que inicializa o bot e configura o agendamento.
    """
    if not validate_credentials():
        logging.error("Impossível iniciar o bot devido a credenciais faltantes.")
        return

    load_posts()
    update_trends()

    # Agenda o reset diário à meia-noite
    schedule.every().day.at("00:00").do(reset_daily_counters)
    # Agenda a atualização de tendências às 07:00
    schedule.every().day.at("07:00").do(update_trends)
    # Agenda a verificação de postagens aprovadas a cada 5 minutos
    schedule.every(5).minutes.do(schedule_posts)

    logging.info("Bot iniciado. Aguardando entrada do usuário e horários de postagem...")

    while True:
        print("\n=== Dashboard do Bot ===")
        print("1. Criar nova postagem (ver tendências para inspiração)")
        print("2. Aprovar postagens pendentes (postar agora ou agendar)")
        print("3. Ver postagens pendentes")
        print("4. Ver postagens aprovadas (prontas para agendamento)")
        print("5. Ver postagens agendadas")
        print("6. Sair e continuar agendamento")
        choice = input("Escolha uma opção (1-6): ")

        if choice == "1":
            create_post()
        elif choice == "2":
            approve_posts()
        elif choice == "3":
            print("\n=== Postagens Pendentes ===")
            if not posts_data["pending"]:
                print("Nenhuma postagem pendente.")
            for i, post in enumerate(posts_data["pending"], 1):
                print(f"{i}. Texto: {post['text']}, Horário: {post['time']}")
        elif choice == "4":
            print("\n=== Postagens Aprovadas (Prontas para Agendamento) ===")
            if not posts_data["approved"]:
                print("Nenhuma postagem aprovada.")
            for i, post in enumerate(posts_data["approved"], 1):
                print(f"{i}. Texto: {post['text']}, Horário: {post['time']}")
        elif choice == "5":
            print("\n=== Postagens Agendadas ===")
            if not posts_data["scheduled"]:
                print("Nenhuma postagem agendada.")
            for i, post in enumerate(posts_data["scheduled"], 1):
                print(f"{i}. Texto: {post['text']}, Horário: {post['time']}")
        elif choice == "6":
            print("Saindo do dashboard. O bot continuará rodando para postagens agendadas.")
            break

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()