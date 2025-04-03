"""
Arquivo de Configurações para Bot do X (Twitter)

Este arquivo contém todas as configurações necessárias para o funcionamento
do bot, como limites da API, intervalos de postagem, e configurações gerais.

Separar as configurações em um arquivo próprio facilita a manutenção e
permite alterar parâmetros sem mexer na lógica principal do programa.

Autor: Uillen Machado
Repositório: github.com/uillenmachado/botx
"""

import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Credenciais da API do X (Twitter)
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

# Configurações de Tendências
WOEID_GLOBAL = 1  # ID para tendências globais (1 = Global)
NUM_TRENDS = 5    # Número de tendências para buscar e exibir

# Limites da API
DAILY_POST_LIMIT = 16        # Máximo de posts por dia
MONTHLY_POST_LIMIT = 500     # Limite mensal da API (nível do app)
API_USER_LEVEL_LIMIT = 1500  # Limite mensal da API (nível do usuário)

# Configurações de Horários
START_HOUR = "08:00"        # Horário de início dos posts
END_HOUR = "23:00"          # Horário de fim dos posts
POST_INTERVAL_MINUTES = 60  # Intervalo entre posts (60 minutos)
TREND_UPDATE_HOUR = "07:00" # Horário para atualização diária das tendências

# Arquivos e Diretórios
POSTS_FILE = "posts.json"  # Arquivo para gerenciar postagens
LOG_FILE = "bot_log.txt"   # Arquivo de log

# Configurações de Timeout e Retry
MENU_TIMEOUT = 60          # Timeout do menu principal em segundos
APPROVE_TIMEOUT = 30       # Timeout para aprovação de posts em segundos
MAX_RETRIES = 3            # Número máximo de tentativas para operações da API
INITIAL_BACKOFF = 5        # Tempo inicial de espera entre tentativas (segundos)

# Configurações de Formatação
DATE_FORMAT = "%d/%m/%Y %H:%M"  # Formato de data para exibição
MAX_TWEET_LENGTH = 280          # Limite de caracteres para um tweet

# Validação de credenciais
def validate_credentials():
    """
    Verifica se todas as credenciais necessárias estão presentes no arquivo .env.
    
    Returns:
        tuple: (bool, list) - True se todas as credenciais estão presentes e
               lista vazia, ou False e lista de chaves ausentes.
    """
    required_keys = ["API_KEY", "API_KEY_SECRET", "ACCESS_TOKEN", 
                    "ACCESS_TOKEN_SECRET", "BEARER_TOKEN"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    
    return (len(missing_keys) == 0, missing_keys)