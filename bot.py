"""
Bot para X (Twitter) - Postagem Manual com Aprovação e Dashboard

Este script implementa um bot que permite ao usuário criar postagens manualmente,
se inspirando em tendências globais, aprovar cada uma, e agendá-las ou postar 
imediatamente no X (Twitter).

Configuração:
- Requer um arquivo .env com as seguintes credenciais da API do X:
  API_KEY=sua_api_key
  API_KEY_SECRET=sua_api_key_secret
  ACCESS_TOKEN=seu_access_token
  ACCESS_TOKEN_SECRET=seu_access_token_secret
  BEARER_TOKEN=seu_bearer_token

- Usa um arquivo posts.json para gerenciar postagens pendentes, aprovadas e agendadas
- Posta até 16 vezes por dia, das 08:00 às 23:00, a cada 60 minutos
- Busca as 5 principais tendências globais diariamente às 07:00 para inspiração

Estrutura do arquivo posts.json:
{
    "pending": [
        {"text": "texto do post", "time": "HH:MM", "status": "pending"}
    ],
    "approved": [
        {"text": "texto do post", "time": "HH:MM", "status": "approved"}
    ],
    "scheduled": [
        {"text": "texto do post", "time": "HH:MM", "status": "scheduled"}
    ]
}

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
last_trend_update = None

# Configura o logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot_log.txt"),
        logging.StreamHandler()
    ]
)

# Carrega as chaves do arquivo .env
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

# Função para retry com backoff
def retry_with_backoff(max_retries=3, initial_backoff=5):
    """
    Decorator para tentar executar uma função várias vezes com backoff exponencial em caso de falha.
    
    Args:
        max_retries (int): Número máximo de tentativas
        initial_backoff (int): Tempo inicial de espera entre tentativas em segundos
        
    Returns:
        function: Função decorada com retry
    """
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
            return None  # Caso todas as tentativas falhem
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
    except tweepy.TweepyException as e:
        logging.error(f"Erro ao buscar tendências: {e}")
        return ["Erro ao buscar tendências"]
    except Exception as e:
        logging.error(f"Erro inesperado ao buscar tendências: {e}")
        return ["Erro inesperado ao buscar tendências"]

# Atualiza as tendências
def update_trends():
    """
    Atualiza a lista de tendências globais e registra o momento da atualização.
    """
    global trends_list, last_trend_update
    trends_list = get_trends()
    last_trend_update = datetime.now()
    logging.info("Tendências atualizadas: " + ", ".join(trends_list))

# Carrega ou inicializa o arquivo de postagens
def load_posts():
    """
    Carrega as postagens do arquivo posts.json ou inicializa um novo.
    Em caso de erro ao ler o arquivo, cria um novo.
    """
    global posts_data
    try:
        if os.path.exists(POSTS_FILE):
            with open(POSTS_FILE, "r", encoding="utf-8") as f:
                try:
                    posts_data = json.load(f)
                    # Verifica se o arquivo tem a estrutura correta
                    if not all(key in posts_data for key in ["pending", "approved", "scheduled"]):
                        raise ValueError("Estrutura incorreta no arquivo posts.json")
                except (json.JSONDecodeError, ValueError) as e:
                    logging.error(f"Erro ao ler {POSTS_FILE}: {e}. Criando novo arquivo.")
                    posts_data = {"pending": [], "approved": [], "scheduled": []}
                    save_posts()
        else:
            with open(POSTS_FILE, "w", encoding="utf-8") as f:
                json.dump(posts_data, f, indent=4)
                logging.info(f"Arquivo {POSTS_FILE} criado.")
    except Exception as e:
        logging.error(f"Erro ao carregar posts: {e}")
        posts_data = {"pending": [], "approved": [], "scheduled": []}

# Salva as postagens no arquivo
def save_posts():
    """
    Salva as postagens no arquivo posts.json.
    Inclui tratamento de erros para garantir que os dados não sejam perdidos.
    """
    try:
        with open(POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(posts_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Erro ao salvar posts: {e}")
        # Tenta salvar em um arquivo alternativo em caso de erro
        try:
            backup_file = f"{POSTS_FILE}.backup.{int(time.time())}.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(posts_data, f, indent=4, ensure_ascii=False)
            logging.info(f"Backup dos posts salvo em {backup_file}")
        except Exception as backup_err:
            logging.critical(f"Falha ao criar backup dos posts: {backup_err}")

# Valida um horário de postagem
def validate_time(time_str):
    """
    Valida se o horário está no formato correto e dentro do intervalo permitido.
    
    Args:
        time_str (str): Horário no formato HH:MM.
        
    Returns:
        bool: True se o horário é válido, False caso contrário.
    """
    try:
        if time_str == "now":
            return True
            
        horario_dt = datetime.strptime(time_str, "%H:%M")
        start_dt = datetime.strptime(START_HOUR, "%H:%M")
        end_dt = datetime.strptime(END_HOUR, "%H:%M")
        return start_dt.time() <= horario_dt.time() <= end_dt.time()
    except ValueError:
        return False

# Cria uma nova postagem
def create_post():
    """
    Permite ao usuário criar uma nova postagem e adicioná-la à lista de pendentes.
    Mostra as tendências globais para inspiração.
    Inclui validações para o texto e horário da postagem.
    """
    print("\n=== Criar Nova Postagem ===")
    print("Tendências globais para inspiração:")
    for i, trend in enumerate(trends_list, 1):
        print(f"{i}. {trend}")
    
    if last_trend_update:
        print(f"\nÚltima atualização das tendências: {last_trend_update.strftime('%d/%m/%Y %H:%M')}")
    
    print("\nDigite sua postagem (você pode usar as tendências acima ou criar algo novo).")

    texto = input("Digite o texto da postagem (máximo 280 caracteres): ").strip()
    if not texto:
        print("Erro: O texto não pode estar vazio.")
        return
    if len(texto) > 280:
        print(f"Erro: O texto excede o limite de 280 caracteres. Atual: {len(texto)}")
        return

    horario = input("Digite o horário para postagem (formato HH:MM, entre 08:00 e 23:00, ou deixe em branco para postar agora): ").strip()
    if not horario:
        horario = "now"
    elif not validate_time(horario):
        print("Erro: Formato de horário inválido ou fora do intervalo permitido (08:00-23:00).")
        return

    # Verificar se já existe um post agendado para este horário
    if horario != "now" and any(p["time"] == horario for p in posts_data["scheduled"]):
        overwrite = input(f"Já existe um post agendado para {horario}. Deseja continuar? (s/n): ").lower()
        if overwrite != "s":
            print("Operação cancelada.")
            return

    post = {"text": texto, "time": horario, "status": "pending", "created_at": datetime.now().isoformat()}
    posts_data["pending"].append(post)
    save_posts()
    print(f"Postagem criada e adicionada à lista de pendentes: {texto} às {horario}")

# Aprova postagens pendentes
def approve_posts():
    """
    Permite ao usuário aprovar ou rejeitar postagens pendentes, com opção de postar agora ou agendar.
    Inclui validações para horários de agendamento.
    """
    if not posts_data["pending"]:
        print("Nenhuma postagem pendente para aprovar.")
        return

    print("\n=== Aprovar Postagens ===")
    
    # Cria uma cópia para iterar, pois vamos modificar a lista original
    pending_posts = posts_data["pending"].copy()
    
    for i, post in enumerate(pending_posts):
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
                        # Remover da lista de pendentes
                        posts_data["pending"].remove(post)
                        
                        # Atualizar status e adicionar à lista de aprovados
                        post["status"] = "approved"
                        posts_data["approved"].append(post)
                        save_posts()
                        
                        # Postar imediatamente
                        post_now(post["text"])
                        print("Postagem publicada imediatamente!")
                    else:
                        new_time = input("Digite o novo horário (formato HH:MM, entre 08:00 e 23:00): ")
                        if not validate_time(new_time):
                            print("Erro: Formato de horário inválido ou fora do intervalo permitido (08:00-23:00).")
                            continue
                        
                        # Remover da lista de pendentes
                        posts_data["pending"].remove(post)
                        
                        # Atualizar hora e status
                        post["time"] = new_time
                        post["status"] = "approved"
                        posts_data["approved"].append(post)
                        save_posts()
                        print("Postagem aprovada e pronta para agendamento!")
                else:
                    # Remover da lista de pendentes
                    posts_data["pending"].remove(post)
                    
                    # Atualizar status
                    post["status"] = "approved"
                    posts_data["approved"].append(post)
                    save_posts()
                    print("Postagem aprovada e pronta para agendamento!")
            else:
                # Remover da lista de pendentes se rejeitada
                posts_data["pending"].remove(post)
                print("Postagem rejeitada e removida da lista.")
                save_posts()
                
        except TimeoutOccurred:
            print("Tempo esgotado. Postagem mantida como pendente.")
    
    save_posts()

# Publica um tweet imediatamente
@retry_with_backoff()
def post_now(text):
    """
    Publica um tweet imediatamente.
    
    Args:
        text (str): Texto do tweet a ser publicado.
    
    Returns:
        bool: True se o post foi publicado com sucesso, False caso contrário.
    """
    global monthly_posts, daily_posts
    try:
        if monthly_posts >= MONTHLY_POST_LIMIT:
            logging.warning("Limite mensal de postagens atingido. Pulando postagem.")
            print("Aviso: Limite mensal de postagens atingido. Postagem não enviada.")
            return False
            
        if daily_posts >= DAILY_POST_LIMIT:
            logging.warning("Limite diário de postagens atingido. Pulando postagem.")
            print("Aviso: Limite diário de postagens atingido. Postagem não enviada.")
            return False

        response = client.create_tweet(text=text)
        monthly_posts += 1
        daily_posts += 1
        logging.info(f"Post publicado imediatamente: {text}. Total mensal: {monthly_posts}/{MONTHLY_POST_LIMIT}, Diário: {daily_posts}/{DAILY_POST_LIMIT}")
        return True
    except tweepy.TweepyException as e:
        logging.error(f"Erro ao postar tweet: {e}")
        print(f"Erro ao publicar tweet: {e}")
        return False

# Remove um post da lista de agendados
def remove_scheduled_post(text):
    """
    Remove um post da lista de agendados após ser publicado.
    
    Args:
        text (str): Texto do post que foi publicado.
    """
    global posts_data
    posts_data["scheduled"] = [p for p in posts_data["scheduled"] if p["text"] != text]
    save_posts()
    logging.info(f"Post removido da lista de agendados: {text[:30]}...")

# Agenda postagens aprovadas
def schedule_posts():
    """
    Agenda as postagens aprovadas para os horários definidos.
    Transfere posts da lista de aprovados para a lista de agendados.
    """
    if not posts_data["approved"]:
        return
        
    logging.info(f"Verificando posts aprovados para agendamento. Total: {len(posts_data['approved'])}")
    
    # Cria uma cópia para iterar, pois vamos modificar a lista original
    approved_posts = posts_data["approved"].copy()
    
    for post in approved_posts:
        if post["time"] != "now":
            # Cria o agendamento
            schedule_job = schedule.every().day.at(post["time"]).do(post_tweet, post["text"])
            
            # Atualiza o status e move para a lista de agendados
            post["status"] = "scheduled"
            post["scheduled_at"] = datetime.now().isoformat()
            posts_data["scheduled"].append(post)
            posts_data["approved"].remove(post)
            
            logging.info(f"Post agendado para {post['time']}: {post['text'][:30]}...")

    save_posts()
    if len(approved_posts) > 0:
        logging.info("Postagens aprovadas foram agendadas.")

# Publica um tweet agendado
@retry_with_backoff()
def post_tweet(text):
    """
    Publica um tweet agendado.
    
    Args:
        text (str): Texto do tweet a ser publicado.
    
    Returns:
        bool: True se o post foi publicado com sucesso, False caso contrário.
    """
    global monthly_posts, daily_posts
    try:
        if monthly_posts >= MONTHLY_POST_LIMIT:
            logging.warning("Limite mensal de postagens atingido. Pulando postagem agendada.")
            return False
            
        if daily_posts >= DAILY_POST_LIMIT:
            logging.warning("Limite diário de postagens atingido. Pulando postagem agendada.")
            return False

        client.create_tweet(text=text)
        monthly_posts += 1
        daily_posts += 1
        logging.info(f"Post agendado publicado: {text[:30]}... Total mensal: {monthly_posts}/{MONTHLY_POST_LIMIT}, Diário: {daily_posts}/{DAILY_POST_LIMIT}")
        
        # Remover o post da lista de agendados
        remove_scheduled_post(text)
        return True
    except tweepy.TweepyException as e:
        logging.error(f"Erro ao postar tweet agendado: {e}")
        return False

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

# Exibe estatísticas do bot
def display_stats():
    """
    Exibe estatísticas sobre o uso do bot e limites da API.
    """
    print("\n=== Estatísticas do Bot ===")
    print(f"Posts enviados hoje: {daily_posts}/{DAILY_POST_LIMIT}")
    print(f"Posts enviados este mês: {monthly_posts}/{MONTHLY_POST_LIMIT}")
    
    print(f"\nTotal de postagens:")
    print(f"- Pendentes: {len(posts_data['pending'])}")
    print(f"- Aprovadas: {len(posts_data['approved'])}")
    print(f"- Agendadas: {len(posts_data['scheduled'])}")
    
    print(f"\nTendências atuais: {', '.join(trends_list)}")
    if last_trend_update:
        print(f"Última atualização das tendências: {last_trend_update.strftime('%d/%m/%Y %H:%M')}")

# Função principal
def main():
    """
    Função principal que inicializa o bot e configura o agendamento.
    Fornece um dashboard interativo para o usuário gerenciar postagens.
    """
    global client
    
    print("Inicializando Bot para X...")
    
    if not validate_credentials():
        logging.error("Impossível iniciar o bot devido a credenciais faltantes.")
        print("Erro: Credenciais da API do X não encontradas no arquivo .env.")
        print("Verifique se o arquivo .env existe e contém todas as chaves necessárias.")
        return

    try:
        # Autentica com a API do X
        client = tweepy.Client(
            bearer_token=BEARER_TOKEN,
            consumer_key=API_KEY,
            consumer_secret=API_KEY_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET
        )
        
        # Teste de conexão
        client.get_me()
        logging.info("Conexão com a API do X estabelecida com sucesso.")
    except Exception as e:
        logging.error(f"Erro ao conectar com a API do X: {e}")
        print(f"Erro ao conectar com a API do X: {e}")
        print("Verifique suas credenciais e conexão de internet.")
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
    print("Bot para X iniciado com sucesso!")

    while True:
        # Executa tarefas agendadas pendentes
        schedule.run_pending()
        
        print("\n=== Dashboard do Bot ===")
        print("1. Criar nova postagem (ver tendências para inspiração)")
        print("2. Aprovar postagens pendentes (postar agora ou agendar)")
        print("3. Ver postagens pendentes")
        print("4. Ver postagens aprovadas (prontas para agendamento)")
        print("5. Ver postagens agendadas")
        print("6. Ver estatísticas do bot")
        print("7. Atualizar tendências manualmente")
        print("8. Sair e continuar agendamento")
        
        try:
            choice = inputimeout(prompt="Escolha uma opção (1-8) [Timeout em 60s]: ", timeout=60)
        except TimeoutOccurred:
            # Se o timeout ocorrer, executa as tarefas agendadas e continua
            continue

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
            display_stats()
        elif choice == "7":
            print("Atualizando tendências...")
            update_trends()
            print(f"Tendências atualizadas: {', '.join(trends_list)}")
        elif choice == "8":
            print("Saindo do dashboard. O bot continuará rodando para postagens agendadas.")
            break
        else:
            print("Opção inválida. Por favor, escolha uma opção de 1 a 8.")

    print("\nBot continua executando em segundo plano para publicar posts agendados.")
    print("Para interagir novamente com o dashboard, execute o bot novamente.")
    
    try:
        # Loop para manter o bot rodando e executar as tarefas agendadas
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nBot encerrado pelo usuário.")
        logging.info("Bot encerrado pelo usuário.")

if __name__ == "__main__":
    main()